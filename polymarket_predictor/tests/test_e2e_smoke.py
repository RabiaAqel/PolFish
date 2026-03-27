"""End-to-end smoke test for the PolFish prediction pipeline.

Runs the FULL pipeline against a REAL Polymarket market using the
cheapest possible configuration. Validates every step works.

Cost: ~$0.02-0.05 per run (DeepSeek for everything)
Time: ~3-5 minutes
Usage: pytest -m e2e polymarket_predictor/tests/test_e2e_smoke.py -v

NOT run in the regular test suite (requires API keys + network).
"""

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)

# Skip if no API keys configured
SKIP_REASON = "E2E test requires LLM_API_KEY and ZEP_API_KEY"


def _has_keys():
    """Check at call time, not import time."""
    return bool(os.environ.get("LLM_API_KEY")) and bool(os.environ.get("ZEP_API_KEY"))


@pytest.mark.e2e
class TestE2ESmoke:
    """Full pipeline smoke test with real APIs, minimal cost."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up cheap configuration for E2E test."""
        self.tmp_dir = tmp_path
        self.original_preset = os.environ.get("PIPELINE_PRESET")
        self.original_rounds = os.environ.get("MAX_SIMULATION_ROUNDS")

        # Force cheapest configuration
        os.environ["PIPELINE_PRESET"] = "cheapest"  # All DeepSeek
        os.environ["MAX_SIMULATION_ROUNDS"] = "5"    # Minimal rounds

        yield

        # Restore
        if self.original_preset:
            os.environ["PIPELINE_PRESET"] = self.original_preset
        elif "PIPELINE_PRESET" in os.environ:
            del os.environ["PIPELINE_PRESET"]
        if self.original_rounds:
            os.environ["MAX_SIMULATION_ROUNDS"] = self.original_rounds
        elif "MAX_SIMULATION_ROUNDS" in os.environ:
            del os.environ["MAX_SIMULATION_ROUNDS"]

    @pytest.mark.skipif(not _has_keys(), reason=SKIP_REASON)
    @pytest.mark.asyncio
    async def test_full_pipeline_smoke(self):
        """Run the complete pipeline: scan -> seed -> graph -> simulate -> report -> predict.

        This is the golden path test. If this passes, the system works end-to-end.
        """
        start_time = time.time()

        # Step 1: Find a real market
        logger.info("Step 1: Scanning for a market...")
        from polymarket_predictor.scrapers.polymarket import PolymarketScraper

        async with PolymarketScraper() as scraper:
            markets = await scraper.get_active_markets(limit=50, min_volume=100)

        assert len(markets) > 0, "No active markets found on Polymarket"

        # Pick a market with interesting odds (not near 0 or 100)
        good_markets = []
        for m in markets:
            yes_price = 0.5
            for o in m.outcomes:
                if isinstance(o, dict) and o.get('name', '').lower() in ('yes', 'up'):
                    yes_price = float(o.get('price', 0.5))
                    break
            if 0.15 <= yes_price <= 0.85:
                good_markets.append(m)

        assert len(good_markets) > 0, "No markets with interesting odds found"
        market = good_markets[0]
        logger.info(f"  Selected: {market.question[:60]} (odds={yes_price:.0%})")

        # Step 2: Generate seed document (basic, not deep)
        logger.info("Step 2: Generating seed...")
        from polymarket_predictor.scrapers.news import NewsAggregator
        from polymarket_predictor.seeds.generator import SeedGenerator

        news = NewsAggregator()
        try:
            articles = await news.search_articles(market.question, max_results=2)
        finally:
            await news.close()

        gen = SeedGenerator()
        seed_path = gen.generate_seed(market, articles, variant="balanced")
        assert seed_path.exists(), f"Seed file not created: {seed_path}"
        seed_text = seed_path.read_text()
        assert len(seed_text) > 100, f"Seed too short: {len(seed_text)} chars"
        logger.info(f"  Seed: {len(seed_text)} chars, {len(articles)} articles")

        # Step 3: Run MiroFish pipeline (with minimal config)
        logger.info("Step 3: Running MiroFish pipeline (cheapest preset, 5 rounds)...")
        from polymarket_predictor.orchestrator.pipeline import MiroFishPipeline

        pipeline = MiroFishPipeline()
        try:
            # Override max_templates to inject fewer agents
            report = await pipeline.run(
                seed_file_path=seed_path,
                simulation_requirement=market.question,
                max_rounds=5,  # Minimal
            )
        finally:
            await pipeline.client.aclose()

        assert report is not None, "Pipeline returned None"
        assert "simulation_id" in report, "Report missing simulation_id"
        sim_id = report["simulation_id"]
        logger.info(f"  Simulation: {sim_id}")

        # Step 4: Extract report text
        logger.info("Step 4: Extracting prediction...")
        report_text = (
            report.get("markdown_content", "")
            or report.get("report_text", "")
            or report.get("content", "")
        )
        assert len(report_text) > 50, f"Report text too short: {len(report_text)} chars"
        logger.info(f"  Report: {len(report_text)} chars")

        # Step 5: Parse prediction
        from polymarket_predictor.parser.prediction import PredictionParser
        parser = PredictionParser()
        prediction = await parser.parse(report_text, market.question)

        assert 0.0 <= prediction.probability <= 1.0, f"Invalid probability: {prediction.probability}"
        assert prediction.confidence in ("high", "medium", "low"), f"Invalid confidence: {prediction.confidence}"
        logger.info(f"  Prediction: {prediction.probability:.1%}, confidence={prediction.confidence}")

        # Step 6: Run quantitative analysis
        logger.info("Step 5: Running quantitative analysis...")
        from polymarket_predictor.analyzer.simulation_analyzer import SimulationAnalyzer
        try:
            analyzer = SimulationAnalyzer()
            quant = analyzer.analyze(sim_id, market.question, yes_price)
            logger.info(f"  Quant: raw={quant.raw_sentiment:.2f}, weighted={quant.weighted_sentiment:.2f}, computed={quant.computed_probability:.1%}")
            assert 0.0 <= quant.computed_probability <= 1.0
        except FileNotFoundError:
            logger.warning("  Quant analysis skipped (simulation data not found)")

        # Step 7: Verify paper bet would work
        logger.info("Step 6: Verifying bet logic...")
        from polymarket_predictor.paper_trader.portfolio import PaperPortfolio, BetSizer

        portfolio = PaperPortfolio(data_dir=self.tmp_dir, initial_balance=10000)
        sizer = BetSizer()

        edge = prediction.probability - yes_price
        abs_edge = abs(edge)
        side = "YES" if edge > 0 else "NO"

        bet_info = sizer.size_bet(
            portfolio.balance, prediction.probability, yes_price,
            abs_edge, prediction.confidence
        )
        logger.info(f"  Edge: {edge:+.1%}, side={side}, bet=${bet_info['amount']:.2f}")

        if bet_info["amount"] > 0:
            bet = portfolio.place_bet(
                market_id=market.slug, slug=market.slug,
                question=market.question, side=side,
                amount=bet_info["amount"], odds=yes_price,
                prediction=prediction.probability,
                edge=abs_edge, confidence=prediction.confidence,
                mode="e2e_test",
            )
            assert bet is not None
            assert portfolio.balance < 10000
            logger.info(f"  Bet placed: {side} ${bet_info['amount']:.2f}")
        else:
            logger.info(f"  No bet (edge {abs_edge:.1%} below threshold)")

        # Step 8: Verify context store
        logger.info("Step 7: Verifying context store...")
        from polymarket_predictor.knowledge.context_store import ContextStore, MarketContext
        store = ContextStore(data_dir=self.tmp_dir)
        store.add(MarketContext(
            market_id=market.slug,
            question=market.question,
            category="e2e_test",
            market_odds_at_prediction=yes_price,
            our_prediction=prediction.probability,
            key_factors=prediction.key_factors[:3],
            agent_consensus="bullish" if prediction.probability > 0.6 else "bearish",
        ))
        entries = store.get_by_category("e2e_test")
        assert len(entries) == 1

        elapsed = time.time() - start_time
        logger.info(f"\n{'='*60}")
        logger.info(f"E2E SMOKE TEST PASSED in {elapsed:.0f}s")
        logger.info(f"  Market: {market.question[:50]}")
        logger.info(f"  Prediction: {prediction.probability:.1%} (market: {yes_price:.0%})")
        logger.info(f"  Edge: {edge:+.1%}")
        logger.info(f"  Cost: ~$0.02-0.05 (cheapest preset)")
        logger.info(f"{'='*60}")


@pytest.mark.e2e
class TestE2EMarketDiscovery:
    """Test that market discovery and grouping works with real data."""

    @pytest.mark.skipif(not _has_keys(), reason="Requires network access")
    @pytest.mark.asyncio
    async def test_scan_and_group_real_markets(self):
        """Scan real Polymarket markets and group them."""
        from polymarket_predictor.scanner.market_scanner import MarketScanner
        from polymarket_predictor.thesis.grouper import MarketGrouper

        async with MarketScanner() as scanner:
            markets = await scanner.scan_interesting(
                days_ahead=30, min_volume=100, odds_range=(0.10, 0.90)
            )

        assert len(markets) > 0, "No interesting markets found"
        logger.info(f"Found {len(markets)} interesting markets")

        grouper = MarketGrouper()
        groups = grouper.group_markets(markets)

        multi = [g for g in groups if len(g.markets) > 1]
        single = [g for g in groups if len(g.markets) == 1]

        logger.info(f"Grouped into {len(groups)} groups ({len(multi)} multi-tier, {len(single)} single)")

        for g in multi[:3]:
            logger.info(f"  {g.group_type}: {g.thesis_question[:50]} ({len(g.markets)} markets)")

        assert len(groups) > 0


@pytest.mark.e2e
class TestE2ENewsResearch:
    """Test deep research with real news sources."""

    @pytest.mark.asyncio
    async def test_deep_research_real(self):
        """Fetch real news for a market question."""
        from polymarket_predictor.scrapers.news import NewsAggregator

        news = NewsAggregator()
        try:
            result = await news.search_articles_deep(
                "Will there be a US-Iran ceasefire?",
                max_results=3,
            )
            logger.info(f"Deep research: {len(result.articles)} articles, {result.total_words} words, {result.sources_count} sources")
            assert result.sources_count > 0
        finally:
            await news.close()
