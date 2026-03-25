"""Tests for polymarket_predictor.seeds.generator and templates."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from polymarket_predictor.scrapers.news import Article
from polymarket_predictor.scrapers.polymarket import Market
from polymarket_predictor.seeds.generator import SeedGenerator
from polymarket_predictor.seeds.templates import CATEGORY_MAP, TEMPLATES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def generator():
    return SeedGenerator()


@pytest.fixture
def market():
    return Market(
        id="m1",
        question="Will Bitcoin exceed $100k by end of 2025?",
        slug="btc-100k-2025",
        outcomes=[{"name": "Yes", "price": 0.65}, {"name": "No", "price": 0.35}],
        volume=120000.0,
        category="Crypto",
        active=True,
        closed=False,
        created_at=None,
        end_date=None,
    )


@pytest.fixture
def articles():
    return [
        Article(
            title="Bitcoin Surges Past $95k",
            source="CoinDesk",
            date="2025-11-01",
            url="https://example.com/1",
            text="Bitcoin has rallied 15% this month reaching new highs. "
            "Institutional adoption is accelerating." * 20,
        ),
        Article(
            title="Analysts Predict Crypto Bull Run",
            source="Reuters",
            date="2025-11-02",
            url="https://example.com/2",
            text="Multiple analysts see potential for BTC to exceed $100k. "
            "Trading volume 500% up year over year." * 10,
        ),
    ]


@pytest.fixture
def data_heavy_articles():
    """Articles with varying numeric content for data_heavy sorting."""
    return [
        Article(
            title="Qualitative Only",
            source="Blog",
            date="2025-01-01",
            url="https://example.com/a",
            text="No numbers here at all, just opinions and speculation.",
        ),
        Article(
            title="Lots of Data",
            source="Research",
            date="2025-01-02",
            url="https://example.com/b",
            text="BTC was 95000 up 15% with volume of 1200000 and 73% of traders bullish, RSI at 68, 24h change 3.2%",
        ),
        Article(
            title="Some Data",
            source="News",
            date="2025-01-03",
            url="https://example.com/c",
            text="Price rose to 90000 and volume was 500000.",
        ),
    ]


# ---------------------------------------------------------------------------
# generate_seed basics
# ---------------------------------------------------------------------------


class TestGenerateSeed:
    def test_creates_file_returns_path(self, generator, market, articles, tmp_path):
        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            result = generator.generate_seed(market, articles)
            assert isinstance(result, Path)
            assert result.exists()
            assert result.suffix == ".txt"

    def test_balanced_variant(self, generator, market, articles, tmp_path):
        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = generator.generate_seed(market, articles, variant="balanced")
            content = path.read_text()
            # balanced uses 1500 char limit -- articles get truncated
            assert "# Prediction Market Question" in content

    def test_news_heavy_variant(self, generator, market, articles, tmp_path):
        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path_nh = generator.generate_seed(market, articles, variant="news_heavy")
            path_bal = generator.generate_seed(market, articles, variant="balanced")
            # news_heavy has a higher char limit so it should contain more text
            assert len(path_nh.read_text()) >= len(path_bal.read_text())

    def test_contrarian_variant(self, generator, market, articles, tmp_path):
        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = generator.generate_seed(market, articles, variant="contrarian")
            content = path.read_text()
            assert "Counterarguments" in content
            assert "skeptical lens" in content

    def test_data_heavy_variant_sorts_articles(self, generator, market, data_heavy_articles, tmp_path):
        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = generator.generate_seed(market, data_heavy_articles, variant="data_heavy")
            content = path.read_text()
            assert "Statistical Context" in content
            # The article with lots of numbers should appear before the qualitative one
            lots_idx = content.find("Lots of Data")
            qual_idx = content.find("Qualitative Only")
            assert lots_idx < qual_idx

    def test_no_articles(self, generator, market, tmp_path):
        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = generator.generate_seed(market, [], variant="balanced")
            content = path.read_text()
            assert "No articles available" in content
            assert path.exists()


# ---------------------------------------------------------------------------
# Seed content verification
# ---------------------------------------------------------------------------


class TestSeedContent:
    def test_contains_market_question(self, generator, market, articles, tmp_path):
        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = generator.generate_seed(market, articles)
            content = path.read_text()
            assert market.question in content

    def test_contains_odds(self, generator, market, articles, tmp_path):
        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = generator.generate_seed(market, articles)
            content = path.read_text()
            assert "65.0%" in content  # Yes price
            assert "35.0%" in content  # No price

    def test_contains_volume(self, generator, market, articles, tmp_path):
        with patch("polymarket_predictor.seeds.generator.SEEDS_DIR", tmp_path):
            path = generator.generate_seed(market, articles)
            content = path.read_text()
            assert "$120,000" in content


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


class TestTemplates:
    def test_all_categories_have_valid_templates(self):
        for cat, key in CATEGORY_MAP.items():
            assert key in TEMPLATES, f"CATEGORY_MAP[{cat!r}] = {key!r} not in TEMPLATES"

    def test_all_templates_have_required_fields(self):
        for key, tpl in TEMPLATES.items():
            assert tpl.category, f"Template {key!r} missing category"
            assert tpl.agent_focus, f"Template {key!r} missing agent_focus"
            assert tpl.context_emphasis, f"Template {key!r} missing context_emphasis"
            assert tpl.seed_header, f"Template {key!r} missing seed_header"

    def test_general_template_exists(self):
        assert "general" in TEMPLATES

    def test_unknown_category_falls_back_to_general(self, generator):
        tpl = generator._resolve_template("NonExistentCategory")
        assert tpl.category == "general"

    def test_none_category_falls_back_to_general(self, generator):
        tpl = generator._resolve_template(None)
        assert tpl.category == "general"
