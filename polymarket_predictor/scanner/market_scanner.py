"""Scan Polymarket for expiring, high-value, and uncertain markets.

Provides :class:`MarketScanner`, which wraps :class:`PolymarketScraper` with
filtering and prediction-pipeline helpers so callers can quickly surface the
most actionable prediction opportunities.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from polymarket_predictor.config import DATA_DIR, MIROFISH_API_URL  # noqa: F401
from polymarket_predictor.scrapers.polymarket import Market, PolymarketScraper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category keywords used by ``categorize_markets``
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "politics": [
        "election", "president", "congress", "senate", "governor",
        "democrat", "republican", "trump", "biden", "vote", "poll",
        "political", "legislation", "parliament", "impeach",
    ],
    "crypto": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "token",
        "blockchain", "solana", "sol", "defi", "nft", "altcoin",
    ],
    "sports": [
        "nba", "nfl", "mlb", "nhl", "soccer", "football", "basketball",
        "baseball", "tennis", "golf", "ufc", "mma", "boxing", "f1",
        "championship", "playoffs", "super bowl", "world cup",
    ],
    "finance": [
        "stock", "s&p", "nasdaq", "fed", "interest rate", "inflation",
        "gdp", "recession", "ipo", "earnings", "market cap", "dow",
    ],
    "entertainment": [
        "oscar", "grammy", "emmy", "movie", "film", "tv show",
        "album", "box office", "streaming", "netflix", "disney",
    ],
    "science": [
        "climate", "nasa", "spacex", "launch", "ai", "artificial intelligence",
        "fda", "vaccine", "pandemic", "study", "research",
    ],
    "world": [
        "war", "conflict", "treaty", "sanctions", "nato", "un",
        "china", "russia", "ukraine", "eu", "trade",
    ],
}

# ---------------------------------------------------------------------------
# Niche market detection — less efficient markets with more alpha potential
# ---------------------------------------------------------------------------

# Categories where prediction markets tend to be LESS efficient
# (fewer informed traders, more noise, more room for MiroFish edge)
_NICHE_CATEGORIES = {"science", "world", "entertainment"}

# High-efficiency categories where markets are hard to beat
# (lots of informed traders, data-driven, heavily arbitraged)
_EFFICIENT_CATEGORIES = {"crypto", "finance", "sports"}

# Keywords that signal a market is niche/obscure (lower volume = less efficient)
_NICHE_KEYWORDS = [
    # Obscure politics (not mainstream US elections)
    "local election", "city council", "state legislature", "referendum",
    "recall", "primary", "special election", "runoff", "ballot measure",
    "minister", "coalition", "parliament", "opposition",
    # Geopolitics
    "ceasefire", "treaty", "sanctions", "diplomatic", "territorial",
    "annexation", "embargo", "extradition", "asylum", "refugee",
    # Science & tech
    "fda approval", "clinical trial", "launch window", "orbit",
    "artemis", "jwst", "cern", "fusion", "quantum", "gene therapy",
    "breakthrough", "peer review", "replication",
    # Regulatory & policy
    "regulation", "antitrust", "ban", "mandate", "executive order",
    "tariff", "subsidy", "compliance", "indictment", "verdict",
    "settlement", "ruling", "appeal",
    # Culture & society
    "census", "population", "migration", "protest", "strike",
    "union", "labor", "minimum wage", "housing",
    # Weather & natural events
    "hurricane", "earthquake", "wildfire", "drought", "flooding",
    "temperature record", "el nino", "la nina",
]


def _compute_niche_score(market: Market, category: str) -> float:
    """Score how 'niche' a market is (0.0 = mainstream, 1.0 = very niche).

    Higher scores indicate markets more likely to be inefficient
    and thus better targets for MiroFish predictions.
    """
    score = 0.0
    text = market.question.lower()

    # Category-based scoring
    if category in _NICHE_CATEGORIES:
        score += 0.3
    elif category in _EFFICIENT_CATEGORIES:
        score -= 0.2

    # Keyword matching
    niche_hits = sum(1 for kw in _NICHE_KEYWORDS if kw in text)
    score += min(niche_hits * 0.15, 0.4)  # cap at 0.4

    # Low volume = less efficient (more alpha potential)
    vol = getattr(market, "volume", 0) or 0
    if vol < 5000:
        score += 0.2
    elif vol < 20000:
        score += 0.1
    elif vol > 500000:
        score -= 0.1  # high volume = very efficient

    # Odds near 50/50 = most uncertain = most alpha potential
    # (markets at 10% or 90% are mostly decided already)
    # This is handled elsewhere but give a small bonus here
    return max(0.0, min(1.0, score))


def _get_yes_price(market: Market) -> float | None:
    """Extract the YES outcome price from *market*, or ``None`` if absent."""
    for outcome in market.outcomes:
        if outcome.get("name", "").lower() in ("yes", "up"):
            return outcome.get("price")
    return None


def _classify_category(market: Market) -> str:
    """Return a category label for *market* based on keyword matching.

    Falls back to the market's own ``category`` field, then ``"other"``.
    """
    text = f"{market.question} {market.category}".lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return market.category or "other"


# ---------------------------------------------------------------------------
# MarketScanner
# ---------------------------------------------------------------------------


class MarketScanner:
    """High-level scanner that discovers actionable Polymarket opportunities.

    Wraps :class:`PolymarketScraper` with expiry-based, odds-based, and
    full scan-and-predict workflows.
    """

    def __init__(self) -> None:
        self._scraper = PolymarketScraper()

    # -- Lifecycle -----------------------------------------------------------

    async def close(self) -> None:
        """Release underlying scraper resources."""
        await self._scraper.close()

    async def __aenter__(self) -> MarketScanner:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- Scanning methods ----------------------------------------------------

    async def scan_expiring(
        self,
        days_ahead: float = 7,
        min_volume: float = 1000,
    ) -> list[Market]:
        """Find active markets expiring within *days_ahead* days (supports decimals, e.g. 0.25 = 6h).

        Parameters
        ----------
        days_ahead:
            Only include markets whose ``end_date`` is within this many days
            from now.
        min_volume:
            Minimum lifetime volume (USD) required.

        Returns
        -------
        list[Market]
            Markets sorted by expiry date, soonest first.
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)

        logger.info(
            "Scanning for markets expiring before %s (min_volume=%.0f)",
            cutoff.date(),
            min_volume,
        )

        markets = await self._scraper.get_active_markets(
            limit=200,
            min_volume=min_volume,
        )

        # Also fetch high-frequency markets (5M, 15M, hourly, 4h, daily)
        try:
            hf_markets = await self._scraper.get_high_frequency_markets(limit=50)
            seen_slugs = {m.slug for m in markets}
            for hf in hf_markets:
                if hf.slug not in seen_slugs:
                    markets.append(hf)
                    seen_slugs.add(hf.slug)
            logger.info("Added %d high-frequency markets to scan pool", len(hf_markets))
        except Exception as exc:
            logger.warning("Failed to fetch high-frequency markets: %s", exc)

        expiring: list[Market] = []
        for mkt in markets:
            if mkt.end_date is None:
                continue
            if not (now < mkt.end_date <= cutoff):
                continue
            if mkt.volume < min_volume:
                continue
            expiring.append(mkt)

        expiring.sort(key=lambda m: m.end_date or cutoff)

        logger.info(
            "Found %d markets expiring within %.1f days (%.0fh)", len(expiring), days_ahead, days_ahead * 24
        )
        return expiring

    async def scan_interesting(
        self,
        days_ahead: float = 7,
        min_volume: float = 1000,
        odds_range: tuple[float, float] = (0.15, 0.85),
    ) -> list[Market]:
        """Find expiring markets whose YES odds fall within *odds_range*.

        Markets near 0 or 1 are already effectively decided and offer little
        prediction value.  This method surfaces the most uncertain -- and
        therefore most interesting -- markets.

        Parameters
        ----------
        days_ahead:
            Maximum days until expiry.
        min_volume:
            Minimum lifetime volume (USD).
        odds_range:
            ``(low, high)`` inclusive range for the YES outcome price.

        Returns
        -------
        list[Market]
            Filtered markets sorted by expiry date, soonest first.
        """
        low, high = odds_range
        expiring = await self.scan_expiring(days_ahead=days_ahead, min_volume=min_volume)

        scored: list[tuple[float, Market]] = []
        for mkt in expiring:
            yes_price = _get_yes_price(mkt)
            if yes_price is None:
                continue
            if low <= yes_price <= high:
                category = _classify_category(mkt)
                niche = _compute_niche_score(mkt, category)
                # Combined score: niche bonus + uncertainty bonus (closeness to 50%)
                uncertainty = 1.0 - abs(yes_price - 0.5) * 2  # 1.0 at 50%, 0.0 at 0%/100%
                combined = niche * 0.6 + uncertainty * 0.4
                scored.append((combined, mkt))

        # Sort by combined score (highest = most promising) then by expiry
        scored.sort(key=lambda x: x[0], reverse=True)
        interesting = [mkt for _, mkt in scored]

        logger.info(
            "Found %d interesting markets (odds %.2f-%.2f, niche-sorted) from %d expiring",
            len(interesting),
            low,
            high,
            len(expiring),
        )
        return interesting

    async def scan_and_predict(
        self,
        days_ahead: int = 3,
        min_volume: float = 500,
        max_markets: int = 10,
        mode: str = "quick",
    ) -> list[dict[str, Any]]:
        """Scan for interesting markets and run predictions via the MiroFish API.

        Parameters
        ----------
        days_ahead:
            Maximum days until expiry.
        min_volume:
            Minimum lifetime volume (USD).
        max_markets:
            Cap on the number of markets to predict (to limit API cost).
        mode:
            Prediction mode forwarded to the API (``"quick"`` or ``"full"``).

        Returns
        -------
        list[dict]
            Each dict contains: ``market``, ``prediction``, ``edge``,
            ``signal``, ``expiry``.
        """
        markets = await self.scan_interesting(
            days_ahead=days_ahead,
            min_volume=min_volume,
        )
        markets = markets[:max_markets]

        if not markets:
            logger.info("No interesting markets found -- nothing to predict")
            return []

        logger.info(
            "Running %s predictions for %d markets", mode, len(markets)
        )

        results: list[dict[str, Any]] = []
        predict_url = f"{MIROFISH_API_URL}/polymarket/predict"

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            for mkt in markets:
                result = await self._predict_market(client, predict_url, mkt, mode)
                if result is not None:
                    results.append(result)

        logger.info(
            "Completed predictions: %d/%d succeeded", len(results), len(markets)
        )
        return results

    # -- Categorization ------------------------------------------------------

    def categorize_markets(
        self,
        markets: list[Market],
    ) -> dict[str, list[Market]]:
        """Group *markets* by inferred category.

        Categories are determined by keyword matching against the market
        question and any existing category tag.  Markets that match no
        keyword set are filed under ``"other"``.

        Returns
        -------
        dict[str, list[Market]]
            Mapping of category name to list of markets.
        """
        grouped: dict[str, list[Market]] = defaultdict(list)
        for mkt in markets:
            category = _classify_category(mkt)
            grouped[category].append(mkt)

        logger.debug(
            "Categorized %d markets into %d categories",
            len(markets),
            len(grouped),
        )
        return dict(grouped)

    # -- Internal helpers ----------------------------------------------------

    async def _predict_market(
        self,
        client: httpx.AsyncClient,
        url: str,
        market: Market,
        mode: str,
    ) -> dict[str, Any] | None:
        """Call the MiroFish prediction API for a single market.

        Returns ``None`` on failure so callers can skip gracefully.
        """
        yes_price = _get_yes_price(market) or 0.0

        payload = {
            "market_id": market.id,
            "question": market.question,
            "slug": market.slug,
            "current_odds": yes_price,
            "mode": mode,
        }

        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            prediction = data.get("prediction", yes_price)
            edge = round(abs(prediction - yes_price), 4)

            signal: str
            if edge >= 0.15:
                signal = "strong"
            elif edge >= 0.08:
                signal = "moderate"
            elif edge >= 0.03:
                signal = "weak"
            else:
                signal = "noise"

            return {
                "market": market,
                "prediction": prediction,
                "edge": edge,
                "signal": signal,
                "expiry": market.end_date.isoformat() if market.end_date else None,
            }

        except httpx.HTTPStatusError as exc:
            logger.error(
                "Prediction API returned HTTP %s for market %s (%s)",
                exc.response.status_code,
                market.id,
                market.slug,
            )
        except httpx.RequestError as exc:
            logger.error(
                "Prediction API request failed for market %s: %s",
                market.id,
                exc,
            )
        except Exception:
            logger.exception(
                "Unexpected error predicting market %s", market.id
            )

        return None
