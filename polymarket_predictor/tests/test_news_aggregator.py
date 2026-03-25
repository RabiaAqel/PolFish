"""Unit tests for polymarket_predictor.scrapers.news."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from polymarket_predictor.scrapers.news import (
    Article,
    NewsAggregator,
    _extract_article_text,
    _strip_tags,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ddgs_results():
    """Simulated DuckDuckGo search results."""
    return [
        {
            "title": "Bitcoin Surges Past $90k",
            "url": "https://example.com/btc-surge",
            "source": "CryptoNews",
            "date": "2025-03-20",
            "body": "Bitcoin has surged past 90k in a dramatic move.",
        },
        {
            "title": "Ethereum Update Delayed",
            "url": "https://example.com/eth-delay",
            "source": "BlockchainDaily",
            "date": "2025-03-19",
            "body": "Ethereum developers announced a delay.",
        },
    ]


@pytest.fixture
def simple_article_html():
    return (
        "<html><body>"
        "<article><p>Main article paragraph one.</p>"
        "<p>Paragraph two with details.</p></article>"
        "<footer>Footer content</footer>"
        "</body></html>"
    )


@pytest.fixture
def no_article_html():
    return (
        "<html><body>"
        "<p>First paragraph outside article.</p>"
        "<p>Second paragraph outside article.</p>"
        "</body></html>"
    )


# ---------------------------------------------------------------------------
# _strip_tags
# ---------------------------------------------------------------------------

class TestStripTags:
    def test_basic_html(self):
        text = _strip_tags("<p>Hello <b>world</b></p>")
        assert "Hello" in text
        assert "world" in text
        assert "<" not in text

    def test_removes_script(self):
        html = "<p>Before</p><script>alert('x')</script><p>After</p>"
        text = _strip_tags(html)
        assert "alert" not in text
        assert "Before" in text
        assert "After" in text

    def test_removes_style(self):
        html = "<style>.red { color: red; }</style><p>Visible</p>"
        text = _strip_tags(html)
        assert "red" not in text
        assert "Visible" in text

    def test_removes_noscript(self):
        html = "<noscript>Enable JS</noscript><p>Content</p>"
        text = _strip_tags(html)
        assert "Enable JS" not in text
        assert "Content" in text

    def test_adds_newlines_for_block_elements(self):
        html = "<h1>Title</h1><p>Para</p><div>Block</div>"
        text = _strip_tags(html)
        assert "\n" in text


# ---------------------------------------------------------------------------
# _extract_article_text
# ---------------------------------------------------------------------------

class TestExtractArticleText:
    def test_with_article_tag(self, simple_article_html):
        text = _extract_article_text(simple_article_html)
        assert "Main article paragraph one" in text
        assert "Paragraph two" in text
        # Footer should NOT be included (it's outside <article>)
        assert "Footer" not in text

    def test_fallback_to_p_tags(self, no_article_html):
        text = _extract_article_text(no_article_html)
        assert "First paragraph" in text
        assert "Second paragraph" in text

    def test_truncation(self):
        # Build HTML with >2000 chars of text
        long_para = "A" * 3000
        html = f"<article><p>{long_para}</p></article>"
        text = _extract_article_text(html)
        assert len(text) <= 2000

    def test_empty_html(self):
        text = _extract_article_text("")
        assert text == ""

    def test_whitespace_collapsing(self):
        html = "<article><p>  lots   of   spaces  </p></article>"
        text = _extract_article_text(html)
        assert "  " not in text  # multiple spaces should be collapsed


# ---------------------------------------------------------------------------
# NewsAggregator.search_articles
# ---------------------------------------------------------------------------

class TestNewsAggregatorSearchArticles:
    @pytest.mark.asyncio
    async def test_search_articles_success(self, ddgs_results):
        aggregator = NewsAggregator()

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.news.return_value = iter(ddgs_results)
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs_instance):
            # Mock _fetch_article to return empty so body from DDG is used
            with patch.object(aggregator, "_fetch_article", new_callable=AsyncMock, return_value=""):
                articles = await aggregator.search_articles("bitcoin price", max_results=2)

        assert len(articles) == 2
        assert all(isinstance(a, Article) for a in articles)
        assert articles[0].title == "Bitcoin Surges Past $90k"
        assert articles[0].source == "CryptoNews"
        await aggregator.close()

    @pytest.mark.asyncio
    async def test_search_articles_empty(self):
        aggregator = NewsAggregator()

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.news.return_value = iter([])
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs_instance):
            articles = await aggregator.search_articles("obscure query xyz")

        assert articles == []
        await aggregator.close()

    @pytest.mark.asyncio
    async def test_search_articles_ddgs_exception(self):
        """If DDGS raises, search_articles returns empty list."""
        aggregator = NewsAggregator()

        with patch("duckduckgo_search.DDGS", side_effect=Exception("DDG down")):
            articles = await aggregator.search_articles("bitcoin")

        assert articles == []
        await aggregator.close()

    @pytest.mark.asyncio
    async def test_search_articles_prefers_full_text(self, ddgs_results):
        """If _fetch_article returns longer text than body, it should be used."""
        aggregator = NewsAggregator()

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.news.return_value = iter(ddgs_results[:1])
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

        long_text = "Full article text that is much longer than the snippet body. " * 10

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs_instance):
            with patch.object(aggregator, "_fetch_article", new_callable=AsyncMock, return_value=long_text):
                articles = await aggregator.search_articles("bitcoin", max_results=1)

        assert len(articles) == 1
        assert "Full article text" in articles[0].text
        await aggregator.close()

    @pytest.mark.asyncio
    async def test_fetch_article_success(self, simple_article_html):
        aggregator = NewsAggregator()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = simple_article_html
        mock_resp.raise_for_status = MagicMock()

        with patch.object(aggregator._http, "get", new_callable=AsyncMock, return_value=mock_resp):
            text = await aggregator._fetch_article("https://example.com/article")

        assert "Main article paragraph one" in text
        await aggregator.close()

    @pytest.mark.asyncio
    async def test_fetch_article_error_returns_empty(self):
        aggregator = NewsAggregator()

        with patch.object(
            aggregator._http,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.RequestError("Timeout"),
        ):
            text = await aggregator._fetch_article("https://example.com/fail")

        assert text == ""
        await aggregator.close()

    @pytest.mark.asyncio
    async def test_article_text_truncated_to_max(self, ddgs_results):
        """Articles longer than 2000 chars are truncated."""
        aggregator = NewsAggregator()

        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.news.return_value = iter(ddgs_results[:1])
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)

        long_text = "X" * 5000

        with patch("duckduckgo_search.DDGS", return_value=mock_ddgs_instance):
            with patch.object(aggregator, "_fetch_article", new_callable=AsyncMock, return_value=long_text):
                articles = await aggregator.search_articles("bitcoin", max_results=1)

        assert len(articles[0].text) <= 2000
        await aggregator.close()
