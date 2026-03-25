"""Tests for polymarket_predictor.backtest.engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from polymarket_predictor.backtest.engine import BacktestEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _gamma_event(
    slug: str = "btc-above-70k",
    question: str = "Will BTC be above 70k?",
    volume: float = 10_000,
    closed: bool = True,
    resolution: str | None = "yes",
    outcome_prices: str = "[0.98, 0.02]",
    condition_id: str = "cond-1",
    category: str = "Crypto",
    end_date: str = "2024-06-01",
) -> dict[str, Any]:
    """Build a single market dict as returned inside a Gamma event."""
    return {
        "slug": slug,
        "question": question,
        "volume": str(volume),
        "closed": closed,
        "resolution": resolution,
        "outcomePrices": outcome_prices,
        "conditionId": condition_id,
        "category": category,
        "endDate": end_date,
    }


def _gamma_response(*events_markets: list[dict]) -> list[dict]:
    """Build a Gamma API-style list of events, each with a 'markets' list."""
    return [{"markets": mkts} for mkts in events_markets]


# ---------------------------------------------------------------------------
# fetch_resolved_markets
# ---------------------------------------------------------------------------


class TestFetchResolvedMarkets:
    """fetch_resolved_markets parses Gamma events and filters."""

    @pytest.mark.asyncio
    async def test_parses_event_response(self, tmp_path: Path):
        events = _gamma_response(
            [_gamma_event(slug="m1", volume=5000, resolution="yes")],
            [_gamma_event(slug="m2", volume=2000, resolution="no")],
        )

        mock_response = MagicMock()
        mock_response.json.return_value = events
        mock_response.raise_for_status = MagicMock()

        with patch("polymarket_predictor.backtest.engine.httpx.AsyncClient") as ClientCls:
            client_ctx = AsyncMock()
            client_inst = AsyncMock()
            client_inst.get.return_value = mock_response
            client_ctx.__aenter__.return_value = client_inst
            client_ctx.__aexit__.return_value = False
            ClientCls.return_value = client_ctx

            engine = BacktestEngine(data_dir=tmp_path)
            markets = await engine.fetch_resolved_markets(limit=10, min_volume=500)

        assert len(markets) == 2
        slugs = {m["slug"] for m in markets}
        assert "m1" in slugs
        assert "m2" in slugs

    @pytest.mark.asyncio
    async def test_filters_by_min_volume(self, tmp_path: Path):
        events = _gamma_response(
            [
                _gamma_event(slug="big", volume=10000, resolution="yes"),
                _gamma_event(slug="small", volume=100, resolution="yes"),
            ]
        )

        mock_response = MagicMock()
        mock_response.json.return_value = events
        mock_response.raise_for_status = MagicMock()

        with patch("polymarket_predictor.backtest.engine.httpx.AsyncClient") as ClientCls:
            client_ctx = AsyncMock()
            client_inst = AsyncMock()
            client_inst.get.return_value = mock_response
            client_ctx.__aenter__.return_value = client_inst
            client_ctx.__aexit__.return_value = False
            ClientCls.return_value = client_ctx

            engine = BacktestEngine(data_dir=tmp_path)
            markets = await engine.fetch_resolved_markets(limit=10, min_volume=500)

        assert len(markets) == 1
        assert markets[0]["slug"] == "big"

    @pytest.mark.asyncio
    async def test_determines_resolution_from_prices(self, tmp_path: Path):
        """When no resolution string, infer from prices."""
        events = _gamma_response(
            [
                _gamma_event(
                    slug="inferred-yes",
                    resolution=None,
                    outcome_prices="[0.98, 0.02]",
                    volume=5000,
                ),
                _gamma_event(
                    slug="inferred-no",
                    resolution=None,
                    outcome_prices="[0.02, 0.98]",
                    volume=5000,
                ),
            ]
        )

        mock_response = MagicMock()
        mock_response.json.return_value = events
        mock_response.raise_for_status = MagicMock()

        with patch("polymarket_predictor.backtest.engine.httpx.AsyncClient") as ClientCls:
            client_ctx = AsyncMock()
            client_inst = AsyncMock()
            client_inst.get.return_value = mock_response
            client_ctx.__aenter__.return_value = client_inst
            client_ctx.__aexit__.return_value = False
            ClientCls.return_value = client_ctx

            engine = BacktestEngine(data_dir=tmp_path)
            markets = await engine.fetch_resolved_markets(limit=10, min_volume=500)

        by_slug = {m["slug"]: m for m in markets}
        assert by_slug["inferred-yes"]["resolved_yes"] is True
        assert by_slug["inferred-no"]["resolved_yes"] is False

    @pytest.mark.asyncio
    async def test_skips_ambiguous_resolutions(self, tmp_path: Path):
        """Market with prices around 0.5 should be skipped."""
        events = _gamma_response(
            [
                _gamma_event(
                    slug="ambiguous",
                    resolution=None,
                    outcome_prices="[0.50, 0.50]",
                    volume=5000,
                ),
            ]
        )

        mock_response = MagicMock()
        mock_response.json.return_value = events
        mock_response.raise_for_status = MagicMock()

        with patch("polymarket_predictor.backtest.engine.httpx.AsyncClient") as ClientCls:
            client_ctx = AsyncMock()
            client_inst = AsyncMock()
            client_inst.get.return_value = mock_response
            client_ctx.__aenter__.return_value = client_inst
            client_ctx.__aexit__.return_value = False
            ClientCls.return_value = client_ctx

            engine = BacktestEngine(data_dir=tmp_path)
            markets = await engine.fetch_resolved_markets(limit=10, min_volume=500)

        assert len(markets) == 0


# ---------------------------------------------------------------------------
# _generate_quick_prediction
# ---------------------------------------------------------------------------


class TestGenerateQuickPrediction:
    """Quick prediction adds noise within [-0.08, 0.08], clamped to [0.01, 0.99]."""

    def test_within_range(self):
        for odds in [0.1, 0.3, 0.5, 0.7, 0.9]:
            for _ in range(100):
                pred = BacktestEngine._generate_quick_prediction(odds)
                assert 0.01 <= pred <= 0.99
                assert abs(pred - odds) <= 0.08 + 1e-9  # allow float rounding

    def test_clamped_low(self):
        """Odds near 0 should clamp prediction to >= 0.01."""
        for _ in range(100):
            pred = BacktestEngine._generate_quick_prediction(0.01)
            assert pred >= 0.01

    def test_clamped_high(self):
        """Odds near 1 should clamp prediction to <= 0.99."""
        for _ in range(100):
            pred = BacktestEngine._generate_quick_prediction(0.99)
            assert pred <= 0.99


# ---------------------------------------------------------------------------
# run_backtest
# ---------------------------------------------------------------------------


class TestRunBacktest:
    """run_backtest processes markets, places bets, resolves, computes summary."""

    @pytest.mark.asyncio
    async def test_processes_markets(self, tmp_path: Path):
        resolved_markets = [
            {
                "slug": f"m{i}",
                "question": f"Q{i}?",
                "category": "test",
                "volume": 10000,
                "yes_price": 0.6,
                "resolved_yes": True,
                "closed_at": "2024-01-01",
                "market_id": f"cond-{i}",
            }
            for i in range(5)
        ]

        engine = BacktestEngine(data_dir=tmp_path)

        with patch.object(
            engine,
            "fetch_resolved_markets",
            new_callable=AsyncMock,
            return_value=resolved_markets,
        ):
            result = await engine.run_backtest(num_markets=5)

        assert result["total_markets"] == 5
        assert "total_bets" in result
        assert "wins" in result
        assert "losses" in result
        assert "total_pnl" in result
        assert "roi" in result
        assert "market_results" in result
        assert len(result["market_results"]) == 5

    @pytest.mark.asyncio
    async def test_summary_counts(self, tmp_path: Path):
        """Bets + skipped should equal total markets."""
        resolved_markets = [
            {
                "slug": f"m{i}",
                "question": f"Q{i}?",
                "category": "test",
                "volume": 10000,
                "yes_price": 0.6,
                "resolved_yes": i % 2 == 0,
                "closed_at": "2024-01-01",
                "market_id": f"cond-{i}",
            }
            for i in range(10)
        ]

        engine = BacktestEngine(data_dir=tmp_path)

        with patch.object(
            engine,
            "fetch_resolved_markets",
            new_callable=AsyncMock,
            return_value=resolved_markets,
        ):
            result = await engine.run_backtest(num_markets=10)

        assert result["total_bets"] + result["total_skipped"] == result["total_markets"]
        assert result["wins"] + result["losses"] == result["total_bets"]

    @pytest.mark.asyncio
    async def test_empty_markets(self, tmp_path: Path):
        """No resolved markets -> empty results."""
        engine = BacktestEngine(data_dir=tmp_path)

        with patch.object(
            engine,
            "fetch_resolved_markets",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await engine.run_backtest(num_markets=10)

        assert result["total_markets"] == 0
        assert result["total_bets"] == 0


# ---------------------------------------------------------------------------
# run_incremental
# ---------------------------------------------------------------------------


class TestRunIncremental:
    """run_incremental runs batches with optimization between them."""

    @pytest.mark.asyncio
    async def test_runs_multiple_batches(self, tmp_path: Path):
        resolved_markets = [
            {
                "slug": f"m{i}",
                "question": f"Q{i}?",
                "category": "test",
                "volume": 10000,
                "yes_price": 0.6,
                "resolved_yes": i % 2 == 0,
                "closed_at": "2024-01-01",
                "market_id": f"cond-{i}",
            }
            for i in range(20)
        ]

        engine = BacktestEngine(data_dir=tmp_path)

        with patch.object(
            engine,
            "fetch_resolved_markets",
            new_callable=AsyncMock,
            return_value=resolved_markets,
        ):
            results = await engine.run_incremental(batch_size=5, total_batches=3)

        assert isinstance(results, list)
        assert len(results) <= 3
        for batch_result in results:
            assert "batch" in batch_result
            assert "total_bets" in batch_result
            assert "wins" in batch_result
            assert "pnl" in batch_result

    @pytest.mark.asyncio
    async def test_empty_resolved(self, tmp_path: Path):
        """No resolved markets -> empty list."""
        engine = BacktestEngine(data_dir=tmp_path)

        with patch.object(
            engine,
            "fetch_resolved_markets",
            new_callable=AsyncMock,
            return_value=[],
        ):
            results = await engine.run_incremental(batch_size=5, total_batches=3)

        assert results == []


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


class TestReset:
    """reset clears backtest portfolio and history files."""

    @pytest.mark.asyncio
    async def test_reset_clears_state(self, tmp_path: Path):
        engine = BacktestEngine(data_dir=tmp_path)

        # Create some files
        engine._predictions_file.write_text("some data\n")
        engine._resolutions_file.write_text("some data\n")

        engine.reset()

        assert not engine._predictions_file.exists()
        assert not engine._resolutions_file.exists()

    @pytest.mark.asyncio
    async def test_reset_fresh_run(self, tmp_path: Path):
        """After reset, subsequent run starts fresh."""
        resolved_markets = [
            {
                "slug": "m1",
                "question": "Q1?",
                "category": "test",
                "volume": 10000,
                "yes_price": 0.6,
                "resolved_yes": True,
                "closed_at": "2024-01-01",
                "market_id": "cond-1",
            }
        ]

        engine = BacktestEngine(data_dir=tmp_path)

        # First run
        with patch.object(
            engine,
            "fetch_resolved_markets",
            new_callable=AsyncMock,
            return_value=resolved_markets,
        ):
            await engine.run_backtest(num_markets=1)

        # Reset
        engine.reset()

        # Verify fresh state
        results = engine.get_results()
        assert results["num_runs"] == 0


# ---------------------------------------------------------------------------
# Backtest isolation
# ---------------------------------------------------------------------------


class TestBacktestIsolation:
    """Backtest uses a backtest/ subdirectory and doesn't affect live data."""

    def test_uses_subdirectory(self, tmp_path: Path):
        engine = BacktestEngine(data_dir=tmp_path)
        assert engine._data_dir == tmp_path / "backtest"
        assert engine._data_dir.exists()

    def test_doesnt_write_to_parent(self, tmp_path: Path):
        engine = BacktestEngine(data_dir=tmp_path)

        # Write prediction
        engine._log_prediction(
            market_id="test",
            question="Q?",
            predicted_prob=0.7,
            market_prob=0.5,
        )

        # Check files exist in backtest subdir
        assert engine._predictions_file.exists()
        assert "backtest" in str(engine._predictions_file)

        # Check no portfolio.jsonl in parent
        parent_portfolio = tmp_path / "portfolio.jsonl"
        assert not parent_portfolio.exists()
