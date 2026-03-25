"""Unit tests for polymarket_predictor.scrapers.polymarket."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from polymarket_predictor.scrapers.polymarket import (
    Market,
    PolymarketScraper,
    _parse_market,
    _safe_datetime,
    _safe_float,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_market_complete():
    """A complete raw market dict as returned by the Gamma API."""
    return {
        "id": "0x_abc123",
        "question": "Will BTC exceed $100k by June?",
        "slug": "btc-100k-june",
        "outcomes": json.dumps(["Yes", "No"]),
        "outcomePrices": json.dumps(["0.62", "0.38"]),
        "volumeNum": 120000,
        "volume": "50000",
        "active": True,
        "closed": False,
        "createdAt": "2025-01-15T10:00:00Z",
        "endDate": "2025-06-30T23:59:59Z",
        "resolution": None,
    }


@pytest.fixture
def raw_event():
    """A raw event dict wrapping a market."""
    return {
        "id": "evt_1",
        "title": "BTC Price Predictions",
        "slug": "btc-predictions",
        "tags": [
            {"slug": "crypto", "label": "Crypto"},
            {"slug": "recurring", "label": "Recurring"},
        ],
        "volume": "200000",
        "active": True,
        "closed": False,
        "createdAt": "2025-01-01T00:00:00Z",
        "endDate": "2025-06-30T23:59:59Z",
        "resolution": "Yes",
    }


@pytest.fixture
def gamma_event_with_markets(raw_market_complete, raw_event):
    """An event containing a nested markets list."""
    event = dict(raw_event)
    event["markets"] = [raw_market_complete]
    return event


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------

class TestSafeFloat:
    def test_valid_int(self):
        assert _safe_float(42) == 42.0

    def test_valid_float(self):
        assert _safe_float(3.14) == 3.14

    def test_valid_string(self):
        assert _safe_float("0.65") == 0.65

    def test_none_returns_default(self):
        assert _safe_float(None) == 0.0

    def test_empty_string_returns_default(self):
        assert _safe_float("") == 0.0

    def test_abc_returns_default(self):
        assert _safe_float("abc") == 0.0

    def test_nan_returns_nan(self):
        result = _safe_float(float("nan"))
        assert math.isnan(result)

    def test_custom_default(self):
        assert _safe_float(None, default=-1.0) == -1.0


# ---------------------------------------------------------------------------
# _safe_datetime
# ---------------------------------------------------------------------------

class TestSafeDatetime:
    def test_valid_iso(self):
        result = _safe_datetime("2025-06-15T12:00:00Z")
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 6

    def test_valid_iso_with_offset(self):
        result = _safe_datetime("2025-06-15T12:00:00+00:00")
        assert isinstance(result, datetime)

    def test_none_returns_none(self):
        assert _safe_datetime(None) is None

    def test_empty_string_returns_none(self):
        assert _safe_datetime("") is None

    def test_malformed_string_returns_none(self):
        assert _safe_datetime("not-a-date") is None

    def test_integer_timestamp_returns_none(self):
        # int is not an ISO string but str(int) is also not a valid ISO date
        assert _safe_datetime(12345) is None


# ---------------------------------------------------------------------------
# _parse_market
# ---------------------------------------------------------------------------

class TestParseMarket:
    def test_complete_market(self, raw_market_complete, raw_event):
        mkt = _parse_market(raw_market_complete, raw_event)
        assert isinstance(mkt, Market)
        assert mkt.id == "0x_abc123"
        assert mkt.question == "Will BTC exceed $100k by June?"
        assert mkt.slug == "btc-100k-june"
        assert mkt.active is True
        assert mkt.closed is False
        assert len(mkt.outcomes) == 2
        assert mkt.outcomes[0]["name"] == "Yes"
        assert mkt.outcomes[0]["price"] == 0.62
        assert mkt.outcomes[1]["name"] == "No"
        assert mkt.outcomes[1]["price"] == 0.38

    def test_missing_optional_fields(self, raw_event):
        """Market with minimal fields still parses without error."""
        raw = {"id": "min_1"}
        mkt = _parse_market(raw, raw_event)
        assert mkt.id == "min_1"
        assert mkt.outcomes == []
        assert mkt.resolution == "Yes"  # falls back to event resolution

    def test_outcomes_as_list(self, raw_event):
        """Outcomes provided as a Python list instead of JSON string."""
        raw = {
            "id": "list_1",
            "outcomes": ["Up", "Down"],
            "outcomePrices": ["0.55", "0.45"],
        }
        mkt = _parse_market(raw, raw_event)
        assert len(mkt.outcomes) == 2
        assert mkt.outcomes[0]["name"] == "Up"
        assert mkt.outcomes[0]["price"] == 0.55

    def test_outcome_length_mismatch(self, raw_event):
        """3 outcome names but only 2 prices -- third should get 0.0."""
        raw = {
            "id": "mismatch_1",
            "outcomes": json.dumps(["Yes", "No", "Maybe"]),
            "outcomePrices": json.dumps(["0.5", "0.3"]),
        }
        mkt = _parse_market(raw, raw_event)
        assert len(mkt.outcomes) == 3
        assert mkt.outcomes[2]["name"] == "Maybe"
        assert mkt.outcomes[2]["price"] == 0.0

    def test_volume_prefers_volumeNum(self, raw_event):
        raw = {
            "id": "vol_1",
            "volumeNum": 99999,
            "volume": "50000",
        }
        mkt = _parse_market(raw, raw_event)
        assert mkt.volume == 99999.0

    def test_volume_falls_back_to_volume(self, raw_event):
        raw = {"id": "vol_2", "volume": "42000"}
        mkt = _parse_market(raw, raw_event)
        assert mkt.volume == 42000.0

    def test_volume_falls_back_to_event(self, raw_event):
        raw = {"id": "vol_3"}
        mkt = _parse_market(raw, raw_event)
        assert mkt.volume == 200000.0

    def test_category_from_tags(self, raw_event):
        """First non-skip tag should be used as category."""
        mkt = _parse_market({"id": "cat_1"}, raw_event)
        assert mkt.category == "Crypto"

    def test_category_skips_meta_tags(self):
        """Skip tags like 'recurring', '5m', etc."""
        event = {
            "tags": [
                {"slug": "recurring", "label": "Recurring"},
                {"slug": "5m", "label": "5m"},
                {"slug": "politics", "label": "Politics"},
            ],
        }
        mkt = _parse_market({"id": "cat_2"}, event)
        assert mkt.category == "Politics"

    def test_resolution_from_market(self, raw_event):
        raw = {"id": "res_1", "resolution": "No"}
        mkt = _parse_market(raw, raw_event)
        assert mkt.resolution == "No"

    def test_resolution_falls_back_to_event(self, raw_event):
        raw = {"id": "res_2"}
        mkt = _parse_market(raw, raw_event)
        assert mkt.resolution == "Yes"

    def test_question_falls_back_to_event_title(self, raw_event):
        raw = {"id": "q_1"}
        mkt = _parse_market(raw, raw_event)
        assert mkt.question == "BTC Price Predictions"


# ---------------------------------------------------------------------------
# PolymarketScraper
# ---------------------------------------------------------------------------

class TestPolymarketScraper:
    @pytest.mark.asyncio
    async def test_get_market_by_slug(self, gamma_event_with_markets):
        scraper = PolymarketScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [gamma_event_with_markets]
        mock_resp.raise_for_status = MagicMock()

        with patch.object(scraper._client, "get", new_callable=AsyncMock, return_value=mock_resp):
            market = await scraper.get_market_by_slug("btc-100k-june")

        assert market is not None
        assert isinstance(market, Market)
        assert market.slug == "btc-100k-june"
        await scraper.close()

    @pytest.mark.asyncio
    async def test_get_market_by_slug_not_found(self):
        scraper = PolymarketScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()

        with patch.object(scraper._client, "get", new_callable=AsyncMock, return_value=mock_resp):
            market = await scraper.get_market_by_slug("nonexistent-slug")

        assert market is None
        await scraper.close()

    @pytest.mark.asyncio
    async def test_get_active_markets(self, gamma_event_with_markets):
        scraper = PolymarketScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [gamma_event_with_markets]
        mock_resp.raise_for_status = MagicMock()

        with patch.object(scraper._client, "get", new_callable=AsyncMock, return_value=mock_resp):
            markets = await scraper.get_active_markets(limit=10, min_volume=0)

        assert len(markets) >= 1
        assert all(isinstance(m, Market) for m in markets)
        await scraper.close()

    @pytest.mark.asyncio
    async def test_get_active_markets_min_volume_filter(self, raw_event):
        """Markets below min_volume are excluded."""
        low_vol_market = {
            "id": "low_vol",
            "question": "Low volume question",
            "slug": "low-vol",
            "outcomes": json.dumps(["Yes", "No"]),
            "outcomePrices": json.dumps(["0.5", "0.5"]),
            "volumeNum": 50,
            "active": True,
            "closed": False,
        }
        high_vol_market = {
            "id": "high_vol",
            "question": "High volume question",
            "slug": "high-vol",
            "outcomes": json.dumps(["Yes", "No"]),
            "outcomePrices": json.dumps(["0.5", "0.5"]),
            "volumeNum": 100000,
            "active": True,
            "closed": False,
        }
        event = dict(raw_event)
        event["markets"] = [low_vol_market, high_vol_market]

        scraper = PolymarketScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [event]
        mock_resp.raise_for_status = MagicMock()

        with patch.object(scraper._client, "get", new_callable=AsyncMock, return_value=mock_resp):
            markets = await scraper.get_active_markets(limit=10, min_volume=1000)

        assert len(markets) == 1
        assert markets[0].id == "high_vol"
        await scraper.close()

    @pytest.mark.asyncio
    async def test_get_active_markets_pagination(self, raw_event):
        """Verify multiple pages are fetched until results are exhausted."""
        scraper = PolymarketScraper()

        # Build enough events to fill fetch_limit so pagination continues.
        # get_active_markets uses fetch_limit = min(limit * 3, 100) = 100 for limit=50
        # It continues pagination when len(events) >= fetch_limit.
        def _make_events(count):
            events = []
            for i in range(count):
                mkt = {
                    "id": f"m{i}", "slug": f"m{i}", "volumeNum": 50000,
                    "outcomes": json.dumps(["Yes", "No"]),
                    "outcomePrices": json.dumps(["0.5", "0.5"]),
                    "active": True, "closed": False,
                }
                ev = dict(raw_event)
                ev["id"] = f"evt_{i}"
                ev["markets"] = [mkt]
                events.append(ev)
            return events

        call_count = 0

        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if call_count == 1:
                # Return full page (fetch_limit events) to trigger pagination
                resp.json.return_value = _make_events(100)
            elif call_count == 2:
                # Second page returns fewer -> stops
                resp.json.return_value = _make_events(5)
            else:
                resp.json.return_value = []
            return resp

        with patch.object(scraper._client, "get", side_effect=mock_get):
            markets = await scraper.get_active_markets(limit=200, min_volume=0)

        assert call_count >= 2
        # Page 1 returned 100, page 2 returned 5 (fewer than fetch_limit -> stop)
        assert len(markets) == 105
        await scraper.close()

    @pytest.mark.asyncio
    async def test_get_high_frequency_markets(self):
        """Verify slug pattern generation and market collection."""
        scraper = PolymarketScraper()

        async def mock_get(path, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            slug = kwargs.get("params", {}).get("slug", "")
            if "btc" in slug:
                resp.json.return_value = [{
                    "id": f"hf_{slug}",
                    "slug": slug,
                    "question": f"Will BTC go up? ({slug})",
                    "outcomes": ["Up", "Down"],
                    "outcomePrices": ["0.52", "0.48"],
                    "active": True,
                    "closed": False,
                    "tags": [],
                }]
            else:
                resp.json.return_value = []
            return resp

        with patch.object(scraper._client, "get", side_effect=mock_get):
            markets = await scraper.get_high_frequency_markets(limit=5)

        assert len(markets) <= 5
        assert all(isinstance(m, Market) for m in markets)
        for m in markets:
            assert "btc" in m.slug
        await scraper.close()

    @pytest.mark.asyncio
    async def test_get_resolved_markets(self, raw_event):
        closed_market = {
            "id": "closed_1",
            "question": "Did BTC hit 80k?",
            "slug": "btc-80k",
            "outcomes": json.dumps(["Yes", "No"]),
            "outcomePrices": json.dumps(["1.0", "0.0"]),
            "volumeNum": 300000,
            "active": False,
            "closed": True,
            "resolution": "Yes",
        }
        event = dict(raw_event)
        event["markets"] = [closed_market]

        scraper = PolymarketScraper()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [event]
        mock_resp.raise_for_status = MagicMock()

        with patch.object(scraper._client, "get", new_callable=AsyncMock, return_value=mock_resp):
            markets = await scraper.get_resolved_markets(limit=10)

        assert len(markets) >= 1
        assert markets[0].closed is True
        assert markets[0].resolution == "Yes"
        await scraper.close()

    @pytest.mark.asyncio
    async def test_get_price_history(self):
        scraper = PolymarketScraper()
        history_data = {
            "history": [
                {"t": 1700000000, "p": 0.55},
                {"t": 1700003600, "p": 0.58},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = history_data
        mock_resp.raise_for_status = MagicMock()

        with patch.object(scraper._client, "get", new_callable=AsyncMock, return_value=mock_resp):
            history = await scraper.get_price_history("token_abc", interval="1h")

        assert len(history) == 2
        assert history[0]["t"] == 1700000000
        assert history[1]["p"] == 0.58
        await scraper.close()

    @pytest.mark.asyncio
    async def test_get_price_history_bare_list(self):
        """CLOB API can return a bare list instead of {history: [...]}."""
        scraper = PolymarketScraper()
        bare = [{"t": 1, "p": 0.5}]
        mock_resp = MagicMock()
        mock_resp.json.return_value = bare
        mock_resp.raise_for_status = MagicMock()

        with patch.object(scraper._client, "get", new_callable=AsyncMock, return_value=mock_resp):
            history = await scraper.get_price_history("token_x")

        assert history == bare
        await scraper.close()

    @pytest.mark.asyncio
    async def test_get_price_history_http_error(self):
        scraper = PolymarketScraper()
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(
            scraper._client,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=mock_request, response=mock_response
            ),
        ):
            history = await scraper.get_price_history("bad_token")

        assert history == []
        await scraper.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        with patch.object(PolymarketScraper, "close", new_callable=AsyncMock) as mock_close:
            async with PolymarketScraper() as scraper:
                assert isinstance(scraper, PolymarketScraper)
            mock_close.assert_awaited_once()
