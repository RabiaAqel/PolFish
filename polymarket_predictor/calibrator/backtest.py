"""Backtest runner — evaluates prediction accuracy against resolved markets."""

import asyncio
import logging
from dataclasses import dataclass

from polymarket_predictor.scrapers.polymarket import PolymarketScraper, Market
from polymarket_predictor.scrapers.news import NewsAggregator
from polymarket_predictor.orchestrator.pipeline import MiroFishPipeline
from polymarket_predictor.seeds.generator import SeedGenerator
from polymarket_predictor.orchestrator.prompts import get_simulation_prompt
from polymarket_predictor.parser.prediction import PredictionParser
from polymarket_predictor.calibrator.history import PredictionHistory, PredictionRecord, ResolutionRecord

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    total: int
    correct: int
    accuracy: float
    brier_score: float
    details: list[dict]


async def run_backtest(count: int = 50, max_rounds: int = 10) -> BacktestResult:
    """Run backtest against resolved Polymarket markets.

    Uses single-variant simulations for speed.
    Returns accuracy metrics and per-market details.
    """
    scraper = PolymarketScraper()
    news = NewsAggregator()
    pipeline = MiroFishPipeline()
    seed_gen = SeedGenerator()
    parser = PredictionParser()
    history = PredictionHistory()

    details = []
    correct = 0
    total = 0
    brier_sum = 0.0

    try:
        markets = await scraper.get_resolved_markets(limit=count)
        logger.info(f"Backtesting against {len(markets)} resolved markets")

        for i, market in enumerate(markets):
            try:
                logger.info(f"[{i+1}/{len(markets)}] {market.question[:60]}...")

                articles = await news.search_articles(market.question, max_results=3)
                seed_path = seed_gen.generate_seed(market, articles, "balanced")
                prompt = get_simulation_prompt(market.question, market.category)
                report = await pipeline.run(seed_path, prompt, max_rounds=max_rounds)

                report_text = report.get("markdown_content", "") or str(report.get("sections", {}))
                prediction = await parser.parse(report_text, market.question)

                resolution = market.resolution or ""
                actual = 1 if resolution.lower() in ("yes", "up") else 0
                brier = (prediction.probability - actual) ** 2
                brier_sum += brier
                total += 1

                predicted_yes = prediction.probability > 0.5
                is_correct = predicted_yes == (actual == 1)
                if is_correct:
                    correct += 1

                detail = {
                    "market_id": market.id,
                    "question": market.question,
                    "predicted": prediction.probability,
                    "actual": resolution,
                    "actual_binary": actual,
                    "brier": brier,
                    "correct": is_correct,
                }
                details.append(detail)

                # Log to history for calibration
                market_prob = next((o["price"] for o in market.outcomes if o["name"].lower() in ("yes", "up")), 0.5)
                history.log_prediction(PredictionRecord(
                    market_id=market.id, question=market.question,
                    predicted_prob=prediction.probability, market_prob=market_prob,
                    ensemble_std=0.0, signal="BACKTEST", reliability="n/a", num_variants=1,
                ))
                history.log_resolution(ResolutionRecord(
                    market_id=market.id, question=market.question,
                    outcome=resolution, outcome_binary=actual,
                    resolved_at=market.end_date or "",
                ))

            except Exception as e:
                logger.error(f"  Failed: {e}")
                continue

    finally:
        await scraper.close()
        await news.close()
        await pipeline.close()

    accuracy = correct / total if total > 0 else 0
    brier = brier_sum / total if total > 0 else 0

    return BacktestResult(
        total=total,
        correct=correct,
        accuracy=accuracy,
        brier_score=brier,
        details=details,
    )
