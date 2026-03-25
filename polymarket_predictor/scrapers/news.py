"""News article search for Polymarket prediction seeds.

Uses duckduckgo-search for finding recent news, then optionally
fetches full article text via httpx.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

logger = logging.getLogger(__name__)

_MAX_ARTICLE_TEXT = 2000


@dataclass
class Article:
    """A single news article."""

    title: str
    source: str
    date: str
    url: str
    text: str


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

    async def close(self):
        await self._http.aclose()
