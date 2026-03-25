"""Strategy optimization based on paper trading performance.

Analyzes historical paper trades to tune betting parameters — edge thresholds,
Kelly sizing, category weights, odds ranges, and confidence multipliers.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from polymarket_predictor.config import DATA_DIR

logger = logging.getLogger(__name__)

DEFAULT_STRATEGY_CONFIG: dict[str, Any] = {
    "min_edge_threshold": 0.03,
    "max_bet_pct": 0.05,
    "kelly_factor": 0.25,
    "min_volume": 100,
    "odds_range": [0.10, 0.90],
    "category_weights": {
        # Niche categories — more likely to find edge
        "science": 1.5,
        "world": 1.4,
        "entertainment": 1.3,
        "politics": 1.1,  # niche politics can be good
        # Efficient categories — harder to beat
        "crypto": 0.7,
        "finance": 0.6,
        "sports": 0.5,
    },
    "confidence_multipliers": {"high": 1.0, "medium": 0.6, "low": 0.3},
    "max_markets_per_scan": 15,
    "prefer_deep": False,
    "prefer_niche": True,
    "days_ahead": 14,
    "version": 2,
}


@dataclass
class OptimizationChange:
    """A single parameter change made during optimization."""

    parameter: str
    before: Any
    after: Any
    reason: str


@dataclass
class OptimizationEntry:
    """A log entry for one optimization run."""

    timestamp: str
    changes: list[dict[str, Any]]
    portfolio_snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "changes": self.changes,
            "portfolio_snapshot": self.portfolio_snapshot,
        }


# ---------------------------------------------------------------------------
# StrategyOptimizer
# ---------------------------------------------------------------------------


class StrategyOptimizer:
    """Learns from past paper trades to tune strategy parameters."""

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._config_path = self._data_dir / "strategy.json"
        self._log_path = self._data_dir / "optimization_log.jsonl"

        self._config: dict[str, Any] = self._load_config()

    # -- persistence --------------------------------------------------------

    def _load_config(self) -> dict[str, Any]:
        """Load strategy config from disk, falling back to defaults."""
        if self._config_path.exists():
            try:
                data = json.loads(self._config_path.read_text())
                # Merge with defaults so new keys are always present
                merged = {**DEFAULT_STRATEGY_CONFIG, **data}
                logger.info("Loaded strategy config v%s from %s", merged.get("version"), self._config_path)
                return merged
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load strategy config, using defaults: %s", exc)
        return {**DEFAULT_STRATEGY_CONFIG}

    def get_config(self) -> dict[str, Any]:
        """Return current strategy configuration."""
        return {**self._config}

    def save(self) -> None:
        """Persist current strategy config to strategy.json."""
        self._config_path.write_text(json.dumps(self._config, indent=2))
        logger.info("Saved strategy config v%s to %s", self._config.get("version"), self._config_path)

    def get_optimization_log(self) -> list[dict[str, Any]]:
        """Return full history of optimization runs."""
        if not self._log_path.exists():
            return []
        entries: list[dict[str, Any]] = []
        for line in self._log_path.read_text().strip().split("\n"):
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed optimization log line")
        return entries

    def _append_log(self, entry: OptimizationEntry) -> None:
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    # -- optimization -------------------------------------------------------

    def optimize(
        self,
        portfolio_performance: dict[str, Any],
        calibration_stats: dict[str, Any],
        resolution_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Run all optimization passes and return a summary of changes.

        Parameters
        ----------
        portfolio_performance:
            Dict with keys like ``win_rate``, ``roi``, ``max_drawdown``,
            ``total_pnl``, ``by_category``, ``by_confidence``, ``by_edge``.
        calibration_stats:
            Calibration report data (bins, brier_score, etc.).
        resolution_history:
            List of resolved bet dicts with at least ``market_prob``,
            ``category``, ``confidence``, ``edge``, ``won`` fields.
        """
        changes: list[OptimizationChange] = []

        changes.extend(self._tune_edge_threshold(portfolio_performance))
        changes.extend(self._tune_kelly_factor(portfolio_performance))
        changes.extend(self._tune_category_weights(portfolio_performance, resolution_history))
        changes.extend(self._tune_odds_range(resolution_history))
        changes.extend(self._tune_confidence_multipliers(portfolio_performance, resolution_history))

        if changes:
            self._config["version"] = self._config.get("version", 1) + 1
            self.save()

        change_dicts = [
            {"parameter": c.parameter, "before": c.before, "after": c.after, "reason": c.reason}
            for c in changes
        ]

        self._append_log(
            OptimizationEntry(
                timestamp=datetime.utcnow().isoformat(),
                changes=change_dicts,
                portfolio_snapshot={
                    "win_rate": portfolio_performance.get("win_rate"),
                    "roi": portfolio_performance.get("roi"),
                    "max_drawdown": portfolio_performance.get("max_drawdown"),
                    "total_pnl": portfolio_performance.get("total_pnl"),
                },
            )
        )

        logger.info("Optimization complete: %d changes applied", len(changes))
        return {"changes": change_dicts, "new_version": self._config.get("version")}

    # -- individual tuning passes -------------------------------------------

    def _tune_edge_threshold(self, perf: dict[str, Any]) -> list[OptimizationChange]:
        changes: list[OptimizationChange] = []
        win_rate = perf.get("win_rate", 0.0)
        old = self._config["min_edge_threshold"]

        if win_rate < 0.50:
            new = min(old + 0.01, 0.10)
            if new != old:
                self._config["min_edge_threshold"] = round(new, 4)
                changes.append(OptimizationChange(
                    "min_edge_threshold", old, new,
                    f"Win rate {win_rate:.1%} < 50% — raising edge threshold",
                ))
        elif win_rate > 0.65:
            new = max(old - 0.005, 0.02)
            if new != old:
                self._config["min_edge_threshold"] = round(new, 4)
                changes.append(OptimizationChange(
                    "min_edge_threshold", old, new,
                    f"Win rate {win_rate:.1%} > 65% — lowering edge threshold",
                ))

        return changes

    def _tune_kelly_factor(self, perf: dict[str, Any]) -> list[OptimizationChange]:
        changes: list[OptimizationChange] = []
        max_dd = perf.get("max_drawdown", 0.0)
        roi = perf.get("roi", 0.0)
        old = self._config["kelly_factor"]

        if max_dd > 0.20:
            new = max(old - 0.05, 0.1)
            if new != old:
                self._config["kelly_factor"] = round(new, 4)
                changes.append(OptimizationChange(
                    "kelly_factor", old, new,
                    f"Max drawdown {max_dd:.1%} > 20% — reducing Kelly factor",
                ))
        elif roi > 0.10 and max_dd < 0.10:
            new = min(old + 0.05, 0.5)
            if new != old:
                self._config["kelly_factor"] = round(new, 4)
                changes.append(OptimizationChange(
                    "kelly_factor", old, new,
                    f"ROI {roi:.1%} > 10% with low drawdown {max_dd:.1%} — increasing Kelly factor",
                ))

        return changes

    def _tune_category_weights(
        self, perf: dict[str, Any], history: list[dict[str, Any]]
    ) -> list[OptimizationChange]:
        changes: list[OptimizationChange] = []
        by_category = perf.get("by_category", {})
        old_weights = dict(self._config.get("category_weights", {}))

        for category, stats in by_category.items():
            cat_wr = stats.get("win_rate", 0.5)
            old_w = old_weights.get(category, 1.0)

            if cat_wr > 0.60:
                new_w = min(old_w + 0.1, 2.0)
            elif cat_wr < 0.40:
                new_w = max(old_w - 0.1, 0.2)
            else:
                continue

            new_w = round(new_w, 2)
            if new_w != old_w:
                self._config.setdefault("category_weights", {})[category] = new_w
                changes.append(OptimizationChange(
                    f"category_weights.{category}", old_w, new_w,
                    f"Category '{category}' win rate {cat_wr:.1%} — adjusting weight",
                ))

        return changes

    def _tune_odds_range(self, history: list[dict[str, Any]]) -> list[OptimizationChange]:
        changes: list[OptimizationChange] = []
        if not history:
            return changes

        # Count accuracy for bets near the extremes
        extreme_bets = [
            h for h in history
            if h.get("market_prob", 0.5) < 0.20 or h.get("market_prob", 0.5) > 0.80
        ]
        if len(extreme_bets) < 5:
            return changes

        extreme_wins = sum(1 for h in extreme_bets if h.get("won", False))
        extreme_wr = extreme_wins / len(extreme_bets)

        if extreme_wr < 0.40:
            old_range = list(self._config["odds_range"])
            new_lower = min(old_range[0] + 0.05, 0.30)
            new_upper = max(old_range[1] - 0.05, 0.70)
            new_range = [round(new_lower, 2), round(new_upper, 2)]

            if new_range != old_range:
                self._config["odds_range"] = new_range
                changes.append(OptimizationChange(
                    "odds_range", old_range, new_range,
                    f"Extreme-odds win rate {extreme_wr:.1%} — tightening odds range",
                ))

        return changes

    def _tune_confidence_multipliers(
        self, perf: dict[str, Any], history: list[dict[str, Any]]
    ) -> list[OptimizationChange]:
        changes: list[OptimizationChange] = []
        by_conf = perf.get("by_confidence", {})

        for level in ("low", "medium"):
            stats = by_conf.get(level, {})
            pnl = stats.get("pnl", 0.0)
            if pnl < 0:
                old = self._config["confidence_multipliers"].get(level, 0.3)
                new = max(old - 0.1, 0.1)
                new = round(new, 2)
                if new != old:
                    self._config["confidence_multipliers"][level] = new
                    changes.append(OptimizationChange(
                        f"confidence_multipliers.{level}", old, new,
                        f"'{level}' confidence bets have negative P&L ({pnl:+.2f}) — reducing multiplier",
                    ))

        return changes


# ---------------------------------------------------------------------------
# PerformanceAnalyzer
# ---------------------------------------------------------------------------


@dataclass
class DailyPnL:
    """Single day's P&L record."""

    date: str
    pnl: float
    cumulative: float


class PerformanceAnalyzer:
    """Analyzes paper trading results into a comprehensive report."""

    def __init__(
        self,
        portfolio: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> None:
        """
        Parameters
        ----------
        portfolio:
            Current portfolio state with keys ``balance``, ``initial_balance``,
            ``peak_balance``.
        history:
            List of completed bet dicts. Expected keys include ``won`` (bool),
            ``pnl`` (float), ``category`` (str), ``confidence`` (str),
            ``edge`` (float), ``market_prob`` (float), ``predicted_prob``
            (float), ``timestamp`` (str ISO).
        """
        self._portfolio = portfolio
        self._history = history

    def analyze(self) -> dict[str, Any]:
        """Return comprehensive performance analysis."""
        if not self._history:
            return self._empty_report()

        return {
            "overall": self._overall_stats(),
            "by_category": self._by_category(),
            "by_confidence": self._by_confidence(),
            "by_edge_bucket": self._by_edge_bucket(),
            "time_series": self._time_series(),
            "predictions_accuracy": self._calibration_curve_data(),
        }

    # -- overall ------------------------------------------------------------

    def _overall_stats(self) -> dict[str, Any]:
        total = len(self._history)
        wins = sum(1 for h in self._history if h.get("won"))
        win_rate = wins / total if total else 0.0

        pnls = [h.get("pnl", 0.0) for h in self._history]
        total_pnl = sum(pnls)
        initial = self._portfolio.get("initial_balance", 1000.0)
        roi = total_pnl / initial if initial else 0.0

        max_drawdown = self._compute_max_drawdown(pnls, initial)
        sharpe = self._compute_sharpe(pnls)

        return {
            "win_rate": round(win_rate, 4),
            "roi": round(roi, 4),
            "sharpe": round(sharpe, 4),
            "max_drawdown": round(max_drawdown, 4),
            "total_pnl": round(total_pnl, 2),
            "total_bets": total,
            "wins": wins,
            "losses": total - wins,
        }

    # -- by category --------------------------------------------------------

    def _by_category(self) -> dict[str, dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for h in self._history:
            buckets[h.get("category", "unknown")].append(h)

        result: dict[str, dict[str, Any]] = {}
        for cat, bets in sorted(buckets.items()):
            wins = sum(1 for b in bets if b.get("won"))
            pnl = sum(b.get("pnl", 0.0) for b in bets)
            result[cat] = {
                "win_rate": round(wins / len(bets), 4) if bets else 0.0,
                "pnl": round(pnl, 2),
                "num_bets": len(bets),
            }
        return result

    # -- by confidence ------------------------------------------------------

    def _by_confidence(self) -> dict[str, dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for h in self._history:
            buckets[h.get("confidence", "unknown")].append(h)

        result: dict[str, dict[str, Any]] = {}
        for level, bets in sorted(buckets.items()):
            wins = sum(1 for b in bets if b.get("won"))
            pnl = sum(b.get("pnl", 0.0) for b in bets)
            result[level] = {
                "win_rate": round(wins / len(bets), 4) if bets else 0.0,
                "pnl": round(pnl, 2),
                "num_bets": len(bets),
            }
        return result

    # -- by edge bucket -----------------------------------------------------

    def _by_edge_bucket(self) -> dict[str, dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = {
            "3-5%": [],
            "5-10%": [],
            "10%+": [],
        }
        for h in self._history:
            edge = abs(h.get("edge", 0.0))
            if edge >= 0.10:
                buckets["10%+"].append(h)
            elif edge >= 0.05:
                buckets["5-10%"].append(h)
            elif edge >= 0.03:
                buckets["3-5%"].append(h)

        result: dict[str, dict[str, Any]] = {}
        for label, bets in buckets.items():
            wins = sum(1 for b in bets if b.get("won"))
            result[label] = {
                "win_rate": round(wins / len(bets), 4) if bets else 0.0,
                "num_bets": len(bets),
            }
        return result

    # -- time series --------------------------------------------------------

    def _time_series(self) -> dict[str, list[dict[str, Any]]]:
        daily: dict[str, float] = defaultdict(float)
        for h in self._history:
            ts = h.get("timestamp", "")
            date_str = ts[:10] if len(ts) >= 10 else "unknown"
            daily[date_str] += h.get("pnl", 0.0)

        sorted_dates = sorted(daily.keys())
        cumulative = 0.0
        daily_records: list[dict[str, Any]] = []
        cumulative_records: list[dict[str, Any]] = []

        for d in sorted_dates:
            pnl = round(daily[d], 2)
            cumulative += pnl
            daily_records.append({"date": d, "pnl": pnl})
            cumulative_records.append({"date": d, "cumulative_pnl": round(cumulative, 2)})

        return {
            "daily_pnl": daily_records,
            "cumulative_pnl": cumulative_records,
        }

    # -- calibration curve data ---------------------------------------------

    def _calibration_curve_data(self) -> dict[str, Any]:
        """Generate calibration-curve-style data from trade history."""
        num_bins = 10
        bins: list[dict[str, Any]] = []

        for i in range(num_bins):
            bin_start = i / num_bins
            bin_end = (i + 1) / num_bins
            in_bin = [
                h for h in self._history
                if bin_start <= h.get("predicted_prob", 0.5) < bin_end
            ]
            if in_bin:
                predicted_mean = sum(h.get("predicted_prob", 0.5) for h in in_bin) / len(in_bin)
                actual_rate = sum(1 for h in in_bin if h.get("won")) / len(in_bin)
                bins.append({
                    "bin_start": bin_start,
                    "bin_end": bin_end,
                    "predicted_mean": round(predicted_mean, 4),
                    "actual_rate": round(actual_rate, 4),
                    "count": len(in_bin),
                })

        return {"bins": bins}

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _compute_max_drawdown(pnls: list[float], initial_balance: float) -> float:
        """Compute maximum drawdown as a fraction of peak balance."""
        if not pnls:
            return 0.0

        balance = initial_balance
        peak = balance
        max_dd = 0.0

        for pnl in pnls:
            balance += pnl
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak if peak > 0 else 0.0
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd

    @staticmethod
    def _compute_sharpe(pnls: list[float], periods_per_year: float = 365.0) -> float:
        """Annualized Sharpe ratio from a series of P&L values."""
        if len(pnls) < 2:
            return 0.0

        mean = sum(pnls) / len(pnls)
        variance = sum((p - mean) ** 2 for p in pnls) / (len(pnls) - 1)
        std = variance ** 0.5

        if std == 0:
            return 0.0

        return (mean / std) * (periods_per_year ** 0.5)

    def _empty_report(self) -> dict[str, Any]:
        return {
            "overall": {
                "win_rate": 0.0,
                "roi": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "total_pnl": 0.0,
                "total_bets": 0,
                "wins": 0,
                "losses": 0,
            },
            "by_category": {},
            "by_confidence": {},
            "by_edge_bucket": {
                "3-5%": {"win_rate": 0.0, "num_bets": 0},
                "5-10%": {"win_rate": 0.0, "num_bets": 0},
                "10%+": {"win_rate": 0.0, "num_bets": 0},
            },
            "time_series": {"daily_pnl": [], "cumulative_pnl": []},
            "predictions_accuracy": {"bins": []},
        }
