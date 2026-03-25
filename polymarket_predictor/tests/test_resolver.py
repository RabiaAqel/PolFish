"""Tests for polymarket_predictor.resolver.resolver."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polymarket_predictor.resolver.resolver import (
    CalibrationUpdater,
    MarketResolver,
    OptimizationSuggestion,
    ResolutionResult,
)
from polymarket_predictor.scrapers.polymarket import Market
from polymarket_predictor.calibrator.history import (
    PredictionRecord,
    ResolutionRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_market(
    slug: str = "test-slug",
    closed: bool = True,
    resolution: str | None = None,
    outcomes: list[dict] | None = None,
    question: str = "Will it happen?",
) -> Market:
    return Market(
        id="mkt-1",
        question=question,
        slug=slug,
        outcomes=outcomes or [],
        volume=10_000,
        category="test",
        active=not closed,
        closed=closed,
        created_at=None,
        end_date=None,
        resolution=resolution,
    )


def _make_position(market_id="mkt-1", slug="test-slug", question="Will it happen?"):
    pos = MagicMock()
    pos.market_id = market_id
    pos.slug = slug
    pos.question = question
    return pos


def _make_bet_record(pnl: float = 5.0):
    rec = MagicMock()
    rec.pnl = pnl
    return rec


# ---------------------------------------------------------------------------
# MarketResolver -- check_resolutions
# ---------------------------------------------------------------------------


class TestCheckResolutionsNoOpenPositions:
    """check_resolutions returns empty list when portfolio has no open positions."""

    @pytest.mark.asyncio
    async def test_returns_empty(self):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = []
        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)
        result = await resolver.check_resolutions()
        assert result == []


class TestCheckResolutionsMarketNotFound:
    """Market not found on Polymarket -> skipped with warning."""

    @pytest.mark.asyncio
    async def test_skips_not_found(self, caplog):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = [_make_position()]

        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = None

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            result = await resolver.check_resolutions()

        assert result == []
        assert scraper_mock.get_market_by_slug.await_count == 1


class TestCheckResolutionsMarketNotClosed:
    """Market exists but is not closed -> returns None for that market."""

    @pytest.mark.asyncio
    async def test_not_closed(self):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = [_make_position()]

        market = _make_market(closed=False)
        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = market

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            result = await resolver.check_resolutions()

        assert result == []


class TestCheckResolutionsWithResolutionString:
    """Resolution string present -> parsed to outcome_yes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "resolution_str, expected_outcome",
        [
            ("Yes", True),
            ("No", False),
            ("Up", True),
            ("Down", False),
        ],
    )
    async def test_resolution_string(self, resolution_str, expected_outcome):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = [_make_position()]
        portfolio.resolve_bet.return_value = [_make_bet_record(pnl=1.0)]

        market = _make_market(resolution=resolution_str)
        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = market

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            result = await resolver.check_resolutions()

        assert len(result) == 1
        assert result[0].outcome_yes is expected_outcome


class TestCheckResolutionsInferredFromPrices:
    """Resolution inferred from outcome prices when no resolution string."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "outcomes, expected_outcome",
        [
            # Up price=1.0, Down price=0.0 -> True
            (
                [{"name": "Up", "price": 1.0}, {"name": "Down", "price": 0.0}],
                True,
            ),
            # Up price=0.0, Down price=1.0 -> False
            (
                [{"name": "Up", "price": 0.0}, {"name": "Down", "price": 1.0}],
                False,
            ),
            # Up price=0.95 -> True (threshold 0.95)
            (
                [{"name": "Up", "price": 0.95}, {"name": "Down", "price": 0.05}],
                True,
            ),
            # Yes price=1.0 -> True
            (
                [{"name": "Yes", "price": 1.0}, {"name": "No", "price": 0.0}],
                True,
            ),
            # No price=1.0 -> False
            (
                [{"name": "No", "price": 1.0}, {"name": "Yes", "price": 0.0}],
                False,
            ),
        ],
    )
    async def test_price_inferred(self, outcomes, expected_outcome):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = [_make_position()]
        portfolio.resolve_bet.return_value = [_make_bet_record(pnl=2.0)]

        market = _make_market(outcomes=outcomes, resolution=None)
        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = market

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            result = await resolver.check_resolutions()

        assert len(result) == 1
        assert result[0].outcome_yes is expected_outcome

    @pytest.mark.asyncio
    async def test_ambiguous_prices_not_resolved(self):
        """Up price=0.5, Down price=0.5 -> unclear, not resolved."""
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = [_make_position()]

        outcomes = [{"name": "Up", "price": 0.5}, {"name": "Down", "price": 0.5}]
        market = _make_market(outcomes=outcomes, resolution=None)
        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = market

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            result = await resolver.check_resolutions()

        assert result == []

    @pytest.mark.asyncio
    async def test_price_below_threshold_not_resolved(self):
        """Up price=0.94 -> below 0.95 threshold, not resolved."""
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = [_make_position()]

        outcomes = [{"name": "Up", "price": 0.94}, {"name": "Down", "price": 0.06}]
        market = _make_market(outcomes=outcomes, resolution=None)
        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = market

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            result = await resolver.check_resolutions()

        assert result == []


class TestCheckResolutionsUpdatesPortfolio:
    """check_resolutions calls resolve_bet on the portfolio."""

    @pytest.mark.asyncio
    async def test_resolve_bet_called(self):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = [_make_position()]
        portfolio.resolve_bet.return_value = [_make_bet_record(pnl=3.0)]

        market = _make_market(resolution="Yes")
        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = market

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            result = await resolver.check_resolutions()

        portfolio.resolve_bet.assert_called_once_with("mkt-1", True)
        assert result[0].pnl == 3.0


class TestCheckResolutionsRecordsHistory:
    """check_resolutions calls history.log_resolution."""

    @pytest.mark.asyncio
    async def test_log_resolution_called(self):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = [_make_position()]
        portfolio.resolve_bet.return_value = [_make_bet_record(pnl=1.0)]

        market = _make_market(resolution="No")
        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = market

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            await resolver.check_resolutions()

        history.log_resolution.assert_called_once()
        record = history.log_resolution.call_args[0][0]
        assert record.outcome == "No"
        assert record.outcome_binary == 0


# ---------------------------------------------------------------------------
# MarketResolver -- resolve_single
# ---------------------------------------------------------------------------


class TestResolveSingle:
    """resolve_single resolves a single market by id and slug."""

    @pytest.mark.asyncio
    async def test_returns_result_for_resolved_market(self):
        portfolio = MagicMock()
        portfolio.resolve_bet.return_value = [_make_bet_record(pnl=5.0)]

        market = _make_market(resolution="Yes")
        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = market

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            result = await resolver.resolve_single("mkt-1", "test-slug")

        assert result is not None
        assert result.outcome_yes is True
        assert result.pnl == 5.0

    @pytest.mark.asyncio
    async def test_returns_none_for_open_market(self):
        portfolio = MagicMock()

        market = _make_market(closed=False)
        scraper_mock = AsyncMock()
        scraper_mock.get_market_by_slug.return_value = market

        calibrator = MagicMock()
        history = MagicMock()

        resolver = MarketResolver(portfolio, calibrator, history)

        with patch(
            "polymarket_predictor.resolver.resolver.PolymarketScraper"
        ) as ScraperCls:
            ctx = AsyncMock()
            ctx.__aenter__.return_value = scraper_mock
            ctx.__aexit__.return_value = False
            ScraperCls.return_value = ctx

            result = await resolver.resolve_single("mkt-1", "test-slug")

        assert result is None


# ---------------------------------------------------------------------------
# MarketResolver -- get_resolution_summary
# ---------------------------------------------------------------------------


class TestGetResolutionSummary:
    """get_resolution_summary returns correct counts, accuracy, pnl by category."""

    def test_correct_summary(self):
        portfolio = MagicMock()
        portfolio.get_open_positions.return_value = [_make_position()]

        # Mock history
        history = MagicMock()

        res1 = MagicMock()
        res1.market_id = "m1"
        res1.question = "Q1"
        res1.outcome = "Yes"
        res1.resolved_at = "2024-01-01"

        res2 = MagicMock()
        res2.market_id = "m2"
        res2.question = "Q2"
        res2.outcome = "No"
        res2.resolved_at = "2024-01-02"

        history.get_resolutions.return_value = [res1, res2]

        pred1 = MagicMock()
        pred1.market_id = "m1"
        pred1.predicted_prob = 0.7
        pred1.market_prob = 0.5
        pred1.category = "Crypto"

        pred2 = MagicMock()
        pred2.market_id = "m2"
        pred2.predicted_prob = 0.3
        pred2.market_prob = 0.5
        pred2.category = "Politics"

        history.get_predictions.return_value = [pred1, pred2]

        # matched records
        match_res1 = MagicMock()
        match_res1.outcome_binary = 1

        match_res2 = MagicMock()
        match_res2.outcome_binary = 0

        history.get_matched_records.return_value = [
            (pred1, match_res1),
            (pred2, match_res2),
        ]

        calibrator = MagicMock()
        resolver = MarketResolver(portfolio, calibrator, history)

        summary = resolver.get_resolution_summary()

        assert summary["total_resolved"] == 2
        assert summary["total_open"] == 1
        assert len(summary["recent_resolutions"]) == 2
        assert "accuracy_by_category" in summary
        assert "pnl_by_category" in summary
        # Both predictions are correct: pred1=0.7>=0.5 => Yes, actual Yes;
        # pred2=0.3<0.5 => No, actual No
        assert summary["accuracy_by_category"]["Crypto"]["correct"] == 1
        assert summary["accuracy_by_category"]["Politics"]["correct"] == 1


# ---------------------------------------------------------------------------
# CalibrationUpdater
# ---------------------------------------------------------------------------


class TestCalibrationUpdaterUpdate:
    """update with sufficient data builds calibration."""

    def test_update_returns_stats(self):
        calibrator = MagicMock()
        report = MagicMock()
        report.brier_score = 0.2
        report.calibration_error = 0.05
        report.total_predictions = 50
        report.bins = []
        calibrator.build_calibration.return_value = report

        history = MagicMock()

        updater = CalibrationUpdater(calibrator, history)
        stats = updater.update()

        assert stats["brier_score"] == 0.2
        assert stats["calibration_error"] == 0.05
        assert stats["total_predictions"] == 50
        assert stats["bins"] == []
        calibrator.build_calibration.assert_called_once()

    def test_update_with_insufficient_data(self):
        """update with insufficient data returns empty bins."""
        calibrator = MagicMock()
        report = MagicMock()
        report.brier_score = 0.0
        report.calibration_error = 0.0
        report.total_predictions = 3
        report.bins = []
        calibrator.build_calibration.return_value = report

        history = MagicMock()

        updater = CalibrationUpdater(calibrator, history)
        stats = updater.update()

        assert stats["total_predictions"] == 3
        assert stats["bins"] == []


class TestCalibrationUpdaterGetOptimizationSuggestions:
    """get_optimization_suggestions returns actionable suggestions."""

    def _make_matched(self, n, predicted_probs, outcomes, categories=None):
        """Build a list of (pred, res) tuples for testing."""
        matched = []
        for i in range(n):
            pred = MagicMock()
            pred.predicted_prob = predicted_probs[i]
            pred.market_prob = 0.5
            pred.category = categories[i] if categories else "unknown"

            res = MagicMock()
            res.outcome_binary = outcomes[i]
            matched.append((pred, res))
        return matched

    def test_returns_list(self):
        calibrator = MagicMock()
        report = MagicMock()
        report.brier_score = 0.1
        calibrator.build_calibration.return_value = report

        history = MagicMock()
        # 15 matched records, all correct predictions
        matched = self._make_matched(
            15,
            [0.7] * 15,
            [1] * 15,
        )
        history.get_matched_records.return_value = matched

        updater = CalibrationUpdater(calibrator, history)
        suggestions = updater.get_optimization_suggestions()
        assert isinstance(suggestions, list)

    def test_over_prediction_detected(self):
        """When mean error > 0.05, suggests lowering probability."""
        calibrator = MagicMock()
        report = MagicMock()
        report.brier_score = 0.1
        calibrator.build_calibration.return_value = report

        history = MagicMock()
        # Predictions all at 0.8, but outcomes all 0 -> mean_error = 0.8
        matched = self._make_matched(
            15,
            [0.8] * 15,
            [0] * 15,
        )
        history.get_matched_records.return_value = matched

        updater = CalibrationUpdater(calibrator, history)
        suggestions = updater.get_optimization_suggestions()

        bias_suggestions = [s for s in suggestions if s["parameter"] == "probability_bias"]
        assert len(bias_suggestions) >= 1
        assert bias_suggestions[0]["suggested_value"] < 0  # negative bias to lower

    def test_poor_category_detected(self):
        """Category with accuracy < 40% triggers a suggestion."""
        calibrator = MagicMock()
        report = MagicMock()
        report.brier_score = 0.1
        calibrator.build_calibration.return_value = report

        history = MagicMock()
        # 10 predictions in "sports", all wrong (pred=0.7, outcome=0)
        # 5 predictions in "crypto", all correct (pred=0.7, outcome=1)
        probs = [0.7] * 10 + [0.7] * 5
        outcomes = [0] * 10 + [1] * 5
        cats = ["sports"] * 10 + ["crypto"] * 5
        matched = self._make_matched(15, probs, outcomes, cats)
        history.get_matched_records.return_value = matched

        updater = CalibrationUpdater(calibrator, history)
        suggestions = updater.get_optimization_suggestions()

        cat_suggestions = [
            s for s in suggestions if s["parameter"] == "category_exclusion"
        ]
        assert len(cat_suggestions) >= 1
        assert "sports" in cat_suggestions[0]["suggested_value"]

    def test_insufficient_data_returns_empty(self):
        """With fewer than 10 matched records, returns empty list."""
        calibrator = MagicMock()
        history = MagicMock()
        history.get_matched_records.return_value = self._make_matched(
            5, [0.5] * 5, [1] * 5
        )

        updater = CalibrationUpdater(calibrator, history)
        suggestions = updater.get_optimization_suggestions()
        assert suggestions == []
