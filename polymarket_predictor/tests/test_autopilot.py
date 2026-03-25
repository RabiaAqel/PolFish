"""Tests for polymarket_predictor.autopilot.engine."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polymarket_predictor.autopilot.engine import (
    AutopilotConfig,
    AutopilotEngine,
    _yes_price,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_market_obj(
    slug: str = "btc-above-70k",
    question: str = "Will BTC be above 70k?",
    market_id: str = "m1",
    yes_price: float = 0.65,
    category: str = "Crypto",
    end_date: datetime | None = None,
) -> MagicMock:
    """Create a mock Market object matching the scraper's Market dataclass."""
    m = MagicMock()
    m.id = market_id
    m.slug = slug
    m.question = question
    m.category = category
    m.end_date = end_date
    m.outcomes = [
        {"name": "Yes", "price": yes_price},
        {"name": "No", "price": round(1 - yes_price, 2)},
    ]
    return m


def _make_position(
    slug: str = "btc-above-70k",
    market_id: str = "m1",
    side: str = "YES",
    mode: str = "quick",
    edge: float = 0.05,
) -> MagicMock:
    pos = MagicMock()
    pos.slug = slug
    pos.market_id = market_id
    pos.side = side
    pos.mode = mode
    pos.edge = edge
    return pos


# ---------------------------------------------------------------------------
# AutopilotConfig
# ---------------------------------------------------------------------------


class TestAutopilotConfigDefaults:
    """Default values are correctly set."""

    def test_defaults(self):
        cfg = AutopilotConfig()
        assert cfg.max_deep_per_cycle == 3
        assert cfg.max_cost_per_cycle == 15.0
        assert cfg.min_edge_for_deep == 0.05
        assert cfg.min_edge_for_bet == 0.03
        assert cfg.cycle_interval_hours == 6
        assert cfg.niche_focus is True
        assert cfg.quick_research is False
        assert cfg.max_markets_to_scan == 50
        assert cfg.cost_per_deep == 4.0


class TestAutopilotConfigRoundtrip:
    """to_dict / from_dict roundtrip preserves all fields."""

    def test_roundtrip(self):
        cfg = AutopilotConfig(max_deep_per_cycle=5, min_edge_for_bet=0.07)
        d = cfg.to_dict()
        restored = AutopilotConfig.from_dict(d)
        assert restored.max_deep_per_cycle == 5
        assert restored.min_edge_for_bet == 0.07
        assert restored.cycle_interval_hours == cfg.cycle_interval_hours


class TestAutopilotConfigSaveLoad:
    """save / load from disk."""

    def test_save_and_load(self, tmp_path: Path):
        cfg = AutopilotConfig(max_deep_per_cycle=7, min_edge_for_deep=0.10)
        path = tmp_path / "cfg.json"
        cfg.save(path)

        loaded = AutopilotConfig.load(path)
        assert loaded.max_deep_per_cycle == 7
        assert loaded.min_edge_for_deep == 0.10

    def test_load_missing_file_returns_defaults(self, tmp_path: Path):
        path = tmp_path / "nonexistent.json"
        loaded = AutopilotConfig.load(path)
        assert loaded.max_deep_per_cycle == 3  # default


class TestAutopilotConfigPartialUpdate:
    """Partial update preserves other fields."""

    def test_partial_update(self):
        cfg = AutopilotConfig()
        d = cfg.to_dict()
        d["max_deep_per_cycle"] = 10
        updated = AutopilotConfig.from_dict(d)
        assert updated.max_deep_per_cycle == 10
        assert updated.min_edge_for_bet == 0.03  # unchanged default


# ---------------------------------------------------------------------------
# AutopilotEngine initialisation
# ---------------------------------------------------------------------------


class TestAutopilotEngineInit:
    """Engine creates with default config or loads from disk."""

    def test_creates_with_default_config(self, tmp_path: Path):
        portfolio = MagicMock()
        ledger = MagicMock()

        with patch("polymarket_predictor.autopilot.engine.DATA_DIR", tmp_path):
            engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)

        cfg = engine.get_config()
        assert cfg["max_deep_per_cycle"] == 3

    def test_loads_existing_config(self, tmp_path: Path):
        # Write a custom config
        config_path = tmp_path / "autopilot_config.json"
        config_path.write_text(json.dumps({"max_deep_per_cycle": 8}))

        portfolio = MagicMock()
        ledger = MagicMock()

        engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)

        cfg = engine.get_config()
        assert cfg["max_deep_per_cycle"] == 8


# ---------------------------------------------------------------------------
# run_cycle_quick_only
# ---------------------------------------------------------------------------


class TestRunCycleQuickOnly:
    """Quick-only cycle flow: scan -> predict -> bet -> resolve -> optimize."""

    @pytest.mark.asyncio
    async def test_full_quick_flow(self, tmp_path: Path):
        portfolio = MagicMock()
        portfolio.balance = 10000.0
        portfolio.total_value = 10000.0
        portfolio.get_open_positions.return_value = []
        portfolio.get_resolved_positions.return_value = []
        portfolio.get_performance.return_value = {
            "total_bets": 0,
            "win_rate": 0,
            "total_pnl": 0,
        }

        bet_record = MagicMock()
        bet_record.bet_id = "bet-001"
        portfolio.place_bet.return_value = bet_record

        ledger = MagicMock()
        ledger.log.return_value = MagicMock()

        markets = [
            _make_market_obj(slug="m1", yes_price=0.50, market_id="id1"),
            _make_market_obj(slug="m2", yes_price=0.30, market_id="id2"),
        ]

        scanner_mock = AsyncMock()
        scanner_mock.scan_interesting.return_value = markets

        with (
            patch("polymarket_predictor.autopilot.engine.push_log"),
            patch("polymarket_predictor.autopilot.engine.MarketScanner") as ScannerCls,
            patch("polymarket_predictor.autopilot.engine.BetSizer") as BetSizerCls,
            patch(
                "polymarket_predictor.resolver.resolver.MarketResolver"
            ) as ResolverCls,
        ):
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scanner_mock
            ctx.__aexit__.return_value = False
            ScannerCls.return_value = ctx

            BetSizerCls.size_bet.return_value = {
                "amount": 50.0,
                "side": "YES",
                "kelly_fraction": 0.02,
                "reasoning": "Test bet",
            }

            # Mock resolver
            resolver_instance = AsyncMock()
            resolver_instance.check_resolutions.return_value = []
            ResolverCls.return_value = resolver_instance

            engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)
            # Force config for predictable test
            engine._config.min_edge_for_bet = 0.0  # accept all edges
            engine._config.max_deep_per_cycle = 10

            summary = await engine.run_cycle_quick_only()

        assert "cycle_id" in summary
        assert "phases" in summary
        assert summary["phases"]["scan"]["markets_found"] == 2


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    """Phase 5 (bet) deduplication logic."""

    def test_same_slug_same_side_skip_quick(self, tmp_path: Path):
        """Same slug, same side in quick mode -> skip."""
        portfolio = MagicMock()
        portfolio.balance = 10000.0
        portfolio.get_open_positions.return_value = [
            _make_position(slug="m1", side="YES", mode="quick"),
        ]
        portfolio.get_performance.return_value = {"total_bets": 0, "win_rate": 0, "total_pnl": 0}

        ledger = MagicMock()
        ledger.log.return_value = MagicMock()

        engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)

        # Candidate predicts YES (prediction > yes_price)
        confirmed = [{
            "slug": "m1",
            "question": "Will it happen?",
            "yes_price": 0.40,
            "quick_prediction": 0.60,
            "edge": 0.20,
        }]

        with patch("polymarket_predictor.autopilot.engine.push_log"):
            bets = engine._phase_bet("cycle-1", engine._config, confirmed, [])

        assert len(bets) == 0  # skipped

    def test_same_slug_different_side_skip_quick(self, tmp_path: Path):
        """Same slug, different side in quick mode -> still skip (random noise)."""
        portfolio = MagicMock()
        portfolio.balance = 10000.0
        portfolio.get_open_positions.return_value = [
            _make_position(slug="m1", side="NO", mode="quick"),
        ]
        portfolio.get_performance.return_value = {"total_bets": 0, "win_rate": 0, "total_pnl": 0}

        ledger = MagicMock()
        ledger.log.return_value = MagicMock()

        engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)

        # Candidate predicts YES (prediction > yes_price) but existing is NO quick
        confirmed = [{
            "slug": "m1",
            "question": "Q?",
            "yes_price": 0.40,
            "quick_prediction": 0.60,
            "edge": 0.20,
        }]

        with patch("polymarket_predictor.autopilot.engine.push_log"):
            bets = engine._phase_bet("cycle-1", engine._config, confirmed, [])

        # Quick mode skips ANY existing position
        assert len(bets) == 0

    def test_new_slug_allowed(self, tmp_path: Path):
        """New slug with no existing position -> allowed."""
        portfolio = MagicMock()
        portfolio.balance = 10000.0
        portfolio.get_open_positions.return_value = []
        portfolio.get_performance.return_value = {"total_bets": 0, "win_rate": 0, "total_pnl": 0}

        bet_record = MagicMock()
        bet_record.bet_id = "bet-new"
        portfolio.place_bet.return_value = bet_record

        ledger = MagicMock()
        ledger.log.return_value = MagicMock()

        engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)

        confirmed = [{
            "slug": "new-market",
            "question": "New Q?",
            "yes_price": 0.40,
            "quick_prediction": 0.60,
            "edge": 0.20,
        }]

        with (
            patch("polymarket_predictor.autopilot.engine.push_log"),
            patch("polymarket_predictor.autopilot.engine.BetSizer") as BetSizerCls,
        ):
            BetSizerCls.size_bet.return_value = {
                "amount": 50.0,
                "side": "YES",
                "kelly_fraction": 0.02,
                "reasoning": "Good bet",
            }
            bets = engine._phase_bet("cycle-1", engine._config, confirmed, [])

        assert len(bets) == 1


# ---------------------------------------------------------------------------
# Edge threshold filtering
# ---------------------------------------------------------------------------


class TestEdgeThresholdFiltering:
    """Edge below min_edge_for_bet -> skipped; above -> passed."""

    def test_below_threshold_skipped(self, tmp_path: Path):
        portfolio = MagicMock()
        portfolio.balance = 10000.0
        portfolio.get_open_positions.return_value = []
        portfolio.get_performance.return_value = {"total_bets": 0, "win_rate": 0, "total_pnl": 0}

        ledger = MagicMock()
        ledger.log.return_value = MagicMock()

        engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)

        confirmed = [{
            "slug": "m1",
            "question": "Q?",
            "yes_price": 0.50,
            "quick_prediction": 0.50,
            "edge": 0.001,  # very small edge
        }]

        with (
            patch("polymarket_predictor.autopilot.engine.push_log"),
            patch("polymarket_predictor.autopilot.engine.BetSizer") as BetSizerCls,
        ):
            BetSizerCls.size_bet.return_value = {
                "amount": 0.0,  # sizer returns 0 for tiny edge
                "side": "YES",
                "kelly_fraction": 0.0,
                "reasoning": "Edge too small",
            }
            bets = engine._phase_bet("cycle-1", engine._config, confirmed, [])

        assert len(bets) == 0

    def test_above_threshold_placed(self, tmp_path: Path):
        portfolio = MagicMock()
        portfolio.balance = 10000.0
        portfolio.get_open_positions.return_value = []
        portfolio.get_performance.return_value = {"total_bets": 0, "win_rate": 0, "total_pnl": 0}

        bet_record = MagicMock()
        bet_record.bet_id = "bet-1"
        portfolio.place_bet.return_value = bet_record

        ledger = MagicMock()
        ledger.log.return_value = MagicMock()

        engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)

        confirmed = [{
            "slug": "m1",
            "question": "Q?",
            "yes_price": 0.40,
            "quick_prediction": 0.60,
            "edge": 0.20,
        }]

        with (
            patch("polymarket_predictor.autopilot.engine.push_log"),
            patch("polymarket_predictor.autopilot.engine.BetSizer") as BetSizerCls,
        ):
            BetSizerCls.size_bet.return_value = {
                "amount": 100.0,
                "side": "YES",
                "kelly_fraction": 0.05,
                "reasoning": "Good edge",
            }
            bets = engine._phase_bet("cycle-1", engine._config, confirmed, [])

        assert len(bets) == 1


# ---------------------------------------------------------------------------
# Budget caps
# ---------------------------------------------------------------------------


class TestBudgetCap:
    """max_deep_per_cycle and max_cost_per_cycle limit candidates."""

    def test_max_deep_per_cycle_limits(self, tmp_path: Path):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = []
        ledger = MagicMock()

        engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)
        engine._config.max_deep_per_cycle = 2
        engine._config.min_edge_for_deep = 0.0

        scored = [
            {"slug": f"m{i}", "edge": 0.10, "quick_prediction": 0.6, "yes_price": 0.5}
            for i in range(10)
        ]

        with patch("polymarket_predictor.autopilot.engine.push_log"):
            candidates = engine._phase_select_candidates("cycle-1", engine._config, scored)

        assert len(candidates) <= 2

    def test_max_cost_per_cycle_limits(self, tmp_path: Path):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = []
        ledger = MagicMock()

        engine = AutopilotEngine(portfolio, ledger, data_dir=tmp_path)
        engine._config.max_deep_per_cycle = 100  # high limit
        engine._config.max_cost_per_cycle = 8.0  # low budget
        engine._config.cost_per_deep = 4.0  # $4 each -> max 2
        engine._config.min_edge_for_deep = 0.0

        scored = [
            {"slug": f"m{i}", "edge": 0.10, "quick_prediction": 0.6, "yes_price": 0.5}
            for i in range(10)
        ]

        with patch("polymarket_predictor.autopilot.engine.push_log"):
            candidates = engine._phase_select_candidates("cycle-1", engine._config, scored)

        assert len(candidates) <= 2  # 8.0 / 4.0 = 2
