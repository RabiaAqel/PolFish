"""News article search for Polymarket prediction seeds.

Uses duckduckgo-search for finding recent news, then optionally
fetches full article text via httpx.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

_MAX_ARTICLE_TEXT = 4000


@dataclass
class Article:
    """A single news article."""

    title: str
    source: str
    date: str
    url: str
    text: str


@dataclass
class DeepResearchResult:
    """Aggregated research from multiple source types."""

    articles: list[Article] = field(default_factory=list)
    wikipedia_context: str = ""
    entity_articles: dict[str, list[Article]] = field(default_factory=dict)
    total_words: int = 0
    sources_count: int = 0
    price_history: list = field(default_factory=list)
    price_summary: str = ""
    domain_data: str = ""


class _TagStripper(HTMLParser):
    """Minimal HTML-to-text converter."""

    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip = False
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._pieces.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._pieces.append(data)

    def get_text(self) -> str:
        return "".join(self._pieces)


def _strip_tags(html: str) -> str:
    stripper = _TagStripper()
    stripper.feed(html)
    return stripper.get_text()


def _extract_article_text(html: str) -> str:
    """Extract main body text from HTML page."""
    # Try <article> tag first
    match = re.search(r"<article[^>]*>(.*?)</article>", html, re.DOTALL | re.IGNORECASE)
    if match:
        text = _strip_tags(match.group(1))
    else:
        # Fallback: collect all <p> tags
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE)
        text = "\n".join(_strip_tags(p) for p in paragraphs)

    text = re.sub(r"\s+", " ", text).strip()
    return text[:_MAX_ARTICLE_TEXT]


class NewsAggregator:
    """Search for news articles using DuckDuckGo."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            timeout=5.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        )

    async def search_articles(self, query: str, max_results: int = 5) -> list[Article]:
        """Search for recent news articles about a topic."""
        import asyncio

        try:
            from duckduckgo_search import DDGS

            raw = []
            with DDGS() as ddgs:
                for r in ddgs.news(query, max_results=max_results):
                    raw.append(r)

            # Fetch all articles in parallel with a global 8s timeout
            async def _build_article(r: dict) -> Article:
                title = r.get("title", "")
                url = r.get("url", "")
                source = r.get("source", "")
                date = r.get("date", "")
                body = r.get("body", "")
                full_text = await self._fetch_article(url) if url else ""
                text = full_text if len(full_text) > len(body) else body
                return Article(title=title, source=source, date=date, url=url, text=text[:_MAX_ARTICLE_TEXT])

            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*[_build_article(r) for r in raw], return_exceptions=True),
                    timeout=8.0,
                )
                articles = [r for r in results if isinstance(r, Article)]
            except asyncio.TimeoutError:
                logger.warning("Article fetch timed out, using DDG snippets only")
                articles = [
                    Article(
                        title=r.get("title", ""),
                        source=r.get("source", ""),
                        date=r.get("date", ""),
                        url=r.get("url", ""),
                        text=r.get("body", "")[:_MAX_ARTICLE_TEXT],
                    )
                    for r in raw
                ]

            logger.info(f"Found {len(articles)} articles for: {query[:50]}")
            return articles

        except Exception as e:
            logger.error(f"News search failed: {e}")
            return []

    async def _fetch_article(self, url: str) -> str:
        """Fetch and extract article text from a URL."""
        try:
            resp = await self._http.get(url)
            resp.raise_for_status()
            return _extract_article_text(resp.text)
        except Exception:
            return ""

    async def search_articles_deep(
        self, query: str, max_results: int = 10, market_slug: str = ""
    ) -> DeepResearchResult:
        """Deep research combining news, general web, Wikipedia, and entity-specific searches.

        Returns a :class:`DeepResearchResult` targeting 8,000+ words across
        diverse source types.

        Parameters
        ----------
        query:
            The market question or search query.
        max_results:
            Max articles to return.
        market_slug:
            Optional Polymarket slug — used to fetch price history.
        """
        import asyncio

        result = DeepResearchResult()

        # --- 1. DuckDuckGo News (5 articles) ---
        news_articles = await self.search_articles(query, max_results=5)
        result.articles.extend(news_articles)

        # --- 2. DuckDuckGo General (3 more results) ---
        try:
            general_articles = await self._search_general(query, max_results=3)
            result.articles.extend(general_articles)
        except Exception as e:
            logger.warning("General web search failed: %s", e)

        # --- 3. Wikipedia context ---
        try:
            result.wikipedia_context = await self._fetch_wikipedia_context(query)
        except Exception as e:
            logger.warning("Wikipedia fetch failed: %s", e)

        # --- 4. Entity-specific searches ---
        entities = self._extract_entities(query)
        for entity in entities:
            try:
                entity_arts = await self.search_articles(entity, max_results=2)
                if entity_arts:
                    result.entity_articles[entity] = entity_arts
            except Exception as e:
                logger.warning("Entity search failed for '%s': %s", entity, e)

        # --- 5. Polymarket price history ---
        if market_slug:
            try:
                history, summary = await self._fetch_price_history(market_slug)
                result.price_history = history
                result.price_summary = summary
            except Exception as e:
                logger.warning("Price history fetch failed: %s", e)

        # --- 6. Category-specific data ---
        category = self._detect_category(query)
        domain_parts: list[str] = []

        if category == "crypto":
            # Extract crypto symbol from query
            symbol = self._extract_crypto_symbol(query)
            if symbol:
                try:
                    crypto_data = await self._fetch_crypto_data(symbol)
                    if crypto_data:
                        domain_parts.append(crypto_data)
                except Exception as e:
                    logger.warning("Crypto data fetch failed: %s", e)

        elif category == "commodity":
            commodity = self._extract_commodity(query)
            ctx = self._get_commodity_context(commodity)
            if ctx:
                domain_parts.append(ctx)

        elif category in ("politics", "geopolitics"):
            ctx = self._get_politics_context(query)
            if ctx:
                domain_parts.append(ctx)

        result.domain_data = "\n\n".join(domain_parts)

        # --- Compute totals ---
        all_texts = [a.text for a in result.articles]
        all_texts.append(result.wikipedia_context)
        all_texts.append(result.price_summary)
        all_texts.append(result.domain_data)
        for arts in result.entity_articles.values():
            all_texts.extend(a.text for a in arts)

        combined = " ".join(all_texts)
        result.total_words = len(combined.split())
        result.sources_count = (
            len(result.articles)
            + (1 if result.wikipedia_context else 0)
            + sum(len(arts) for arts in result.entity_articles.values())
            + (1 if result.price_history else 0)
            + (1 if result.domain_data else 0)
        )

        logger.info(
            "Deep research: %d words from %d sources for: %s",
            result.total_words,
            result.sources_count,
            query[:50],
        )
        return result

    async def _search_general(self, query: str, max_results: int = 3) -> list[Article]:
        """Search DuckDuckGo general web (not news-only) for broader context."""
        import asyncio

        try:
            from duckduckgo_search import DDGS

            raw = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    raw.append(r)

            async def _build(r: dict) -> Article:
                title = r.get("title", "")
                url = r.get("href", r.get("url", ""))
                body = r.get("body", r.get("text", ""))
                full_text = await self._fetch_article(url) if url else ""
                text = full_text if len(full_text) > len(body) else body
                return Article(
                    title=title,
                    source="web",
                    date="",
                    url=url,
                    text=text[:_MAX_ARTICLE_TEXT],
                )

            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*[_build(r) for r in raw], return_exceptions=True),
                    timeout=8.0,
                )
                return [r for r in results if isinstance(r, Article)]
            except asyncio.TimeoutError:
                logger.warning("General search fetch timed out, using snippets")
                return [
                    Article(
                        title=r.get("title", ""),
                        source="web",
                        date="",
                        url=r.get("href", ""),
                        text=r.get("body", "")[:_MAX_ARTICLE_TEXT],
                    )
                    for r in raw
                ]
        except Exception as e:
            logger.error("General search failed: %s", e)
            return []

    async def _fetch_wikipedia_context(self, query: str) -> str:
        """Fetch the Wikipedia summary for the most relevant topic in the query.

        Uses the Wikipedia search API to find the best matching article, then
        fetches its summary via the REST API.
        """
        # First extract entities to use as search terms
        entities = self._extract_entities(query)

        # Build search attempts: entities first (most specific), then broader terms
        attempts = list(entities[:3])
        # Also try key noun phrases from the query
        topic = re.sub(r"[^\w\s]", "", query).strip()
        words = topic.split()
        if len(words) >= 3:
            attempts.append(" ".join(words[:3]))
        if words:
            attempts.append(words[0])

        for attempt in attempts:
            try:
                # Use Wikipedia's search API to find the best article title
                search_resp = await self._http.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": attempt,
                        "srlimit": "1",
                        "format": "json",
                    },
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "PolFish/1.0 (prediction research; polfish@example.com)",
                    },
                )
                if search_resp.status_code != 200:
                    continue
                search_data = search_resp.json()
                results = search_data.get("query", {}).get("search", [])
                if not results:
                    continue

                title = results[0]["title"]

                # Now fetch the summary for this specific title
                encoded = quote(title.replace(" ", "_"))
                resp = await self._http.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}",
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "PolFish/1.0 (prediction research; polfish@example.com)",
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    extract = data.get("extract", "")
                    if extract and len(extract) > 100:
                        return f"[Wikipedia: {data.get('title', title)}]\n{extract[:2000]}"
            except Exception:
                continue
        return ""

    @staticmethod
    def _extract_entities(query: str) -> list[str]:
        """Extract key entities/topics from a prediction question.

        Uses simple heuristics: capitalized words, known patterns (countries,
        currencies, names), and noun-phrase-like sequences.
        """
        # Remove common question words and stop words
        stop_words = {
            "will", "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "shall", "should",
            "may", "might", "can", "could", "would", "this", "that", "these",
            "those", "it", "its", "by", "for", "from", "with", "at", "on", "in",
            "to", "of", "and", "or", "but", "if", "as", "than", "before", "after",
            "above", "below", "between", "during", "through", "about", "into",
            "over", "under", "again", "further", "then", "once", "there", "when",
            "where", "why", "how", "what", "which", "who", "whom", "each", "every",
            "all", "both", "few", "more", "most", "other", "some", "such", "no",
            "not", "only", "own", "same", "so", "very", "just", "because",
            "yes", "no", "up", "down", "end", "reach", "exceed", "drop", "rise",
            "fall", "hit", "go", "get", "make", "take", "will", "new", "next",
        }

        # Find capitalized sequences (potential proper nouns / entities)
        # e.g. "United States", "Elon Musk", "Bitcoin", "Federal Reserve"
        cap_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
        entities = []
        for match in cap_pattern.finditer(query):
            entity = match.group(1)
            # Strip leading stop words (e.g., "Will Bitcoin" -> "Bitcoin")
            words = entity.split()
            while words and words[0].lower() in stop_words:
                words = words[1:]
            if not words:
                continue
            entity = " ".join(words)
            # Skip if all remaining words are stop words
            if not all(w.lower() in stop_words for w in words):
                entities.append(entity)

        # Also grab any ALL-CAPS tokens (acronyms like BTC, ETH, US, NATO)
        acro_pattern = re.compile(r"\b([A-Z]{2,})\b")
        for match in acro_pattern.finditer(query):
            entities.append(match.group(1))

        # Also extract numbers with units (e.g., "$100,000", "100K")
        # These are useful as search context but not standalone entities

        # Deduplicate while preserving order, limit to 5 entities
        seen = set()
        unique = []
        for e in entities:
            if e.lower() not in seen and e.lower() not in stop_words:
                seen.add(e.lower())
                unique.append(e)
        return unique[:5]

    # ------------------------------------------------------------------
    # Price history
    # ------------------------------------------------------------------

    async def _fetch_price_history(self, market_slug: str) -> tuple[list, str]:
        """Fetch Polymarket price history and generate readable summary."""
        try:
            from polymarket_predictor.scrapers.polymarket import PolymarketScraper

            async with PolymarketScraper() as scraper:
                # First get the market to find the token ID
                market = await scraper.get_market_by_slug(market_slug)
                if not market:
                    return [], ""

                # Fetch the raw market data to get clobTokenIds
                # Try markets endpoint which returns the raw data with token IDs
                resp = await scraper._client.get(
                    "/markets", params={"slug": market_slug}
                )
                if resp.status_code != 200:
                    return [], ""

                raw_markets = resp.json()
                token_id = ""
                for raw in raw_markets if isinstance(raw_markets, list) else [raw_markets]:
                    # clobTokenIds is a JSON string like '["token1","token2"]'
                    clob_ids = raw.get("clobTokenIds")
                    if clob_ids:
                        import json

                        if isinstance(clob_ids, str):
                            try:
                                ids = json.loads(clob_ids)
                                token_id = ids[0] if ids else ""
                            except (json.JSONDecodeError, IndexError):
                                token_id = clob_ids
                        elif isinstance(clob_ids, list) and clob_ids:
                            token_id = clob_ids[0]
                    # Fallback: conditionId
                    if not token_id:
                        token_id = raw.get("conditionId", "")
                    if token_id:
                        break

                if not token_id:
                    return [], ""

                # Use 1h interval for 7-day granularity
                history = await scraper.get_price_history(token_id, interval="1h")

                if not history:
                    # Try daily interval as fallback
                    history = await scraper.get_price_history(token_id, interval="1d")

                if not history:
                    return [], ""

                # Generate summary
                summary_parts = []
                if len(history) >= 2:
                    first_price = history[0].get("p", 0.5)
                    last_price = history[-1].get("p", 0.5)
                    change = last_price - first_price
                    direction = "up" if change > 0 else "down"
                    summary_parts.append(
                        f"Price moved from {first_price:.1%} to {last_price:.1%} "
                        f"({direction} {abs(change):.1%}) over the observation period."
                    )

                    # Find high/low
                    prices = [h.get("p", 0.5) for h in history]
                    high = max(prices)
                    low = min(prices)
                    summary_parts.append(f"Range: {low:.1%} to {high:.1%}.")

                    # Recent trend (last 20% of data)
                    recent_start = len(prices) - max(1, len(prices) // 5)
                    recent_prices = prices[recent_start:]
                    if len(recent_prices) >= 2:
                        recent_change = recent_prices[-1] - recent_prices[0]
                        if abs(recent_change) > 0.02:
                            recent_dir = "bullish" if recent_change > 0 else "bearish"
                            summary_parts.append(
                                f"Recent trend is {recent_dir} ({recent_change:+.1%})."
                            )

                return history, " ".join(summary_parts)
        except Exception as e:
            logger.warning("Failed to fetch price history: %s", e)
            return [], ""

    # ------------------------------------------------------------------
    # Category detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_category(question: str) -> str:
        """Detect market category from question text."""
        q = question.lower()
        if any(
            kw in q
            for kw in [
                "bitcoin", "btc", "ethereum", "eth", "solana", "crypto",
                "token", "doge", "bnb", "xrp",
            ]
        ):
            return "crypto"
        if any(
            kw in q
            for kw in ["crude oil", "oil price", "natural gas", "gold price", "commodity"]
        ):
            return "commodity"
        if any(
            kw in q
            for kw in [
                "election", "vote", "president", "congress", "parliament",
                "party", "senator",
            ]
        ):
            return "politics"
        if any(
            kw in q
            for kw in ["ceasefire", "war", "military", "invasion", "sanctions", "diplomat"]
        ):
            return "geopolitics"
        return "general"

    # ------------------------------------------------------------------
    # Category-specific data sources
    # ------------------------------------------------------------------

    async def _fetch_crypto_data(self, symbol: str) -> str:
        """Fetch crypto price data from CoinGecko (free, no auth)."""
        symbol_map = {
            "btc": "bitcoin", "bitcoin": "bitcoin",
            "eth": "ethereum", "ethereum": "ethereum",
            "sol": "solana", "solana": "solana",
            "xrp": "ripple",
            "doge": "dogecoin", "dogecoin": "dogecoin",
            "bnb": "binancecoin",
        }

        coin_id = symbol_map.get(symbol.lower(), symbol.lower())

        try:
            resp = await self._http.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": coin_id,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                },
            )
            if resp.status_code == 200:
                data = resp.json().get(coin_id, {})
                price = data.get("usd", 0)
                change_24h = data.get("usd_24h_change", 0)
                market_cap = data.get("usd_market_cap", 0)
                volume = data.get("usd_24h_vol", 0)

                return (
                    f"Current {symbol.upper()} Price Data:\n"
                    f"  Price: ${price:,.2f}\n"
                    f"  24h Change: {change_24h:+.2f}%\n"
                    f"  Market Cap: ${market_cap:,.0f}\n"
                    f"  24h Volume: ${volume:,.0f}\n"
                )
        except Exception as e:
            logger.warning("CoinGecko fetch failed: %s", e)

        return ""

    @staticmethod
    def _get_commodity_context(commodity: str) -> str:
        """Static context for commodity markets."""
        contexts = {
            "crude_oil": (
                "Key factors for crude oil prices:\n"
                "- OPEC+ production decisions\n"
                "- US Strategic Petroleum Reserve levels\n"
                "- Global economic growth indicators (GDP, PMI)\n"
                "- Geopolitical tensions in oil-producing regions\n"
                "- US Dollar strength (inverse correlation)\n"
                "- Seasonal demand patterns\n"
                "- EIA weekly inventory reports\n"
            ),
            "natural_gas": (
                "Key factors for natural gas prices:\n"
                "- Weather forecasts (heating/cooling demand)\n"
                "- Storage levels (EIA weekly report)\n"
                "- LNG export demand\n"
                "- Production levels and rig counts\n"
                "- Pipeline capacity and constraints\n"
            ),
            "gold": (
                "Key factors for gold prices:\n"
                "- US Dollar strength (inverse correlation)\n"
                "- Real interest rates (inverse correlation)\n"
                "- Central bank buying/selling\n"
                "- Geopolitical uncertainty (safe-haven demand)\n"
                "- Inflation expectations\n"
            ),
        }
        return contexts.get(commodity.lower(), "")

    @staticmethod
    def _get_politics_context(topic: str) -> str:
        """Context frameworks for political prediction markets."""
        return (
            "Key factors for political predictions:\n"
            "- Historical base rates for similar events\n"
            "- Incumbent advantage/disadvantage patterns\n"
            "- Economic indicators (typically strongest predictor)\n"
            "- Recent polling data and trends\n"
            "- Media narrative momentum\n"
            "- Key institutional endorsements\n"
            "- Voter turnout predictions\n"
        )

    # ------------------------------------------------------------------
    # Symbol extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_crypto_symbol(query: str) -> str:
        """Extract the primary crypto symbol from a query."""
        q = query.lower()
        # Check in order of specificity
        symbols = [
            ("bitcoin", "btc"), ("btc", "btc"),
            ("ethereum", "eth"), ("eth", "eth"),
            ("solana", "sol"), ("sol", "sol"),
            ("dogecoin", "doge"), ("doge", "doge"),
            ("xrp", "xrp"), ("ripple", "xrp"),
            ("bnb", "bnb"), ("binance", "bnb"),
        ]
        for keyword, symbol in symbols:
            if keyword in q:
                return symbol
        return ""

    @staticmethod
    def _extract_commodity(query: str) -> str:
        """Extract commodity type from query."""
        q = query.lower()
        if "crude oil" in q or "oil price" in q:
            return "crude_oil"
        if "natural gas" in q:
            return "natural_gas"
        if "gold" in q:
            return "gold"
        return ""

    async def close(self):
        await self._http.aclose()
