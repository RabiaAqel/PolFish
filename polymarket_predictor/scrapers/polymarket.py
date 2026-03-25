"""Fetch markets from the Polymarket Gamma and CLOB APIs.

This module provides an async scraper that retrieves active, resolved, and
individual markets from Polymarket's public APIs, returning strongly-typed
``Market`` dataclass instances suitable for downstream prediction pipelines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from polymarket_predictor.config import (
    MIN_VOLUME_THRESHOLD,
    POLYMARKET_CLOB_URL,
    POLYMARKET_GAMMA_URL,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Market:
    """Represents a single Polymarket prediction market."""

    id: str
    question: str
    slug: str
    outcomes: list[dict[str, Any]]  # [{"name": "Yes", "price": 0.65}, ...]
    volume: float
    category: str
    active: bool
    closed: bool
    created_at: datetime | None
    end_date: datetime | None
    resolution: str | None = None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert *value* to float, returning *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 string into a :class:`datetime`, or return ``None``."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _parse_market(raw: dict[str, Any], event: dict[str, Any]) -> Market:
    """Build a :class:`Market` from a raw market dict and its parent event."""

    # Outcomes ---------------------------------------------------------------
    outcome_names: list[str] = []
    outcome_prices: list[str] = []

    if raw.get("outcomes"):
        # The API returns outcomes as a JSON-encoded string or a list.
        outcomes_raw = raw["outcomes"]
        if isinstance(outcomes_raw, str):
            import json

            try:
                outcome_names = json.loads(outcomes_raw)
            except json.JSONDecodeError:
                outcome_names = [o.strip() for o in outcomes_raw.split(",")]
        elif isinstance(outcomes_raw, list):
            outcome_names = outcomes_raw

    if raw.get("outcomePrices"):
        prices_raw = raw["outcomePrices"]
        if isinstance(prices_raw, str):
            import json

            try:
                outcome_prices = json.loads(prices_raw)
            except json.JSONDecodeError:
                outcome_prices = [p.strip() for p in prices_raw.split(",")]
        elif isinstance(prices_raw, list):
            outcome_prices = prices_raw

    outcomes: list[dict[str, Any]] = []
    for idx, name in enumerate(outcome_names):
        price = _safe_float(outcome_prices[idx]) if idx < len(outcome_prices) else 0.0
        outcomes.append({"name": name, "price": round(price, 4)})

    # Resolution (only meaningful for closed markets) ------------------------
    resolution: str | None = raw.get("resolution") or event.get("resolution")

    # Volume — prefer volumeNum (numeric) over volume (sometimes 0 or string)
    volume = _safe_float(
        raw.get("volumeNum") or raw.get("volume") or event.get("volume", 0)
    )

    # Category — extracted from event tags
    category = ""
    tags = event.get("tags") or []
    if isinstance(tags, list):
        # Pick first meaningful tag (skip meta tags like "Recurring", "Hide From New")
        skip_tags = {"recurring", "hide-from-new", "5m", "15m", "1h"}
        for tag in tags:
            tag_slug = tag.get("slug", "") if isinstance(tag, dict) else ""
            if tag_slug and tag_slug.lower() not in skip_tags:
                category = tag.get("label", tag_slug) if isinstance(tag, dict) else str(tag)
                break

    return Market(
        id=str(raw.get("id", "")),
        question=raw.get("question") or event.get("title", ""),
        slug=raw.get("slug") or event.get("slug", ""),
        outcomes=outcomes,
        volume=volume,
        category=category,
        active=bool(raw.get("active", event.get("active", False))),
        closed=bool(raw.get("closed", event.get("closed", False))),
        created_at=_safe_datetime(raw.get("createdAt") or event.get("createdAt")),
        end_date=_safe_datetime(raw.get("endDate") or event.get("endDate")),
        resolution=resolution,
    )


def _parse_event(event_dict: dict[str, Any]) -> list[Market]:
    """Convert a raw event dict from the Gamma API into a list of :class:`Market`.

    Each Polymarket event can contain multiple markets (e.g. binary outcome
    markets). This helper iterates over the ``markets`` key and produces one
    :class:`Market` per entry.
    """
    markets_raw: list[dict[str, Any]] = event_dict.get("markets", [])
    if not markets_raw:
        logger.debug("Event %s has no nested markets – skipping", event_dict.get("id"))
        return []

    parsed: list[Market] = []
    for mkt in markets_raw:
        try:
            parsed.append(_parse_market(mkt, event_dict))
        except Exception:
            logger.warning(
                "Failed to parse market %s in event %s",
                mkt.get("id", "?"),
                event_dict.get("id", "?"),
                exc_info=True,
            )
    return parsed


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------


class PolymarketScraper:
    """Async client for the Polymarket Gamma and CLOB APIs."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=POLYMARKET_GAMMA_URL,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Accept": "application/json"},
        )

    # -- Public API ----------------------------------------------------------

    async def get_active_markets(
        self,
        limit: int = 50,
        min_volume: float = MIN_VOLUME_THRESHOLD,
    ) -> list[Market]:
        """Return active, open markets whose volume exceeds *min_volume*.

        Markets are fetched via ``GET /events`` with pagination support so that
        the caller receives up to *limit* **events** worth of markets.
        """
        all_markets: list[Market] = []
        offset = 0
        # Fetch more events than requested to account for volume filtering
        fetch_limit = min(limit * 3, 100)
        max_pages = 3  # Safety cap to prevent infinite pagination

        for _page in range(max_pages):
            params: dict[str, Any] = {
                "active": "true",
                "closed": "false",
                "limit": fetch_limit,
                "offset": offset,
                "order": "volume24hr",
                "ascending": "false",
            }
            events = await self._fetch_events(params)
            if not events:
                break

            for event in events:
                for market in _parse_event(event):
                    if market.volume >= min_volume:
                        all_markets.append(market)

            # Stop if we have enough or exhausted results
            if len(all_markets) >= limit or len(events) < fetch_limit:
                break

            offset += fetch_limit

        # Trim to requested limit
        all_markets = all_markets[:limit]

        logger.info(
            "Fetched %d active markets (min_volume=%.0f)", len(all_markets), min_volume
        )
        return all_markets

    async def get_high_frequency_markets(self, limit: int = 50) -> list[Market]:
        """Fetch high-frequency crypto markets (4hour, daily).

        These use slug patterns like ``btc-updown-4h-{epoch}`` where the epoch
        aligns to UTC block boundaries. They are NOT returned by ``/events``.
        """
        import time as _time

        coins = ["btc", "eth", "sol", "xrp", "doge", "bnb", "hype"]
        intervals = {
            "5m": 300,      # 5 minutes
            "15m": 900,     # 15 minutes
            "4h": 14400,    # 4 hours
        }

        now_ts = int(_time.time())
        all_markets: list[Market] = []
        seen_slugs: set[str] = set()

        for interval_label, block_size in intervals.items():
            # Next block start (round up to next boundary)
            current_block = ((now_ts // block_size) + 1) * block_size

            # Fewer blocks for shorter intervals to limit API calls
            # 5m: next 3 blocks (15 min), 15m: next 4 blocks (1h), 4h: next 6 blocks (24h)
            max_blocks = 3 if block_size <= 300 else (4 if block_size <= 900 else 6)
            for block_offset in range(max_blocks):
                block_ts = current_block + (block_offset * block_size)

                for coin in coins:
                    slug = f"{coin}-updown-{interval_label}-{block_ts}"
                    if slug in seen_slugs:
                        continue

                    try:
                        resp = await self._client.get(
                            "/markets",
                            params={"slug": slug},
                        )
                        resp.raise_for_status()
                        data = resp.json()

                        for mkt_data in data:
                            actual_slug = mkt_data.get("slug", "")
                            if actual_slug in seen_slugs:
                                continue
                            seen_slugs.add(actual_slug)

                            try:
                                market = _parse_market(mkt_data, mkt_data)
                                if market and market.active and not market.closed:
                                    all_markets.append(market)
                            except Exception:
                                continue

                    except Exception:
                        continue  # Market doesn't exist for this coin/window

                    if len(all_markets) >= limit:
                        break
                if len(all_markets) >= limit:
                    break
            if len(all_markets) >= limit:
                break

        logger.info("Fetched %d high-frequency markets", len(all_markets))
        return all_markets

    async def get_resolved_markets(self, limit: int = 100) -> list[Market]:
        """Return closed/resolved markets suitable for backtesting."""
        all_markets: list[Market] = []
        offset = 0

        while True:
            params: dict[str, Any] = {
                "active": "false",
                "closed": "true",
                "limit": limit,
                "offset": offset,
            }
            events = await self._fetch_events(params)
            if not events:
                break

            for event in events:
                all_markets.extend(_parse_event(event))

            if len(events) < limit:
                break

            offset += limit

        logger.info("Fetched %d resolved markets", len(all_markets))
        return all_markets

    async def get_market_by_slug(self, slug: str) -> Market | None:
        """Fetch a single market identified by its URL *slug*.

        Tries the events endpoint first (event-level slug), then falls back
        to the markets endpoint (market-level slug).  Returns ``None`` when
        no matching market is found.
        """
        try:
            # Try 1: event-level lookup
            resp = await self._client.get("/events", params={"slug": slug})
            resp.raise_for_status()
            events: list[dict[str, Any]] = resp.json()

            for event in events:
                markets = _parse_event(event)
                if markets:
                    for mkt in markets:
                        if mkt.slug == slug:
                            return mkt
                    return markets[0]

            # Try 2: market-level lookup (slug may be a market slug, not event)
            resp = await self._client.get("/markets", params={"slug": slug})
            resp.raise_for_status()
            markets_raw: list[dict[str, Any]] = resp.json()

            for raw in markets_raw:
                # Build a minimal event wrapper so _parse_market works
                try:
                    return _parse_market(raw, raw)
                except Exception:
                    continue

        except httpx.HTTPStatusError as exc:
            logger.error("HTTP %s fetching market slug=%s", exc.response.status_code, slug)
        except httpx.RequestError as exc:
            logger.error("Request error fetching market slug=%s: %s", slug, exc)

        return None

    async def get_price_history(
        self,
        token_id: str,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        """Fetch price history for a token from the CLOB API.

        Parameters
        ----------
        token_id:
            The condition/token ID of the market outcome.
        interval:
            Candle interval, e.g. ``"1d"``, ``"1h"``, ``"1m"``.

        Returns
        -------
        list[dict]
            A list of dicts with ``t`` (timestamp) and ``p`` (price) keys.
        """
        try:
            resp = await self._client.get(
                f"{POLYMARKET_CLOB_URL}/prices-history",
                params={"market": token_id, "interval": interval},
            )
            resp.raise_for_status()
            data = resp.json()

            # The CLOB API returns {"history": [...]} or a bare list.
            if isinstance(data, dict):
                return data.get("history", [])
            if isinstance(data, list):
                return data
            return []

        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP %s fetching price history for token=%s",
                exc.response.status_code,
                token_id,
            )
        except httpx.RequestError as exc:
            logger.error("Request error fetching price history for token=%s: %s", token_id, exc)

        return []

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        await self._client.aclose()
        logger.debug("PolymarketScraper HTTP client closed")

    # -- Context manager support ---------------------------------------------

    async def __aenter__(self) -> PolymarketScraper:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- Internals -----------------------------------------------------------

    async def _fetch_events(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Perform a ``GET /events`` request and return the JSON payload."""
        try:
            resp = await self._client.get("/events", params=params)
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "events" in data:
                return data["events"]

            logger.warning("Unexpected response shape from /events: %s", type(data))
            return []

        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP %s from /events (params=%s)", exc.response.status_code, params
            )
        except httpx.RequestError as exc:
            logger.error("Request error from /events: %s", exc)

        return []
