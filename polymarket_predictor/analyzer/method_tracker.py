"""Track prediction method accuracy and self-adjust blending weights.

Every prediction stores both the LLM and quantitative probability.
When a market resolves, we score both methods and adjust the blend.

The engine becomes self-aware: it learns which method to trust more
based on actual outcomes.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PredictionComparison:
    """A single prediction with both method outputs + outcome."""
    market_id: str
    question: str
    market_odds: float

    # Method outputs
    llm_prediction: float          # From report verdict
    quant_prediction: float        # From simulation analyzer
    combined_prediction: float     # Blended

    # Weights used
    llm_weight: float
    quant_weight: float

    # Metadata
    simulation_id: str = ""
    total_agents: int = 0
    total_interactions: int = 0
    consensus_strength: float = 0.0
    timestamp: str = ""

    # Outcome (filled when market resolves)
    resolved: bool = False
    outcome_yes: Optional[bool] = None
    resolved_at: str = ""

    # Scoring (filled when resolved)
    llm_correct: Optional[bool] = None       # Was LLM on the right side?
    quant_correct: Optional[bool] = None     # Was quant on the right side?
    combined_correct: Optional[bool] = None  # Was combined on the right side?
    llm_brier: Optional[float] = None        # Brier score (lower = better)
    quant_brier: Optional[float] = None
    combined_brier: Optional[float] = None


@dataclass
class MethodPerformance:
    """Aggregated performance of a prediction method."""
    method: str  # "llm", "quant", "combined"
    total_predictions: int = 0
    resolved_predictions: int = 0
    correct: int = 0
    accuracy: float = 0.0
    mean_brier: float = 1.0  # Lower is better
    mean_edge_when_correct: float = 0.0
    mean_edge_when_wrong: float = 0.0


class MethodTracker:
    """Track and compare LLM vs Quantitative prediction performance.

    Stores every prediction comparison to JSONL.
    When markets resolve, scores both methods.
    Adjusts blending weights based on which method is performing better.
    """

    DEFAULT_LLM_WEIGHT = 0.25    # Was 0.40 — WEEX 200-agent study: organic discourse 3x more accurate
    DEFAULT_QUANT_WEIGHT = 0.75  # Was 0.60 — quantitative analyzer gets 75% weight
    MIN_WEIGHT = 0.15  # Never go below 15% for either method
    MAX_WEIGHT = 0.85  # Never go above 85% for either method
    MIN_RESOLVED_FOR_ADJUSTMENT = 10  # Need 10+ resolved before adjusting

    def __init__(self, data_dir: Path = None):
        from polymarket_predictor.config import DATA_DIR
        self._dir = data_dir or DATA_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._comparisons_file = self._dir / "method_comparisons.jsonl"
        self._weights_file = self._dir / "method_weights.json"
        self._llm_weight, self._quant_weight = self._load_weights()

    @property
    def llm_weight(self) -> float:
        return self._llm_weight

    @property
    def quant_weight(self) -> float:
        return self._quant_weight

    def _load_weights(self) -> tuple[float, float]:
        """Load weights from disk, or use defaults."""
        if self._weights_file.exists():
            try:
                data = json.loads(self._weights_file.read_text())
                lw = data.get("llm_weight", self.DEFAULT_LLM_WEIGHT)
                qw = data.get("quant_weight", self.DEFAULT_QUANT_WEIGHT)
                logger.info("Loaded method weights: LLM=%.2f, Quant=%.2f", lw, qw)
                return lw, qw
            except Exception as e:
                logger.warning("Failed to load weights: %s", e)
        return self.DEFAULT_LLM_WEIGHT, self.DEFAULT_QUANT_WEIGHT

    def _save_weights(self):
        """Persist current weights."""
        data = {
            "llm_weight": round(self._llm_weight, 4),
            "quant_weight": round(self._quant_weight, 4),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._weights_file.write_text(json.dumps(data, indent=2))

    def blend(self, llm_pred: float, quant_pred: float) -> float:
        """Blend two predictions using current learned weights."""
        return llm_pred * self._llm_weight + quant_pred * self._quant_weight

    def log_prediction(self, comparison: PredictionComparison):
        """Log a new prediction comparison."""
        comparison.llm_weight = self._llm_weight
        comparison.quant_weight = self._quant_weight
        comparison.timestamp = comparison.timestamp or time.strftime("%Y-%m-%dT%H:%M:%S")

        with open(self._comparisons_file, "a") as f:
            f.write(json.dumps(asdict(comparison)) + "\n")

        logger.info(
            "Logged comparison: LLM=%.1f%% Quant=%.1f%% Combined=%.1f%% (weights: %.0f/%.0f) -> %s",
            comparison.llm_prediction * 100, comparison.quant_prediction * 100,
            comparison.combined_prediction * 100,
            self._llm_weight * 100, self._quant_weight * 100,
            comparison.question[:50],
        )

    def resolve_prediction(self, market_id: str, outcome_yes: bool) -> Optional[PredictionComparison]:
        """Score a prediction when its market resolves.

        Reads all comparisons, finds the matching one, scores it,
        rewrites the file with the scored entry.
        Returns the scored comparison, or None if not found.
        """
        comparisons = self._load_all()
        found = None

        for comp in comparisons:
            if comp.get("market_id") == market_id and not comp.get("resolved"):
                comp["resolved"] = True
                comp["outcome_yes"] = outcome_yes
                comp["resolved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

                # Score each method
                # "Correct" = prediction was on the right side of 50%
                # For YES outcome: prediction > 50% is correct
                # For NO outcome: prediction < 50% is correct
                for method, pred_key in [("llm", "llm_prediction"), ("quant", "quant_prediction"), ("combined", "combined_prediction")]:
                    pred = comp.get(pred_key, 0.5)
                    if outcome_yes:
                        comp[f"{method}_correct"] = pred > 0.5
                        comp[f"{method}_brier"] = (pred - 1.0) ** 2
                    else:
                        comp[f"{method}_correct"] = pred < 0.5
                        comp[f"{method}_brier"] = (pred - 0.0) ** 2

                found = comp
                break

        if found:
            # Rewrite file with scored entry
            self._save_all(comparisons)

            logger.info(
                "Resolved %s: LLM %s (%.1f%%), Quant %s (%.1f%%), Combined %s (%.1f%%)",
                market_id,
                "CORRECT" if found["llm_correct"] else "WRONG", found["llm_prediction"] * 100,
                "CORRECT" if found["quant_correct"] else "WRONG", found["quant_prediction"] * 100,
                "CORRECT" if found["combined_correct"] else "WRONG", found["combined_prediction"] * 100,
            )

            # Check if we should adjust weights
            self._maybe_adjust_weights()

            return PredictionComparison(**{k: v for k, v in found.items() if k in PredictionComparison.__dataclass_fields__})

        return None

    def _maybe_adjust_weights(self):
        """Adjust blending weights based on resolved prediction performance.

        The method with lower Brier score (better calibration) gets more weight.
        Adjustments are gradual (max 5% per adjustment).
        """
        comparisons = self._load_all()
        resolved = [c for c in comparisons if c.get("resolved")]

        if len(resolved) < self.MIN_RESOLVED_FOR_ADJUSTMENT:
            logger.info("Only %d resolved (need %d) -- not adjusting weights yet",
                       len(resolved), self.MIN_RESOLVED_FOR_ADJUSTMENT)
            return

        # Calculate Brier scores for each method
        llm_briers = [c["llm_brier"] for c in resolved if c.get("llm_brier") is not None]
        quant_briers = [c["quant_brier"] for c in resolved if c.get("quant_brier") is not None]

        if not llm_briers or not quant_briers:
            return

        mean_llm_brier = sum(llm_briers) / len(llm_briers)
        mean_quant_brier = sum(quant_briers) / len(quant_briers)

        # Lower Brier = better. Adjust weight toward the better method.
        brier_diff = mean_llm_brier - mean_quant_brier  # Positive = quant is better

        # Gradual adjustment: max 5% shift per adjustment
        adjustment = max(-0.05, min(0.05, brier_diff * 0.3))

        old_llm = self._llm_weight
        old_quant = self._quant_weight

        self._quant_weight = max(self.MIN_WEIGHT, min(self.MAX_WEIGHT, self._quant_weight + adjustment))
        self._llm_weight = 1.0 - self._quant_weight

        # Clamp
        self._llm_weight = max(self.MIN_WEIGHT, min(self.MAX_WEIGHT, self._llm_weight))
        self._quant_weight = 1.0 - self._llm_weight

        self._save_weights()

        if abs(adjustment) > 0.001:
            logger.info(
                "Adjusted weights: LLM %.0f%%->%.0f%%, Quant %.0f%%->%.0f%% "
                "(LLM Brier=%.3f, Quant Brier=%.3f, based on %d resolved)",
                old_llm * 100, self._llm_weight * 100,
                old_quant * 100, self._quant_weight * 100,
                mean_llm_brier, mean_quant_brier, len(resolved),
            )

            # Log to decision ledger
            try:
                from polymarket_predictor.ledger.decision_ledger import DecisionLedger
                from polymarket_predictor.config import DATA_DIR
                ledger = DecisionLedger(data_dir=DATA_DIR)
                ledger.log(
                    entry_type="PARAM_CHANGED",
                    question="Method blending weights",
                    explanation=(
                        f"Auto-adjusted: LLM {old_llm:.0%}->{self._llm_weight:.0%}, "
                        f"Quant {old_quant:.0%}->{self._quant_weight:.0%}. "
                        f"LLM Brier={mean_llm_brier:.3f}, Quant Brier={mean_quant_brier:.3f}, "
                        f"based on {len(resolved)} resolved predictions."
                    ),
                    data={
                        "old_llm_weight": old_llm,
                        "new_llm_weight": self._llm_weight,
                        "old_quant_weight": old_quant,
                        "new_quant_weight": self._quant_weight,
                        "llm_brier": mean_llm_brier,
                        "quant_brier": mean_quant_brier,
                        "resolved_count": len(resolved),
                    },
                )
            except Exception:
                pass

    def get_performance(self) -> dict:
        """Get aggregated performance metrics for each method."""
        comparisons = self._load_all()
        resolved = [c for c in comparisons if c.get("resolved")]

        result = {
            "total_predictions": len(comparisons),
            "resolved_predictions": len(resolved),
            "unresolved": len(comparisons) - len(resolved),
            "current_weights": {
                "llm": round(self._llm_weight, 4),
                "quant": round(self._quant_weight, 4),
            },
            "methods": {},
        }

        for method in ["llm", "quant", "combined"]:
            correct = sum(1 for c in resolved if c.get(f"{method}_correct"))
            briers = [c[f"{method}_brier"] for c in resolved if c.get(f"{method}_brier") is not None]

            perf = MethodPerformance(
                method=method,
                total_predictions=len(comparisons),
                resolved_predictions=len(resolved),
                correct=correct,
                accuracy=correct / len(resolved) if resolved else 0,
                mean_brier=sum(briers) / len(briers) if briers else 1.0,
            )

            result["methods"][method] = {
                "accuracy": round(perf.accuracy, 4),
                "correct": perf.correct,
                "total_resolved": perf.resolved_predictions,
                "mean_brier": round(perf.mean_brier, 4),
            }

        # Comparison summary
        if resolved:
            llm_acc = result["methods"]["llm"]["accuracy"]
            quant_acc = result["methods"]["quant"]["accuracy"]
            combined_acc = result["methods"]["combined"]["accuracy"]

            best = "combined"
            best_acc = combined_acc
            if llm_acc > best_acc:
                best, best_acc = "llm", llm_acc
            if quant_acc > best_acc:
                best, best_acc = "quant", quant_acc

            result["best_method"] = best
            result["recommendation"] = (
                f"{best} is currently most accurate ({best_acc:.0%}). "
                f"Weights auto-adjusting based on Brier scores."
            )
        else:
            result["best_method"] = "unknown"
            result["recommendation"] = "No resolved predictions yet. Need market outcomes to compare methods."

        return result

    def get_recent_comparisons(self, limit: int = 20) -> list[dict]:
        """Get recent comparisons for display."""
        comparisons = self._load_all()
        return comparisons[-limit:]

    def _load_all(self) -> list[dict]:
        """Load all comparisons from JSONL."""
        if not self._comparisons_file.exists():
            return []
        comparisons = []
        for line in self._comparisons_file.read_text().strip().split("\n"):
            if line.strip():
                try:
                    comparisons.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return comparisons

    def _save_all(self, comparisons: list[dict]):
        """Rewrite all comparisons to JSONL."""
        with open(self._comparisons_file, "w") as f:
            for comp in comparisons:
                f.write(json.dumps(comp) + "\n")
