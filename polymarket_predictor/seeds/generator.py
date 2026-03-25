"""Seed document generator for prediction-market debates.

Combines market data and news articles into structured .txt documents that
serve as initial context for the agent-based prediction pipeline.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Literal

from polymarket_predictor.config import SEEDS_DIR
from polymarket_predictor.scrapers.news import Article
from polymarket_predictor.scrapers.polymarket import Market
from polymarket_predictor.seeds.templates import CATEGORY_MAP, TEMPLATES, SeedTemplate

logger = logging.getLogger(__name__)

Variant = Literal["balanced", "news_heavy", "contrarian", "data_heavy"]

# Maximum characters of article text to include per article.
_DEFAULT_ARTICLE_LIMIT = 1500
_NEWS_HEAVY_ARTICLE_LIMIT = 3000


class SeedGenerator:
    """Builds seed documents from market data and news articles."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_seed(
        self,
        market: Market,
        articles: list[Article],
        variant: Variant = "balanced",
    ) -> Path:
        """Build a structured seed document and write it to disk.

        Parameters
        ----------
        market:
            The prediction market to create a seed for.
        articles:
            Related news articles to include as evidence.
        variant:
            Document flavour -- ``"balanced"`` (default), ``"news_heavy"``,
            ``"contrarian"``, or ``"data_heavy"``.

        Returns
        -------
        Path
            Absolute path to the generated ``.txt`` file.
        """
        template = self._resolve_template(market.category)
        char_limit = (
            _NEWS_HEAVY_ARTICLE_LIMIT if variant == "news_heavy" else _DEFAULT_ARTICLE_LIMIT
        )

        if variant == "data_heavy":
            articles = self._prioritise_data_articles(articles)

        sections: list[str] = [
            self._section_question(market),
            self._section_market_data(market),
            self._section_context(template),
        ]

        if variant == "contrarian":
            sections.append(self._section_counterarguments())

        if variant == "data_heavy":
            sections.append(self._section_statistical_context())

        sections.append(self._section_articles(articles, char_limit, variant))
        sections.append(self._section_closing(market))

        document = "\n\n".join(sections) + "\n"
        output_path = self._write(market, variant, document)

        logger.info(
            "Generated %s seed for market '%s' -> %s",
            variant,
            market.question[:60],
            output_path,
        )
        return output_path

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _section_question(market: Market) -> str:
        return f"# Prediction Market Question\n{market.question}"

    @staticmethod
    def _section_market_data(market: Market) -> str:
        # Extract prices from outcomes list
        outcomes = getattr(market, "outcomes", [])
        yes_price = "N/A"
        no_price = "N/A"
        for o in outcomes:
            name = o.get("name", "").lower()
            price = o.get("price", 0)
            if name == "yes":
                yes_price = f"{float(price):.1%}" if price else "N/A"
            elif name == "no":
                no_price = f"{float(price):.1%}" if price else "N/A"
            elif name == "up":
                yes_price = f"{float(price):.1%}" if price else "N/A"
            elif name == "down":
                no_price = f"{float(price):.1%}" if price else "N/A"

        volume = getattr(market, "volume", 0)
        category = getattr(market, "category", "Unknown")
        volume_str = f"${volume:,.0f}" if isinstance(volume, (int, float)) else str(volume)

        lines = [
            "# Current Market Data",
            f"- Outcome prices: Yes = {yes_price}, No = {no_price}",
            f"- Total volume: {volume_str}",
            f"- Category: {category}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _section_context(template: SeedTemplate) -> str:
        lines = [
            "# Context & Analysis Focus",
            template.seed_header,
            "",
            f"Agent focus: {template.agent_focus}",
            f"Key context: {template.context_emphasis}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _section_counterarguments() -> str:
        return (
            "# Counterarguments & Opposing Views\n"
            "Consider the strongest reasons the consensus might be wrong. "
            "Look for overlooked evidence, selection bias in available data, "
            "and historical cases where the expected outcome did not materialise. "
            "Articles below should be read with a skeptical lens -- what might "
            "they be missing or overstating?"
        )

    @staticmethod
    def _section_statistical_context() -> str:
        return (
            "# Statistical Context\n"
            "Pay special attention to quantitative evidence in the articles "
            "below. Extract concrete numbers, percentages, sample sizes, and "
            "base rates. Where possible, compare current figures against "
            "historical baselines."
        )

    @staticmethod
    def _section_articles(
        articles: list[Article],
        char_limit: int,
        variant: Variant,
    ) -> str:
        if not articles:
            return "# Recent News & Evidence\nNo articles available."

        parts: list[str] = ["# Recent News & Evidence"]

        for article in articles:
            source = getattr(article, "source", "Unknown")
            date = getattr(article, "date", "Unknown")
            title = getattr(article, "title", "Untitled")
            text = getattr(article, "text", "") or ""

            truncated = text[:char_limit]
            if len(text) > char_limit:
                truncated = truncated.rsplit(" ", 1)[0] + " ..."

            header = f"## {title} ({source}, {date})"

            if variant == "contrarian":
                header += "\n[Read critically -- consider what this report may overstate or omit.]"

            parts.append(f"{header}\n{truncated}")

        return "\n\n".join(parts)

    @staticmethod
    def _section_closing(market: Market) -> str:
        return (
            "# Key Question for Analysis\n"
            f"Based on the evidence above, what is the most likely outcome for: "
            f"{market.question}?\n"
            "Agents should debate and estimate the probability of each outcome."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_template(category: str | None) -> SeedTemplate:
        """Map a market category string to the matching SeedTemplate."""
        key = CATEGORY_MAP.get(category or "", "general")
        return TEMPLATES.get(key, TEMPLATES["general"])

    @staticmethod
    def _prioritise_data_articles(articles: list[Article]) -> list[Article]:
        """Sort articles so those containing numbers/statistics come first."""
        number_pattern = re.compile(r"\d+[\d,.]*%?")

        def _score(article: Article) -> int:
            text = getattr(article, "text", "") or ""
            return len(number_pattern.findall(text))

        return sorted(articles, key=_score, reverse=True)

    @staticmethod
    def _write(market: Market, variant: str, document: str) -> Path:
        """Persist the seed document to disk and return its path."""
        slug = getattr(market, "slug", None) or "unknown_market"
        out_dir = SEEDS_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        path = out_dir / f"seed_{variant}.txt"
        path.write_text(document, encoding="utf-8")
        return path
