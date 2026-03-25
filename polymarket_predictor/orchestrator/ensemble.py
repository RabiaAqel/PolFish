from dataclasses import dataclass, field
import asyncio
import logging
from pathlib import Path

from polymarket_predictor.scrapers.polymarket import Market
from polymarket_predictor.scrapers.news import Article, NewsAggregator
from polymarket_predictor.seeds.generator import SeedGenerator
from polymarket_predictor.orchestrator.pipeline import MiroFishPipeline
from polymarket_predictor.orchestrator.prompts import get_simulation_prompt
from polymarket_predictor.parser.prediction import PredictionParser, Prediction
from polymarket_predictor.config import DEFAULT_MAX_ROUNDS, DEFAULT_VARIANTS

logger = logging.getLogger(__name__)

VARIANT_CONFIGS = [
    {"name": "balanced", "seed_variant": "balanced", "max_rounds": DEFAULT_MAX_ROUNDS},
    {"name": "news_heavy", "seed_variant": "news_heavy", "max_rounds": DEFAULT_MAX_ROUNDS},
    {"name": "contrarian", "seed_variant": "contrarian", "max_rounds": DEFAULT_MAX_ROUNDS},
]

@dataclass
class EnsemblePrediction:
    market_id: str
    market_question: str
    mean_probability: float         # Weighted average across variants
    std_deviation: float            # Disagreement between variants
    individual_predictions: list[Prediction]
    reliability: str                # "high", "medium", "low" based on std_dev
    market_probability: float       # Current Polymarket price
    edge: float                     # mean_probability - market_probability
    signal: str                     # "BUY_YES", "BUY_NO", "SKIP"

class EnsemblePredictor:
    def __init__(self, num_variants: int = DEFAULT_VARIANTS):
        self.num_variants = min(num_variants, len(VARIANT_CONFIGS))
        self.seed_generator = SeedGenerator()
        self.parser = PredictionParser()
        self.pipeline = MiroFishPipeline()

    async def predict(self, market: Market, articles: list[Article]) -> EnsemblePrediction:
        """Run N simulation variants for a market and aggregate predictions."""
        variants = VARIANT_CONFIGS[:self.num_variants]
        predictions = []

        prompt = get_simulation_prompt(market.question, market.category)

        # Run variants sequentially (MiroFish can only handle one sim at a time)
        for variant in variants:
            try:
                logger.info(f"Running variant '{variant['name']}' for: {market.question[:60]}...")
                seed_path = self.seed_generator.generate_seed(market, articles, variant["seed_variant"])
                report = await self.pipeline.run(seed_path, prompt, variant["max_rounds"])
                report_text = report.get("markdown_content", "") or str(report.get("sections", {}))
                prediction = await self.parser.parse(report_text, market.question)
                predictions.append(prediction)
                logger.info(f"Variant '{variant['name']}': probability={prediction.probability:.2f}")
            except Exception as e:
                logger.error(f"Variant '{variant['name']}' failed: {e}")
                continue

        if not predictions:
            raise ValueError(f"All variants failed for market: {market.question}")

        return self._aggregate(market, predictions)

    def _aggregate(self, market: Market, predictions: list[Prediction]) -> EnsemblePrediction:
        """Aggregate individual predictions into ensemble result."""
        import statistics

        probs = [p.probability for p in predictions]
        mean_prob = statistics.mean(probs)
        std_dev = statistics.stdev(probs) if len(probs) > 1 else 0.0

        # Determine reliability
        if std_dev < 0.08:
            reliability = "high"
        elif std_dev < 0.15:
            reliability = "medium"
        else:
            reliability = "low"

        # Get market's current Yes price
        market_prob = next((o["price"] for o in market.outcomes if o["name"].lower() in ("yes", "up")), 0.5)

        edge = mean_prob - market_prob

        # Determine signal
        min_edge = 0.10
        if abs(edge) < min_edge or reliability == "low":
            signal = "SKIP"
        elif edge > 0:
            signal = "BUY_YES"
        else:
            signal = "BUY_NO"

        return EnsemblePrediction(
            market_id=market.id,
            market_question=market.question,
            mean_probability=mean_prob,
            std_deviation=std_dev,
            individual_predictions=predictions,
            reliability=reliability,
            market_probability=market_prob,
            edge=edge,
            signal=signal,
        )

    async def close(self):
        await self.pipeline.close()
