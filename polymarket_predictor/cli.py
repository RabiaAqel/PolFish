"""CLI entry point for the Polymarket Predictor."""

import asyncio
import logging
import sys
from pathlib import Path

import click

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("polymarket_predictor")


@click.group()
def cli():
    """Polymarket Predictor — MiroFish-powered prediction market analysis."""
    pass


@cli.command()
@click.option("--top", default=10, help="Number of top markets to scan")
@click.option("--variants", default=3, help="Number of simulation variants per market")
@click.option("--min-volume", default=10000, help="Minimum market volume in USD")
@click.option("--max-rounds", default=15, help="Max simulation rounds per variant")
def scan(top, variants, min_volume, max_rounds):
    """Scan top active Polymarket markets and generate predictions."""
    asyncio.run(_scan(top, variants, min_volume, max_rounds))


async def _scan(top: int, variants: int, min_volume: float, max_rounds: int):
    from polymarket_predictor.scrapers.polymarket import PolymarketScraper
    from polymarket_predictor.scrapers.news import NewsAggregator
    from polymarket_predictor.orchestrator.ensemble import EnsemblePredictor
    from polymarket_predictor.calibrator.history import PredictionHistory, PredictionRecord
    from polymarket_predictor.calibrator.calibrate import Calibrator

    scraper = PolymarketScraper()
    news = NewsAggregator()
    ensemble = EnsemblePredictor(num_variants=variants)
    history = PredictionHistory()
    calibrator = Calibrator()

    try:
        logger.info(f"Fetching top {top} active markets (min volume: ${min_volume:,.0f})...")
        markets = await scraper.get_active_markets(limit=top, min_volume=min_volume)
        logger.info(f"Found {len(markets)} markets")

        for i, market in enumerate(markets):
            logger.info(f"\n{'='*60}")
            logger.info(f"[{i+1}/{len(markets)}] {market.question}")
            logger.info(f"{'='*60}")

            try:
                # Fetch news articles
                articles = await news.search_articles(market.question, max_results=5)
                logger.info(f"Found {len(articles)} articles")

                # Run ensemble prediction
                result = await ensemble.predict(market, articles)

                # Apply calibration
                calibrated_prob = calibrator.calibrate(result.mean_probability)
                calibrated_edge = calibrated_prob - result.market_probability

                # Log results
                logger.info(f"Raw prediction:   {result.mean_probability:.1%}")
                logger.info(f"Calibrated:       {calibrated_prob:.1%}")
                logger.info(f"Market odds:      {result.market_probability:.1%}")
                logger.info(f"Edge:             {calibrated_edge:+.1%}")
                logger.info(f"Reliability:      {result.reliability}")
                logger.info(f"Signal:           {result.signal}")

                # Save to history
                history.log_prediction(PredictionRecord(
                    market_id=market.id,
                    question=market.question,
                    predicted_prob=calibrated_prob,
                    market_prob=result.market_probability,
                    ensemble_std=result.std_deviation,
                    signal=result.signal,
                    reliability=result.reliability,
                    num_variants=len(result.individual_predictions),
                ))

            except Exception as e:
                logger.error(f"Failed to predict market: {e}")
                continue

    finally:
        await scraper.close()
        await news.close()
        await ensemble.close()


@cli.command()
@click.argument("slug")
@click.option("--variants", default=3, help="Number of simulation variants")
@click.option("--max-rounds", default=15, help="Max simulation rounds per variant")
def predict(slug, variants, max_rounds):
    """Predict a single market by slug or URL."""
    asyncio.run(_predict(slug, variants, max_rounds))


async def _predict(slug: str, variants: int, max_rounds: int):
    from polymarket_predictor.scrapers.polymarket import PolymarketScraper
    from polymarket_predictor.scrapers.news import NewsAggregator
    from polymarket_predictor.orchestrator.ensemble import EnsemblePredictor
    from polymarket_predictor.calibrator.calibrate import Calibrator

    # Clean slug from URL if needed
    if "polymarket.com" in slug:
        slug = slug.rstrip("/").split("/")[-1]

    scraper = PolymarketScraper()
    news = NewsAggregator()
    ensemble = EnsemblePredictor(num_variants=variants)
    calibrator = Calibrator()

    try:
        market = await scraper.get_market_by_slug(slug)
        if not market:
            logger.error(f"Market not found: {slug}")
            return

        logger.info(f"Market: {market.question}")
        yes_price = next((o["price"] for o in market.outcomes if o["name"].lower() in ("yes", "up")), None)
        if yes_price is not None:
            logger.info(f"Current odds: Yes={yes_price:.1%}")

        articles = await news.search_articles(market.question, max_results=5)
        logger.info(f"Found {len(articles)} articles")

        result = await ensemble.predict(market, articles)
        calibrated = calibrator.calibrate(result.mean_probability)

        print(f"\n{'='*60}")
        print(f"  PREDICTION: {market.question}")
        print(f"{'='*60}")
        print(f"  MiroFish prediction:  {calibrated:.1%}")
        print(f"  Market odds:          {result.market_probability:.1%}")
        print(f"  Edge:                 {calibrated - result.market_probability:+.1%}")
        print(f"  Reliability:          {result.reliability}")
        print(f"  Signal:               {result.signal}")
        print(f"  Variants run:         {len(result.individual_predictions)}")
        print(f"  Std deviation:        {result.std_deviation:.3f}")
        print(f"{'='*60}\n")

        if result.individual_predictions:
            print("  Individual predictions:")
            for j, p in enumerate(result.individual_predictions):
                print(f"    Variant {j+1}: {p.probability:.1%} (confidence: {p.confidence})")
                if p.key_factors:
                    for f in p.key_factors[:3]:
                        print(f"      - {f}")

    finally:
        await scraper.close()
        await news.close()
        await ensemble.close()


@cli.command()
@click.option("--min-edge", default=0.10, help="Minimum edge to show")
def signals(min_edge):
    """Show current prediction signals from history."""
    from polymarket_predictor.calibrator.history import PredictionHistory

    history = PredictionHistory()
    predictions = history.get_predictions()

    if not predictions:
        print("No predictions yet. Run 'scan' or 'predict' first.")
        return

    # Sort by absolute edge
    predictions.sort(key=lambda p: abs(p.predicted_prob - p.market_prob), reverse=True)

    print(f"\n{'Market':<50} {'Predict':>8} {'Market':>8} {'Edge':>8} {'Signal':>10} {'Rel':>6}")
    print("-" * 96)

    for p in predictions:
        edge = p.predicted_prob - p.market_prob
        if abs(edge) < min_edge:
            continue
        question = p.question[:48] + ".." if len(p.question) > 50 else p.question
        print(f"{question:<50} {p.predicted_prob:>7.1%} {p.market_prob:>7.1%} {edge:>+7.1%} {p.signal:>10} {p.reliability:>6}")

    print()


@cli.command()
def calibrate():
    """Update calibration curve from resolved predictions."""
    from polymarket_predictor.calibrator.calibrate import Calibrator

    calibrator = Calibrator()
    report = calibrator.build_calibration()

    if not report.bins:
        print("Not enough matched predictions for calibration. Need at least 10 resolved markets.")
        return

    print(f"\nCalibration Report ({report.total_predictions} matched predictions)")
    print(f"Brier Score: {report.brier_score:.4f}")
    print(f"Mean Calibration Error: {report.calibration_error:.4f}")
    print(f"\n{'Bin':>10} {'Predicted':>10} {'Actual':>10} {'Count':>8}")
    print("-" * 42)
    for b in report.bins:
        print(f"{b.bin_start:.0%}-{b.bin_end:.0%}  {b.predicted_mean:>9.1%} {b.actual_rate:>9.1%} {b.count:>8}")
    print()


@cli.command()
@click.option("--count", default=50, help="Number of resolved markets to backtest")
def backtest(count):
    """Run backtest against resolved Polymarket markets."""
    asyncio.run(_backtest(count))


async def _backtest(count: int):
    from polymarket_predictor.scrapers.polymarket import PolymarketScraper
    from polymarket_predictor.scrapers.news import NewsAggregator
    from polymarket_predictor.orchestrator.pipeline import MiroFishPipeline
    from polymarket_predictor.seeds.generator import SeedGenerator
    from polymarket_predictor.orchestrator.prompts import get_simulation_prompt
    from polymarket_predictor.parser.prediction import PredictionParser
    from polymarket_predictor.calibrator.history import PredictionHistory, PredictionRecord, ResolutionRecord

    scraper = PolymarketScraper()
    news = NewsAggregator()
    pipeline = MiroFishPipeline()
    seed_gen = SeedGenerator()
    parser = PredictionParser()
    history = PredictionHistory()

    try:
        logger.info(f"Fetching {count} resolved markets for backtesting...")
        markets = await scraper.get_resolved_markets(limit=count)
        logger.info(f"Found {len(markets)} resolved markets")

        correct = 0
        total = 0
        brier_sum = 0.0

        for i, market in enumerate(markets):
            try:
                logger.info(f"[{i+1}/{len(markets)}] {market.question[:60]}...")

                # Single variant for speed during backtest
                articles = await news.search_articles(market.question, max_results=3)
                seed_path = seed_gen.generate_seed(market, articles, "balanced")
                prompt = get_simulation_prompt(market.question, market.category)
                report = await pipeline.run(seed_path, prompt, max_rounds=10)

                report_text = report.get("markdown_content", "") or str(report.get("sections", {}))
                prediction = await parser.parse(report_text, market.question)

                # Check resolution
                resolution = market.resolution or ""
                actual = 1 if resolution.lower() in ("yes", "up") else 0

                brier = (prediction.probability - actual) ** 2
                brier_sum += brier
                total += 1

                predicted_yes = prediction.probability > 0.5
                if predicted_yes == (actual == 1):
                    correct += 1

                logger.info(f"  Predicted: {prediction.probability:.1%}, Actual: {resolution}, Brier: {brier:.4f}")

                # Log to history
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

        if total > 0:
            print(f"\n{'='*50}")
            print(f"  BACKTEST RESULTS ({total} markets)")
            print(f"{'='*50}")
            print(f"  Accuracy:    {correct/total:.1%} ({correct}/{total})")
            print(f"  Brier Score: {brier_sum/total:.4f}")
            print(f"{'='*50}\n")

    finally:
        await scraper.close()
        await news.close()
        await pipeline.close()


@cli.command()
def history():
    """Show prediction history summary."""
    from polymarket_predictor.calibrator.history import PredictionHistory

    h = PredictionHistory()
    predictions = h.get_predictions()
    resolutions = h.get_resolutions()

    print(f"\nPrediction History")
    print(f"  Total predictions: {len(predictions)}")
    print(f"  Total resolutions: {len(resolutions)}")

    if predictions:
        buy_yes = sum(1 for p in predictions if p.signal == "BUY_YES")
        buy_no = sum(1 for p in predictions if p.signal == "BUY_NO")
        skip = sum(1 for p in predictions if p.signal == "SKIP")
        print(f"  Signals: BUY_YES={buy_yes}, BUY_NO={buy_no}, SKIP={skip}")

    print()


if __name__ == "__main__":
    cli()
