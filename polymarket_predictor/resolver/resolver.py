"""Resolve Polymarket outcomes and update calibration data.

This module checks whether open positions have resolved on Polymarket,
records outcomes in the prediction history, updates the paper portfolio,
and rebuilds the calibration curve to improve future predictions.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from polymarket_predictor.calibrator.calibrate import Calibrator, CalibrationReport
from polymarket_predictor.calibrator.history import (
    PredictionHistory,
    ResolutionRecord,
)
from polymarket_predictor.config import DATA_DIR
from polymarket_predictor.paper_trader.portfolio import PaperPortfolio
from polymarket_predictor.scrapers.polymarket import PolymarketScraper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ResolutionResult:
    """Outcome of resolving a single market position."""

    market_id: str
    question: str
    outcome_yes: bool
    pnl: float
    resolved_at: str


@dataclass
class OptimizationSuggestion:
    """A suggested parameter change based on performance analysis."""

    parameter: str
    current_value: Any
    suggested_value: Any
    reason: str


# ---------------------------------------------------------------------------
# MarketResolver
# ---------------------------------------------------------------------------


class MarketResolver:
    """Check Polymarket for resolved markets and settle paper-trading positions.

    Parameters
    ----------
    portfolio:
        The paper-trading portfolio holding open positions.
    calibrator:
        Calibration engine used to adjust raw probabilities.
    history:
        Prediction/resolution history store.
    """

    def __init__(
        self,
        portfolio: PaperPortfolio,
        calibrator: Calibrator,
        history: PredictionHistory,
    ) -> None:
        self._portfolio = portfolio
        self._calibrator = calibrator
        self._history = history

    # -- Public API ----------------------------------------------------------

    async def check_resolutions(self) -> list[ResolutionResult]:
        """Check all open positions and resolve any that have settled.

        Workflow for each open position:
        1. Fetch the market from Polymarket by slug.
        2. If the market is closed **and** carries a resolution string,
           treat it as resolved.
        3. Update the portfolio and record the resolution in history.

        Returns
        -------
        list[ResolutionResult]
            Newly resolved positions with their P&L.
        """
        open_positions = self._portfolio.get_open_positions()
        if not open_positions:
            logger.info("No open positions to check")
            return []

        logger.info("Checking %d open positions for resolutions", len(open_positions))
        resolved: list[ResolutionResult] = []

        async with PolymarketScraper() as scraper:
            for position in open_positions:
                try:
                    result = await self._check_single(
                        scraper,
                        market_id=position.market_id,
                        slug=position.slug,
                        question=getattr(position, "question", ""),
                    )
                    if result is not None:
                        resolved.append(result)
                except Exception:
                    logger.exception(
                        "Error checking resolution for market %s",
                        position.market_id,
                    )

        if resolved:
            logger.info(
                "Resolved %d positions (total P&L: %.2f)",
                len(resolved),
                sum(r.pnl for r in resolved),
            )
        else:
            logger.info("No new resolutions found")

        return resolved

    async def resolve_single(
        self, market_id: str, slug: str
    ) -> ResolutionResult | None:
        """Check and resolve a single market by *market_id* and *slug*.

        Returns
        -------
        ResolutionResult | None
            The resolution result, or ``None`` if the market has not resolved.
        """
        async with PolymarketScraper() as scraper:
            return await self._check_single(scraper, market_id, slug)

    def get_resolution_summary(self) -> dict[str, Any]:
        """Return an overview of resolution performance.

        Keys
        ----
        total_resolved : int
        total_open : int
        recent_resolutions : list[dict]
            Last 10 resolutions.
        accuracy_by_category : dict[str, dict]
            Per-category correct/total/accuracy.
        pnl_by_category : dict[str, float]
            Cumulative P&L per category.
        """
        resolutions = self._history.get_resolutions()
        predictions = {r.market_id: r for r in self._history.get_predictions()}
        open_positions = self._portfolio.get_open_positions()

        # --- recent resolutions (last 10) ---
        recent = []
        for res in resolutions[-10:]:
            pred = predictions.get(res.market_id)
            recent.append(
                {
                    "market_id": res.market_id,
                    "question": res.question,
                    "outcome": res.outcome,
                    "resolved_at": res.resolved_at,
                    "predicted_prob": pred.predicted_prob if pred else None,
                }
            )

        # --- accuracy & P&L by category ---
        accuracy_by_category: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"correct": 0, "total": 0, "accuracy": 0.0}
        )
        pnl_by_category: dict[str, float] = defaultdict(float)

        matched = self._history.get_matched_records()
        for pred, res in matched:
            # Determine category from the prediction record if available,
            # otherwise fall back to "unknown".
            category = getattr(pred, "category", None) or "unknown"

            accuracy_by_category[category]["total"] += 1

            predicted_yes = pred.predicted_prob >= 0.5
            actual_yes = res.outcome_binary == 1
            if predicted_yes == actual_yes:
                accuracy_by_category[category]["correct"] += 1

            # Simplified P&L: gain if correct, loss otherwise.
            pnl = abs(pred.predicted_prob - pred.market_prob) if predicted_yes == actual_yes else -abs(pred.predicted_prob - pred.market_prob)
            pnl_by_category[category] += pnl

        # Compute accuracy percentages
        for cat_data in accuracy_by_category.values():
            total = cat_data["total"]
            cat_data["accuracy"] = (
                cat_data["correct"] / total if total > 0 else 0.0
            )

        return {
            "total_resolved": len(resolutions),
            "total_open": len(open_positions),
            "recent_resolutions": recent,
            "accuracy_by_category": dict(accuracy_by_category),
            "pnl_by_category": dict(pnl_by_category),
        }

    # -- Internals -----------------------------------------------------------

    async def _check_single(
        self,
        scraper: PolymarketScraper,
        market_id: str,
        slug: str,
        question: str = "",
    ) -> ResolutionResult | None:
        """Fetch a market and resolve it if closed with a resolution."""
        market = await scraper.get_market_by_slug(slug)
        if market is None:
            logger.warning("Market not found for slug=%s", slug)
            return None

        if not market.closed:
            return None

        # Determine binary outcome from resolution string or price
        outcome_yes = None
        if market.resolution and market.resolution.strip():
            outcome_yes = market.resolution.strip().lower() in ("yes", "up")
        elif market.outcomes:
            # Infer from outcome prices — price=1.0 means that outcome won
            for o in market.outcomes:
                if isinstance(o, dict):
                    name = o.get("name", "").lower()
                    price = float(o.get("price", 0))
                    if price >= 0.95 and name in ("yes", "up"):
                        outcome_yes = True
                        break
                    elif price >= 0.95 and name in ("no", "down"):
                        outcome_yes = False
                        break
                    elif price <= 0.05 and name in ("yes", "up"):
                        outcome_yes = False
                        break
                    elif price <= 0.05 and name in ("no", "down"):
                        outcome_yes = True
                        break

        if outcome_yes is None:
            logger.debug("Market %s closed but resolution unclear", slug)
            return None
        outcome_str = "Yes" if outcome_yes else "No"

        # Update portfolio — resolve_bet returns a list of BetRecord objects
        resolved_bets = self._portfolio.resolve_bet(market_id, outcome_yes)
        pnl = sum(b.pnl for b in resolved_bets) if resolved_bets else 0.0

        # Record resolution in history
        resolved_at = datetime.utcnow().isoformat()
        resolution_record = ResolutionRecord(
            market_id=market_id,
            question=question or market.question,
            outcome=outcome_str,
            outcome_binary=1 if outcome_yes else 0,
            resolved_at=resolved_at,
        )
        self._history.log_resolution(resolution_record)

        logger.info(
            "Resolved market %s (%s) -> %s  P&L=%.4f",
            market_id,
            slug,
            outcome_str,
            pnl,
        )

        # Score method predictions for this resolved market
        try:
            from polymarket_predictor.analyzer.method_tracker import MethodTracker
            tracker = MethodTracker()
            tracker.resolve_prediction(market_id, outcome_yes)
        except Exception:
            pass

        return ResolutionResult(
            market_id=market_id,
            question=question or market.question,
            outcome_yes=outcome_yes,
            pnl=pnl,
            resolved_at=resolved_at,
        )


# ---------------------------------------------------------------------------
# CalibrationUpdater
# ---------------------------------------------------------------------------


class CalibrationUpdater:
    """Rebuild calibration data after resolutions and suggest improvements.

    Parameters
    ----------
    calibrator:
        The calibration engine whose curve will be rebuilt.
    history:
        Prediction/resolution history used as the data source.
    """

    def __init__(self, calibrator: Calibrator, history: PredictionHistory) -> None:
        self._calibrator = calibrator
        self._history = history

    def update(self) -> dict[str, Any]:
        """Rebuild the calibration curve from all historical data.

        Should be called after each batch of resolutions so that future
        probability estimates benefit from the latest outcomes.

        Returns
        -------
        dict
            Calibration statistics with keys ``brier_score``,
            ``calibration_error``, and ``bins``.
        """
        report: CalibrationReport = self._calibrator.build_calibration()

        stats = {
            "brier_score": report.brier_score,
            "calibration_error": report.calibration_error,
            "total_predictions": report.total_predictions,
            "bins": [
                {
                    "range": f"{b.bin_start:.1f}-{b.bin_end:.1f}",
                    "predicted_mean": round(b.predicted_mean, 4),
                    "actual_rate": round(b.actual_rate, 4),
                    "count": b.count,
                }
                for b in report.bins
            ],
        }

        logger.info(
            "Calibration updated: Brier=%.4f, CalError=%.4f, N=%d",
            report.brier_score,
            report.calibration_error,
            report.total_predictions,
        )
        return stats

    def get_optimization_suggestions(self) -> list[dict[str, Any]]:
        """Analyze historical performance and suggest parameter adjustments.

        Inspects the calibration curve and prediction accuracy to produce
        actionable suggestions for tuning the prediction pipeline.

        Returns
        -------
        list[dict]
            Each dict has keys: ``parameter``, ``current_value``,
            ``suggested_value``, ``reason``.
        """
        suggestions: list[dict[str, Any]] = []
        matched = self._history.get_matched_records()

        if len(matched) < 10:
            logger.info(
                "Not enough matched records (%d) to generate suggestions",
                len(matched),
            )
            return suggestions

        # --- 1. Over/under-prediction bias ---
        errors = [
            pred.predicted_prob - res.outcome_binary for pred, res in matched
        ]
        mean_error = sum(errors) / len(errors)

        if mean_error > 0.05:
            suggestions.append(
                {
                    "parameter": "probability_bias",
                    "current_value": 0.0,
                    "suggested_value": round(-mean_error, 3),
                    "reason": (
                        f"Predictions are systematically too high by "
                        f"{mean_error:.3f} on average. Consider lowering "
                        f"probability estimates."
                    ),
                }
            )
        elif mean_error < -0.05:
            suggestions.append(
                {
                    "parameter": "probability_bias",
                    "current_value": 0.0,
                    "suggested_value": round(-mean_error, 3),
                    "reason": (
                        f"Predictions are systematically too low by "
                        f"{abs(mean_error):.3f} on average. Consider raising "
                        f"probability estimates."
                    ),
                }
            )

        # --- 2. Per-category performance ---
        category_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"correct": 0, "total": 0}
        )
        for pred, res in matched:
            category = getattr(pred, "category", None) or "unknown"
            category_stats[category]["total"] += 1
            predicted_yes = pred.predicted_prob >= 0.5
            actual_yes = res.outcome_binary == 1
            if predicted_yes == actual_yes:
                category_stats[category]["correct"] += 1

        for category, stats in category_stats.items():
            if stats["total"] >= 5:
                accuracy = stats["correct"] / stats["total"]
                if accuracy < 0.4:
                    suggestions.append(
                        {
                            "parameter": "category_exclusion",
                            "current_value": [],
                            "suggested_value": [category],
                            "reason": (
                                f"Category '{category}' has only "
                                f"{accuracy:.0%} accuracy over "
                                f"{stats['total']} predictions. Consider "
                                f"avoiding or down-weighting this category."
                            ),
                        }
                    )

        # --- 3. Edge threshold analysis ---
        edges = [
            abs(pred.predicted_prob - pred.market_prob) for pred, _ in matched
        ]
        correct_flags = [
            (pred.predicted_prob >= 0.5) == (res.outcome_binary == 1)
            for pred, res in matched
        ]

        # Split into small-edge and large-edge groups
        median_edge = sorted(edges)[len(edges) // 2]
        small_edge_correct = [
            c for e, c in zip(edges, correct_flags) if e <= median_edge
        ]
        large_edge_correct = [
            c for e, c in zip(edges, correct_flags) if e > median_edge
        ]

        if small_edge_correct and large_edge_correct:
            small_acc = sum(small_edge_correct) / len(small_edge_correct)
            large_acc = sum(large_edge_correct) / len(large_edge_correct)

            if small_acc < 0.45 and large_acc > small_acc + 0.1:
                from polymarket_predictor.config import MIN_EDGE_THRESHOLD

                suggested_edge = round(median_edge * 1.2, 3)
                suggestions.append(
                    {
                        "parameter": "min_edge_threshold",
                        "current_value": MIN_EDGE_THRESHOLD,
                        "suggested_value": max(suggested_edge, MIN_EDGE_THRESHOLD + 0.02),
                        "reason": (
                            f"Low-edge bets ({small_acc:.0%} accuracy) "
                            f"underperform high-edge bets ({large_acc:.0%}). "
                            f"Raising the minimum edge threshold should "
                            f"filter out unprofitable trades."
                        ),
                    }
                )

        # --- 4. Brier score assessment ---
        report = self._calibrator.build_calibration()
        if report.brier_score > 0.25:
            suggestions.append(
                {
                    "parameter": "ensemble_variants",
                    "current_value": 3,
                    "suggested_value": 5,
                    "reason": (
                        f"Brier score of {report.brier_score:.3f} indicates "
                        f"poor calibration. Increasing ensemble variants may "
                        f"improve prediction quality through better averaging."
                    ),
                }
            )

        logger.info("Generated %d optimization suggestions", len(suggestions))
        return suggestions
