"""Unit tests for polymarket_predictor.scanner.market_scanner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from polymarket_predictor.scanner.market_scanner import (
    MarketScanner,
    _classify_category,
    _compute_niche_score,
    _get_yes_price,
)
from polymarket_predictor.scrapers.polymarket import Market

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def _make_market(
    *,
    id: str = "test_1",
    question: str = "Will X happen?",
    slug: str = "will-x-happen",
    yes_price: float = 0.5,
    no_price: float = 0.5,
    volume: float = 50000.0,
    category: str = "",
    active: bool = True,
    closed: bool = False,
    end_date: datetime | None = None,
    resolution: str | None = None,
) -> Market:
    return Market(
        id=id,
        question=question,
        slug=slug,
        outcomes=[
            {"name": "Yes", "price": yes_price},
            {"name": "No", "price": no_price},
        ],
        volume=volume,
        category=category,
        active=active,
        closed=closed,
        created_at=NOW - timedelta(days=30),
        end_date=end_date,
        resolution=resolution,
    )


@pytest.fixture
def expiring_markets():
    """Markets with various end dates relative to now."""
    return [
        _make_market(id="exp_1h", slug="exp-1h", end_date=NOW + timedelta(hours=1), volume=5000, yes_price=0.6),
        _make_market(id="exp_3d", slug="exp-3d", end_date=NOW + timedelta(days=3), volume=20000, yes_price=0.45),
        _make_market(id="exp_10d", slug="exp-10d", end_date=NOW + timedelta(days=10), volume=30000, yes_price=0.7),
        _make_market(id="exp_past", slug="exp-past", end_date=NOW - timedelta(days=1), volume=10000, yes_price=0.9),
        _make_market(id="no_end", slug="no-end", end_date=None, volume=15000, yes_price=0.5),
    ]


@pytest.fixture
def categorized_markets():
    return [
        _make_market(id="pol", question="Will Trump win the election?", category=""),
        _make_market(id="crypto", question="Will bitcoin BTC exceed 100k?", category=""),
        _make_market(id="sport", question="Will the NBA championship go to Lakers?", category=""),
        _make_market(id="other", question="Will it rain tomorrow?", category="Weather"),
    ]


# ---------------------------------------------------------------------------
# _get_yes_price
# ---------------------------------------------------------------------------

class TestGetYesPrice:
    def test_standard_outcomes(self):
        mkt = _make_market(yes_price=0.72)
        assert _get_yes_price(mkt) == 0.72

    def test_up_outcome(self):
        mkt = Market(
            id="up_1", question="BTC up?", slug="btc-up",
            outcomes=[{"name": "Up", "price": 0.55}, {"name": "Down", "price": 0.45}],
            volume=1000, category="", active=True, closed=False,
            created_at=None, end_date=None,
        )
        assert _get_yes_price(mkt) == 0.55

    def test_no_yes_outcome(self):
        mkt = Market(
            id="none_1", question="A or B?", slug="a-or-b",
            outcomes=[{"name": "A", "price": 0.6}, {"name": "B", "price": 0.4}],
            volume=1000, category="", active=True, closed=False,
            created_at=None, end_date=None,
        )
        assert _get_yes_price(mkt) is None

    def test_empty_outcomes(self):
        mkt = Market(
            id="empty", question="?", slug="empty",
            outcomes=[], volume=0, category="", active=True, closed=False,
            created_at=None, end_date=None,
        )
        assert _get_yes_price(mkt) is None


# ---------------------------------------------------------------------------
# _compute_niche_score
# ---------------------------------------------------------------------------

class TestComputeNicheScore:
    def test_niche_category_boosts_score(self):
        mkt = _make_market(question="Will the FDA approve this drug?", volume=3000)
        score = _compute_niche_score(mkt, "science")
        assert score >= 0.3  # niche category + niche keyword + low volume

    def test_efficient_category_reduces_score(self):
        mkt = _make_market(question="Will bitcoin go up?", volume=600000)
        score = _compute_niche_score(mkt, "crypto")
        # efficient category (-0.2) + high volume (-0.1) = should be low
        assert score <= 0.1

    def test_low_volume_boosts_score(self):
        mkt = _make_market(question="Generic question", volume=2000)
        score = _compute_niche_score(mkt, "other")
        # Low volume (+0.2)
        assert score >= 0.2

    def test_medium_volume(self):
        mkt = _make_market(question="Generic question", volume=15000)
        score = _compute_niche_score(mkt, "other")
        assert score >= 0.1

    def test_niche_keywords_boost_score(self):
        mkt = _make_market(question="Will there be a ceasefire treaty?", volume=10000)
        score = _compute_niche_score(mkt, "world")
        # niche category (+0.3) + keywords "ceasefire" and "treaty" (+0.3)
        assert score >= 0.5

    def test_score_clamped_to_0_1(self):
        mkt = _make_market(question="Normal question", volume=50000)
        score = _compute_niche_score(mkt, "other")
        assert 0.0 <= score <= 1.0

    def test_high_volume_efficient_category(self):
        """Maximum efficiency: crypto + high volume should be near zero."""
        mkt = _make_market(question="Simple crypto question", volume=1000000)
        score = _compute_niche_score(mkt, "crypto")
        assert score == 0.0  # -0.2 + -0.1 clamped to 0


# ---------------------------------------------------------------------------
# _classify_category
# ---------------------------------------------------------------------------

class TestClassifyCategory:
    def test_politics(self):
        mkt = _make_market(question="Will Trump win the election?")
        assert _classify_category(mkt) == "politics"

    def test_crypto(self):
        mkt = _make_market(question="Will ethereum reach 5000?")
        assert _classify_category(mkt) == "crypto"

    def test_sports(self):
        mkt = _make_market(question="NBA playoffs winner?")
        assert _classify_category(mkt) == "sports"

    def test_falls_back_to_market_category(self):
        mkt = _make_market(question="How tall is that tower?", category="CustomCat")
        assert _classify_category(mkt) == "CustomCat"

    def test_falls_back_to_other(self):
        mkt = _make_market(question="How tall is that tower?", category="")
        assert _classify_category(mkt) == "other"

    def test_uses_category_field_for_matching(self):
        """Keywords in the category field also match."""
        mkt = _make_market(question="Who wins?", category="basketball")
        assert _classify_category(mkt) == "sports"


# ---------------------------------------------------------------------------
# MarketScanner.scan_expiring
# ---------------------------------------------------------------------------

class TestScanExpiring:
    @pytest.mark.asyncio
    async def test_scan_expiring_filters_by_date(self, expiring_markets):
        scanner = MarketScanner()

        with patch.object(
            scanner._scraper, "get_active_markets",
            new_callable=AsyncMock, return_value=expiring_markets,
        ), patch.object(
            scanner._scraper, "get_high_frequency_markets",
            new_callable=AsyncMock, return_value=[],
        ):
            results = await scanner.scan_expiring(days_ahead=7, min_volume=0)

        slugs = [m.slug for m in results]
        # exp_1h and exp_3d are within 7 days
        assert "exp-1h" in slugs
        assert "exp-3d" in slugs
        # exp_10d is beyond 7 days
        assert "exp-10d" not in slugs
        # exp_past is in the past
        assert "exp-past" not in slugs
        # no_end has no end_date
        assert "no-end" not in slugs
        await scanner.close()

    @pytest.mark.asyncio
    async def test_scan_expiring_sorted_by_date(self, expiring_markets):
        scanner = MarketScanner()

        with patch.object(
            scanner._scraper, "get_active_markets",
            new_callable=AsyncMock, return_value=expiring_markets,
        ), patch.object(
            scanner._scraper, "get_high_frequency_markets",
            new_callable=AsyncMock, return_value=[],
        ):
            results = await scanner.scan_expiring(days_ahead=7, min_volume=0)

        # Should be sorted soonest first
        if len(results) >= 2:
            assert results[0].end_date <= results[1].end_date
        await scanner.close()

    @pytest.mark.asyncio
    async def test_scan_expiring_min_volume(self, expiring_markets):
        scanner = MarketScanner()

        with patch.object(
            scanner._scraper, "get_active_markets",
            new_callable=AsyncMock, return_value=expiring_markets,
        ), patch.object(
            scanner._scraper, "get_high_frequency_markets",
            new_callable=AsyncMock, return_value=[],
        ):
            results = await scanner.scan_expiring(days_ahead=7, min_volume=10000)

        # exp_1h has volume=5000, below threshold
        slugs = [m.slug for m in results]
        assert "exp-1h" not in slugs
        # exp_3d has volume=20000, above threshold
        assert "exp-3d" in slugs
        await scanner.close()

    @pytest.mark.asyncio
    async def test_scan_expiring_no_markets(self):
        scanner = MarketScanner()

        with patch.object(
            scanner._scraper, "get_active_markets",
            new_callable=AsyncMock, return_value=[],
        ), patch.object(
            scanner._scraper, "get_high_frequency_markets",
            new_callable=AsyncMock, return_value=[],
        ):
            results = await scanner.scan_expiring(days_ahead=7, min_volume=0)

        assert results == []
        await scanner.close()

    @pytest.mark.asyncio
    async def test_scan_expiring_includes_hf_markets(self):
        """High-frequency markets are merged into the scan pool."""
        scanner = MarketScanner()
        hf = _make_market(id="hf_1", slug="hf-btc", end_date=NOW + timedelta(hours=2), volume=5000)

        with patch.object(
            scanner._scraper, "get_active_markets",
            new_callable=AsyncMock, return_value=[],
        ), patch.object(
            scanner._scraper, "get_high_frequency_markets",
            new_callable=AsyncMock, return_value=[hf],
        ):
            results = await scanner.scan_expiring(days_ahead=7, min_volume=0)

        assert any(m.slug == "hf-btc" for m in results)
        await scanner.close()


# ---------------------------------------------------------------------------
# MarketScanner.scan_interesting
# ---------------------------------------------------------------------------

class TestScanInteresting:
    @pytest.mark.asyncio
    async def test_filters_by_odds_range(self):
        scanner = MarketScanner()
        markets = [
            _make_market(id="low", slug="low", yes_price=0.05, end_date=NOW + timedelta(days=1), volume=5000),
            _make_market(id="mid", slug="mid", yes_price=0.50, end_date=NOW + timedelta(days=1), volume=5000),
            _make_market(id="high", slug="high", yes_price=0.95, end_date=NOW + timedelta(days=1), volume=5000),
        ]

        with patch.object(scanner, "scan_expiring", new_callable=AsyncMock, return_value=markets):
            results = await scanner.scan_interesting(
                days_ahead=7, min_volume=0, odds_range=(0.15, 0.85)
            )

        slugs = [m.slug for m in results]
        assert "mid" in slugs
        assert "low" not in slugs
        assert "high" not in slugs
        await scanner.close()

    @pytest.mark.asyncio
    async def test_niche_scoring_affects_order(self):
        scanner = MarketScanner()
        niche = _make_market(
            id="niche", slug="niche",
            question="Will the FDA approve gene therapy?",
            yes_price=0.50, volume=3000,
            end_date=NOW + timedelta(days=1),
        )
        mainstream = _make_market(
            id="main", slug="main",
            question="Will bitcoin go up?",
            yes_price=0.50, volume=600000,
            end_date=NOW + timedelta(days=1),
        )

        with patch.object(scanner, "scan_expiring", new_callable=AsyncMock, return_value=[niche, mainstream]):
            results = await scanner.scan_interesting(days_ahead=7, min_volume=0)

        assert len(results) == 2
        # Niche market should rank higher
        assert results[0].slug == "niche"
        await scanner.close()

    @pytest.mark.asyncio
    async def test_no_yes_outcome_excluded(self):
        """Markets without a Yes/Up outcome are excluded."""
        scanner = MarketScanner()
        mkt = Market(
            id="ab", question="A or B?", slug="a-or-b",
            outcomes=[{"name": "A", "price": 0.5}, {"name": "B", "price": 0.5}],
            volume=10000, category="", active=True, closed=False,
            created_at=None, end_date=NOW + timedelta(days=1),
        )

        with patch.object(scanner, "scan_expiring", new_callable=AsyncMock, return_value=[mkt]):
            results = await scanner.scan_interesting(days_ahead=7, min_volume=0)

        assert results == []
        await scanner.close()


# ---------------------------------------------------------------------------
# MarketScanner.categorize_markets
# ---------------------------------------------------------------------------

class TestCategorizeMarkets:
    def test_categorize_markets(self, categorized_markets):
        scanner = MarketScanner()
        grouped = scanner.categorize_markets(categorized_markets)

        assert "politics" in grouped
        assert "crypto" in grouped
        assert "sports" in grouped
        assert any(m.id == "pol" for m in grouped["politics"])
        assert any(m.id == "crypto" for m in grouped["crypto"])
        assert any(m.id == "sport" for m in grouped["sports"])

    def test_categorize_empty_list(self):
        scanner = MarketScanner()
        grouped = scanner.categorize_markets([])
        assert grouped == {}

    def test_other_category(self):
        scanner = MarketScanner()
        mkt = _make_market(question="How tall is that tower?", category="")
        grouped = scanner.categorize_markets([mkt])
        assert "other" in grouped


# ---------------------------------------------------------------------------
# MarketScanner.scan_and_predict
# ---------------------------------------------------------------------------

class TestScanAndPredict:
    @pytest.mark.asyncio
    async def test_scan_and_predict_success(self):
        scanner = MarketScanner()
        mkt = _make_market(
            id="pred_1", slug="pred-1",
            yes_price=0.50,
            end_date=NOW + timedelta(days=1),
        )

        api_response = MagicMock()
        api_response.status_code = 200
        api_response.json.return_value = {"prediction": 0.70}
        api_response.raise_for_status = MagicMock()

        with patch.object(
            scanner, "scan_interesting",
            new_callable=AsyncMock, return_value=[mkt],
        ), patch("httpx.AsyncClient") as MockClient:
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=api_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            results = await scanner.scan_and_predict(
                days_ahead=3, min_volume=0, max_markets=5
            )

        assert len(results) == 1
        r = results[0]
        assert r["market"] == mkt
        assert r["prediction"] == 0.70
        assert r["edge"] == 0.20
        assert r["signal"] == "strong"
        await scanner.close()

    @pytest.mark.asyncio
    async def test_scan_and_predict_edge_signals(self):
        """Verify edge -> signal mapping."""
        scanner = MarketScanner()

        async def _run_with_prediction(pred_value: float, yes_price: float = 0.5):
            mkt = _make_market(id="sig", slug="sig", yes_price=yes_price, end_date=NOW + timedelta(days=1))

            api_response = MagicMock()
            api_response.json.return_value = {"prediction": pred_value}
            api_response.raise_for_status = MagicMock()

            with patch.object(
                scanner, "scan_interesting",
                new_callable=AsyncMock, return_value=[mkt],
            ), patch("httpx.AsyncClient") as MockClient:
                mock_instance = AsyncMock()
                mock_instance.post = AsyncMock(return_value=api_response)
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_instance

                results = await scanner.scan_and_predict(days_ahead=3, min_volume=0)
            return results[0] if results else None

        # strong: edge >= 0.15
        r = await _run_with_prediction(0.70, 0.50)
        assert r["signal"] == "strong"

        # moderate: 0.08 <= edge < 0.15
        r = await _run_with_prediction(0.60, 0.50)
        assert r["signal"] == "moderate"

        # weak: 0.03 <= edge < 0.08
        r = await _run_with_prediction(0.55, 0.50)
        assert r["signal"] == "weak"

        # noise: edge < 0.03
        r = await _run_with_prediction(0.51, 0.50)
        assert r["signal"] == "noise"

        await scanner.close()

    @pytest.mark.asyncio
    async def test_scan_and_predict_no_markets(self):
        scanner = MarketScanner()

        with patch.object(
            scanner, "scan_interesting",
            new_callable=AsyncMock, return_value=[],
        ):
            results = await scanner.scan_and_predict()

        assert results == []
        await scanner.close()

    @pytest.mark.asyncio
    async def test_scan_and_predict_api_error_skips(self):
        """If the prediction API fails, that market is skipped."""
        scanner = MarketScanner()
        mkt = _make_market(id="fail", slug="fail", yes_price=0.5, end_date=NOW + timedelta(days=1))

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            scanner, "scan_interesting",
            new_callable=AsyncMock, return_value=[mkt],
        ), patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                side_effect=httpx.HTTPStatusError("Server Error", request=mock_request, response=mock_response)
            )
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            results = await scanner.scan_and_predict(days_ahead=3, min_volume=0)

        assert results == []
        await scanner.close()

    @pytest.mark.asyncio
    async def test_scan_and_predict_respects_max_markets(self):
        scanner = MarketScanner()
        markets = [
            _make_market(id=f"m{i}", slug=f"m{i}", yes_price=0.5, end_date=NOW + timedelta(days=1))
            for i in range(20)
        ]

        api_response = MagicMock()
        api_response.json.return_value = {"prediction": 0.7}
        api_response.raise_for_status = MagicMock()

        with patch.object(
            scanner, "scan_interesting",
            new_callable=AsyncMock, return_value=markets,
        ), patch("httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=api_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            results = await scanner.scan_and_predict(max_markets=3)

        assert len(results) == 3
        await scanner.close()
