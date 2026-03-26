"""Tests for deep seed generation in polymarket_predictor.seeds.generator."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from polymarket_predictor.scrapers.news import Article, DeepResearchResult
from polymarket_predictor.scrapers.polymarket import Market
from polymarket_predictor.seeds.generator import SeedGenerator
from polymarket_predictor.seeds.templates import DEEP_TEMPLATES, CATEGORY_MAP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_market(
    question: str = "Will BTC hit 100K by end of year?",
    slug: str = "btc-100k",
    yes_price: float = 0.65,
    category: str = "Crypto",
    volume: float = 100_000.0,
) -> Market:
    return Market(
        id="test-id",
        question=question,
        slug=slug,
        outcomes=[
            {"name": "Yes", "price": yes_price},
            {"name": "No", "price": round(1 - yes_price, 2)},
        ],
        volume=volume,
        category=category,
        active=True,
        closed=False,
        created_at=None,
        end_date=None,
        resolution=None,
    )


def _make_research(
    num_articles: int = 3,
    wikipedia: str = "Wikipedia context about the topic.",
    price_summary: str = "Price moved from 50% to 65% (up 15%) over the observation period.",
    domain_data: str = "Current BTC Price Data:\n  Price: $95,000\n  24h Change: +3.42%",
    entity_articles: dict | None = None,
) -> DeepResearchResult:
    articles = [
        Article(
            title=f"Article {i}",
            source=f"Source {i}",
            date="2024-01-01",
            url=f"http://example.com/{i}",
            text=f"Article body text number {i} with some detailed content " * 20,
        )
        for i in range(num_articles)
    ]
    result = DeepResearchResult(
        articles=articles,
        wikipedia_context=wikipedia,
        entity_articles=entity_articles or {},
        total_words=5000,
        sources_count=num_articles + (1 if wikipedia else 0),
        price_history=[{"p": 0.5}, {"p": 0.55}, {"p": 0.6}, {"p": 0.65}],
        price_summary=price_summary,
        domain_data=domain_data,
    )
    return result


# ---------------------------------------------------------------------------
# generate_deep_seed
# ---------------------------------------------------------------------------


class TestGenerateDeepSeed:

    def test_deep_seed_creates_file(self, tmp_path):
        """generate_deep_seed returns a Path that exists on disk."""
        gen = SeedGenerator()
        market = _make_market()
        research = _make_research()

        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = gen.generate_deep_seed(market, research)

        assert isinstance(path, Path)
        assert path.exists()
        assert path.stat().st_size > 0

    def test_deep_seed_contains_market_context(self, tmp_path):
        """Seed text includes market odds and volume."""
        gen = SeedGenerator()
        market = _make_market(yes_price=0.72, volume=250_000)
        research = _make_research()

        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = gen.generate_deep_seed(market, research)

        text = path.read_text()
        assert "72.0%" in text  # yes_price formatted
        assert "250,000" in text  # volume formatted

    def test_deep_seed_contains_wikipedia(self, tmp_path):
        """Seed includes Wikipedia content when provided."""
        gen = SeedGenerator()
        market = _make_market()
        research = _make_research(wikipedia="Wikipedia says Bitcoin was created in 2009 by Satoshi Nakamoto.")

        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = gen.generate_deep_seed(market, research)

        text = path.read_text()
        assert "Wikipedia" in text
        assert "Satoshi" in text or "2009" in text

    def test_deep_seed_contains_price_history(self, tmp_path):
        """Seed includes price summary when provided."""
        gen = SeedGenerator()
        market = _make_market()
        research = _make_research(price_summary="Price moved from 50.0% to 65.0% (up 15.0%)")

        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = gen.generate_deep_seed(market, research)

        text = path.read_text()
        assert "Price" in text
        assert "50.0%" in text or "65.0%" in text

    def test_deep_seed_contains_domain_data(self, tmp_path):
        """Seed includes crypto/commodity data when provided."""
        gen = SeedGenerator()
        market = _make_market()
        research = _make_research(domain_data="Current BTC Price: $95,000.00")

        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = gen.generate_deep_seed(market, research)

        text = path.read_text()
        assert "$95,000" in text

    def test_deep_seed_contains_contrarian_section(self, tmp_path):
        """Seed has contrarian perspectives section."""
        gen = SeedGenerator()
        market = _make_market()
        research = _make_research()

        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = gen.generate_deep_seed(market, research)

        text = path.read_text()
        assert "Contrarian" in text
        assert "WRONG" in text  # "Why might the market be WRONG?"

    def test_deep_seed_minimum_length(self, tmp_path):
        """Seed is at least 3000 chars for deep research."""
        gen = SeedGenerator()
        market = _make_market()
        research = _make_research(num_articles=5)

        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = gen.generate_deep_seed(market, research)

        text = path.read_text()
        assert len(text) >= 3000, f"Deep seed too short: {len(text)} chars"

    def test_deep_seed_handles_empty_research(self, tmp_path):
        """Graceful with empty DeepResearchResult."""
        gen = SeedGenerator()
        market = _make_market()
        research = DeepResearchResult()  # All defaults (empty)

        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = gen.generate_deep_seed(market, research)

        assert path.exists()
        text = path.read_text()
        # Should still have the question and contrarian section
        assert market.question in text
        assert "Contrarian" in text


# ---------------------------------------------------------------------------
# Deep templates coverage
# ---------------------------------------------------------------------------


class TestDeepTemplates:

    def test_deep_templates_all_categories(self):
        """Every category that appears in CATEGORY_MAP has a deep template."""
        for cat_key in set(CATEGORY_MAP.values()):
            assert cat_key in DEEP_TEMPLATES, (
                f"Category '{cat_key}' in CATEGORY_MAP but missing from DEEP_TEMPLATES"
            )

    def test_deep_templates_have_required_fields(self):
        """Every deep template has all required prompt fields."""
        for key, template in DEEP_TEMPLATES.items():
            assert template.background_prompt, f"{key} missing background_prompt"
            assert template.stakeholder_prompt, f"{key} missing stakeholder_prompt"
            assert template.contrarian_prompt, f"{key} missing contrarian_prompt"
            assert template.historical_prompt, f"{key} missing historical_prompt"
            assert template.seed_header, f"{key} missing seed_header"
