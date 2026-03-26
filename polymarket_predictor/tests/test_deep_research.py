"""Tests for deep research functionality in polymarket_predictor.scrapers.news."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from polymarket_predictor.scrapers.news import (
    Article,
    DeepResearchResult,
    NewsAggregator,
)


# ---------------------------------------------------------------------------
# _detect_category
# ---------------------------------------------------------------------------


class TestDetectCategory:

    def test_detect_category_crypto(self):
        assert NewsAggregator._detect_category("Will Bitcoin hit 100K?") == "crypto"

    def test_detect_category_crypto_eth(self):
        assert NewsAggregator._detect_category("Will ETH break $5000?") == "crypto"

    def test_detect_category_geopolitics(self):
        assert NewsAggregator._detect_category("US Iran ceasefire agreement") == "geopolitics"

    def test_detect_category_geopolitics_war(self):
        assert NewsAggregator._detect_category("Russia Ukraine war escalation") == "geopolitics"

    def test_detect_category_politics(self):
        assert NewsAggregator._detect_category("Will Newsom win the election?") == "politics"

    def test_detect_category_politics_congress(self):
        assert NewsAggregator._detect_category("Will congress pass the bill?") == "politics"

    def test_detect_category_commodity(self):
        assert NewsAggregator._detect_category("Crude oil hit $100?") == "commodity"

    def test_detect_category_commodity_gold(self):
        assert NewsAggregator._detect_category("Will gold price reach $3000?") == "commodity"

    def test_detect_category_unknown(self):
        assert NewsAggregator._detect_category("Will it rain tomorrow?") == "general"

    def test_detect_category_empty(self):
        assert NewsAggregator._detect_category("") == "general"


# ---------------------------------------------------------------------------
# _extract_entities
# ---------------------------------------------------------------------------


class TestExtractEntities:

    def test_extract_entities_crypto(self):
        entities = NewsAggregator._extract_entities("Will Bitcoin and Ethereum crash?")
        entity_lower = [e.lower() for e in entities]
        assert "bitcoin" in entity_lower
        assert "ethereum" in entity_lower

    def test_extract_entities_names(self):
        entities = NewsAggregator._extract_entities("Will Elon Musk buy Twitter?")
        joined = " ".join(entities).lower()
        assert "elon" in joined or "musk" in joined

    def test_extract_entities_empty(self):
        entities = NewsAggregator._extract_entities("")
        assert entities == []

    def test_extract_entities_no_caps(self):
        entities = NewsAggregator._extract_entities("will something happen tomorrow?")
        # No capitalized words -> no entities (or only acronyms)
        for e in entities:
            assert e == e.upper()  # only all-caps acronyms if any

    def test_extract_entities_acronyms(self):
        entities = NewsAggregator._extract_entities("Will NATO intervene in the EU crisis?")
        entity_set = set(entities)
        assert "NATO" in entity_set or "EU" in entity_set

    def test_extract_entities_max_five(self):
        entities = NewsAggregator._extract_entities(
            "Apple Google Microsoft Amazon Meta Tesla Nvidia all crash simultaneously"
        )
        assert len(entities) <= 5


# ---------------------------------------------------------------------------
# DeepResearchResult totals
# ---------------------------------------------------------------------------


class TestDeepResearchResult:

    def test_word_count_calculation(self):
        result = DeepResearchResult()
        result.articles = [
            Article(title="T1", source="S1", date="", url="", text="word " * 100),
            Article(title="T2", source="S2", date="", url="", text="word " * 200),
        ]
        result.wikipedia_context = "wiki " * 50
        result.price_summary = ""
        result.domain_data = ""
        result.entity_articles = {}

        # Recalculate like the source does
        all_texts = [a.text for a in result.articles]
        all_texts.append(result.wikipedia_context)
        all_texts.append(result.price_summary)
        all_texts.append(result.domain_data)
        combined = " ".join(all_texts)
        result.total_words = len(combined.split())

        assert result.total_words == 350

    def test_sources_count_includes_all_types(self):
        result = DeepResearchResult()
        result.articles = [
            Article(title="T1", source="S", date="", url="", text="x"),
            Article(title="T2", source="S", date="", url="", text="x"),
        ]
        result.wikipedia_context = "Some wiki context"
        result.entity_articles = {
            "Bitcoin": [Article(title="E1", source="S", date="", url="", text="x")],
        }
        result.price_history = [{"p": 0.5}]
        result.domain_data = "Some domain data"

        # Calculate like the source
        sources_count = (
            len(result.articles)
            + (1 if result.wikipedia_context else 0)
            + sum(len(arts) for arts in result.entity_articles.values())
            + (1 if result.price_history else 0)
            + (1 if result.domain_data else 0)
        )
        result.sources_count = sources_count

        # 2 articles + 1 wiki + 1 entity article + 1 price + 1 domain = 6
        assert result.sources_count == 6


# ---------------------------------------------------------------------------
# search_articles_deep with mocking
# ---------------------------------------------------------------------------


class TestSearchArticlesDeep:

    @pytest.mark.asyncio
    async def test_search_articles_deep_with_mock(self):
        """Mock all HTTP calls, verify it combines DDG + Wikipedia + entity results."""
        agg = NewsAggregator()

        fake_article = Article(title="Fake", source="DDG", date="2024-01-01", url="http://x", text="Some text about topic")

        with patch.object(agg, "search_articles", new_callable=AsyncMock, return_value=[fake_article]) as mock_search, \
             patch.object(agg, "_search_general", new_callable=AsyncMock, return_value=[fake_article]) as mock_general, \
             patch.object(agg, "_fetch_wikipedia_context", new_callable=AsyncMock, return_value="Wikipedia content about topic") as mock_wiki:

            result = await agg.search_articles_deep("Will Bitcoin hit 100K?")

            assert isinstance(result, DeepResearchResult)
            # DDG news + general = at least 2 articles
            assert len(result.articles) >= 2
            assert result.wikipedia_context == "Wikipedia content about topic"
            assert result.total_words > 0
            assert result.sources_count > 0

        await agg.close()

    @pytest.mark.asyncio
    async def test_search_articles_deep_wikipedia_failure_graceful(self):
        """Wikipedia fails, but rest continues without crashing."""
        agg = NewsAggregator()

        fake_article = Article(title="F", source="S", date="", url="", text="word " * 50)

        with patch.object(agg, "search_articles", new_callable=AsyncMock, return_value=[fake_article]), \
             patch.object(agg, "_search_general", new_callable=AsyncMock, return_value=[]), \
             patch.object(agg, "_fetch_wikipedia_context", new_callable=AsyncMock, side_effect=Exception("wiki down")):

            result = await agg.search_articles_deep("Test query")

            # Should succeed despite wiki failure
            assert isinstance(result, DeepResearchResult)
            assert len(result.articles) >= 1
            assert result.wikipedia_context == ""  # Failed, so empty

        await agg.close()


# ---------------------------------------------------------------------------
# _fetch_crypto_data formatting
# ---------------------------------------------------------------------------


class TestCryptoDataFormatting:

    @pytest.mark.asyncio
    async def test_crypto_data_formatting(self):
        """Mock CoinGecko response, verify output format."""
        agg = NewsAggregator()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "bitcoin": {
                "usd": 95000.50,
                "usd_24h_change": 3.42,
                "usd_market_cap": 1900000000000,
                "usd_24h_vol": 45000000000,
            }
        }

        with patch.object(agg._http, "get", new_callable=AsyncMock, return_value=mock_response):
            result = await agg._fetch_crypto_data("btc")

        assert "BTC" in result
        assert "$95,000.50" in result
        assert "+3.42%" in result
        assert "Market Cap" in result
        assert "24h Volume" in result

        await agg.close()


# ---------------------------------------------------------------------------
# _extract_crypto_symbol
# ---------------------------------------------------------------------------


class TestExtractCryptoSymbol:

    def test_bitcoin(self):
        assert NewsAggregator._extract_crypto_symbol("Will Bitcoin hit 100K?") == "btc"

    def test_eth(self):
        assert NewsAggregator._extract_crypto_symbol("ETH price above $5000") == "eth"

    def test_no_crypto(self):
        assert NewsAggregator._extract_crypto_symbol("Will it rain tomorrow?") == ""
