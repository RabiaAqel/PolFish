"""Lightweight persistent context store for market intelligence.

Instead of a full vector DB (Chroma), this stores structured market
context as JSON that accumulates over time. Each prediction adds to
the knowledge base, building institutional memory.

Future upgrade path: swap JSON store for Chroma when needed.
"""

import json
import logging
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class MarketContext:
    """Context record for a single market prediction."""
    market_id: str
    question: str
    category: str
    market_odds_at_prediction: float
    our_prediction: float
    key_factors: list[str] = field(default_factory=list)
    news_summary: str = ""
    agent_consensus: str = ""  # "bullish", "bearish", "divided"
    outcome: str = ""  # "yes", "no", "pending"
    was_correct: bool | None = None
    timestamp: str = ""


class ContextStore:
    """Persistent store of market intelligence that grows over time.

    Used to:
    1. Avoid researching the same topic twice (reuse context)
    2. Build historical patterns ("last 3 Iran predictions were wrong")
    3. Provide cross-market context ("oil is correlated with geopolitics")
    """

    def __init__(self, data_dir: Path | None = None):
        from polymarket_predictor.config import DATA_DIR
        self._dir = data_dir or DATA_DIR
        self._file = self._dir / "context_store.jsonl"

    def add(self, context: MarketContext):
        """Add a new context record."""
        context.timestamp = context.timestamp or time.strftime("%Y-%m-%dT%H:%M:%S")
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._file, "a") as f:
            f.write(json.dumps(asdict(context)) + "\n")

    def get_by_category(self, category: str, limit: int = 10) -> list[dict]:
        """Get recent context records for a category."""
        records = self._load_all()
        filtered = [r for r in records if r.get("category") == category]
        return filtered[-limit:]

    def get_related(self, question: str, limit: int = 5) -> list[dict]:
        """Find context records related to a question (simple keyword matching).

        Future: replace with vector similarity search.
        """
        records = self._load_all()
        question_words = set(question.lower().split())

        scored = []
        for r in records:
            record_words = set(r.get("question", "").lower().split())
            overlap = len(question_words & record_words)
            if overlap >= 2:
                scored.append((overlap, r))

        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:limit]]

    def get_accuracy_by_category(self) -> dict:
        """Get prediction accuracy per category."""
        records = self._load_all()
        stats: dict[str, dict[str, int]] = {}
        for r in records:
            cat = r.get("category", "other")
            if cat not in stats:
                stats[cat] = {"total": 0, "correct": 0, "pending": 0}
            if r.get("outcome") == "pending" or r.get("was_correct") is None:
                stats[cat]["pending"] += 1
            else:
                stats[cat]["total"] += 1
                if r.get("was_correct"):
                    stats[cat]["correct"] += 1

        result = {}
        for cat, s in stats.items():
            result[cat] = {
                "total": s["total"],
                "correct": s["correct"],
                "accuracy": s["correct"] / s["total"] if s["total"] > 0 else 0,
                "pending": s["pending"],
            }
        return result

    def get_track_record_summary(self, category: str) -> str:
        """Generate a human-readable track record for a category.

        Used in the Prediction Verdict prompt to give the LLM context
        about how well we've predicted this category before.
        """
        accuracy = self.get_accuracy_by_category()
        cat_stats = accuracy.get(category, {})

        if cat_stats.get("total", 0) < 3:
            return f"Limited track record for {category} markets ({cat_stats.get('total', 0)} resolved predictions)."

        acc = cat_stats.get("accuracy", 0)
        total = cat_stats["total"]
        correct = cat_stats["correct"]

        if acc >= 0.60:
            return f"Strong track record on {category}: {correct}/{total} correct ({acc:.0%}). Our predictions in this category tend to be reliable."
        elif acc >= 0.50:
            return f"Mixed track record on {category}: {correct}/{total} correct ({acc:.0%}). Predictions in this category are roughly coin-flip quality."
        else:
            return f"Weak track record on {category}: {correct}/{total} correct ({acc:.0%}). Consider being less confident in {category} predictions."

    def _load_all(self) -> list[dict]:
        if not self._file.exists():
            return []
        records = []
        for line in self._file.read_text().strip().split("\n"):
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
        return records
