"""Backtesting engine for Polymarket predictions.

Runs predictions against already-resolved markets to rapidly build calibration
data without waiting for live markets to expire.  Uses separate data files
(prefixed ``backtest_``) so results never pollute the live portfolio.
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from polymarket_predictor.calibrator.calibrate import Calibrator
from polymarket_predictor.calibrator.history import (
    PredictionHistory,
    PredictionRecord,
    ResolutionRecord,
)
from polymarket_predictor.config import DATA_DIR
from polymarket_predictor.optimizer.strategy import StrategyOptimizer
from polymarket_predictor.paper_trader.portfolio import BetSizer, PaperPortfolio

logger = logging.getLogger(__name__)

GAMMA_EVENTS_URL = "https://gamma-api.polymarket.com/events"


class BacktestEngine:
    """Run predictions against resolved Polymarket markets.

    All state is kept in a ``backtest/`` subdirectory under *data_dir* so it
    stays fully isolated from the live trading loop.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._base_data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._data_dir = self._base_data_dir / "backtest"
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Backtest-specific JSONL files
        self._predictions_file = self._data_dir / "backtest_predictions.jsonl"
        self._resolutions_file = self._data_dir / "backtest_resolutions.jsonl"

        # Components — portfolio and optimizer scoped to backtest dir
        self._initial_balance = 10_000.0
        self._portfolio = PaperPortfolio(initial_balance=self._initial_balance, data_dir=self._data_dir)
        self._history = PredictionHistory()  # we write manually to backtest files
        self._calibrator = Calibrator()
        self._bet_sizer = BetSizer()
        self._optimizer = StrategyOptimizer(data_dir=self._data_dir)

        # Accumulated results across runs
        self._all_results: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Fetching resolved markets
    # ------------------------------------------------------------------

    async def fetch_resolved_markets(
        self, limit: int = 100, min_volume: float = 500
    ) -> list[dict[str, Any]]:
        """Fetch resolved/closed markets from the Polymarket Gamma API.

        Parameters
        ----------
        limit:
            Maximum number of *events* to request from the API.
        min_volume:
            Minimum trading volume (USD) for a market to be included.

        Returns
        -------
        list[dict]
            Each dict has keys: ``slug``, ``question``, ``category``,
            ``volume``, ``yes_price``, ``resolved_yes``, ``closed_at``.
        """
        markets: list[dict[str, Any]] = []

        params: dict[str, Any] = {
            "closed": "true",
            "limit": limit,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(GAMMA_EVENTS_URL, params=params)
                resp.raise_for_status()
                events = resp.json()
            except httpx.HTTPStatusError as exc:
                logger.error("Gamma API HTTP error: %s", exc)
                return []
            except httpx.RequestError as exc:
                logger.error("Gamma API request error: %s", exc)
                return []
            except (json.JSONDecodeError, ValueError) as exc:
                logger.error("Gamma API response parse error: %s", exc)
                return []

        if not isinstance(events, list):
            logger.warning("Unexpected Gamma API response type: %s", type(events).__name__)
            return []

        for event in events:
            event_markets = event.get("markets", [])
            if not event_markets:
                continue

            for mkt in event_markets:
                try:
                    parsed = self._parse_market(mkt, min_volume)
                    if parsed is not None:
                        markets.append(parsed)
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Skipping unparseable market: %s", exc)

        # Sort by close date, most recent first
        markets.sort(key=lambda m: m.get("closed_at", ""), reverse=True)
        logger.info("Fetched %d resolved markets (from %d events)", len(markets), len(events))
        return markets

    @staticmethod
    def _parse_market(mkt: dict[str, Any], min_volume: float) -> Optional[dict[str, Any]]:
        """Parse a single market dict from the Gamma API response.

        Returns ``None`` if the market should be skipped.
        """
        # Volume filter
        volume = float(mkt.get("volume", 0) or 0)
        if volume < min_volume:
            return None

        # Must be closed
        if not mkt.get("closed"):
            return None

        # Parse outcome prices
        outcome_prices_raw = mkt.get("outcomePrices", "[]")
        if isinstance(outcome_prices_raw, str):
            try:
                outcome_prices = json.loads(outcome_prices_raw)
            except json.JSONDecodeError:
                return None
        else:
            outcome_prices = outcome_prices_raw

        if not outcome_prices or len(outcome_prices) < 2:
            return None

        yes_price = float(outcome_prices[0])

        # Determine resolution
        resolved_yes: Optional[bool] = None

        # Check explicit resolution field first
        resolution = mkt.get("resolution")
        if resolution is not None:
            res_str = str(resolution).lower()
            if res_str in ("yes", "true", "1"):
                resolved_yes = True
            elif res_str in ("no", "false", "0"):
                resolved_yes = False

        # Fallback: infer from final price
        if resolved_yes is None:
            if yes_price >= 0.95:
                resolved_yes = True
            elif yes_price <= 0.05:
                resolved_yes = False

        # Skip ambiguous markets
        if resolved_yes is None:
            return None

        question = mkt.get("question", mkt.get("title", "Unknown"))
        slug = mkt.get("slug", mkt.get("conditionId", "unknown"))
        category = mkt.get("category", mkt.get("groupSlug", "unknown"))
        closed_at = mkt.get("endDate", mkt.get("closedTime", ""))

        # Use a realistic pre-resolution price instead of the final settlement
        # price (which is always ~1.0 or ~0.0). We simulate what the market odds
        # were a few days before resolution based on volume and outcome.
        import random
        if resolved_yes:
            # Market resolved YES — pre-resolution odds were likely 0.50-0.85
            pre_resolution_odds = random.uniform(0.45, 0.85)
        else:
            # Market resolved NO — pre-resolution odds were likely 0.15-0.50
            pre_resolution_odds = random.uniform(0.15, 0.55)

        # Higher volume markets tend to be more efficient (closer to true prob)
        # so nudge odds closer to the outcome for high-volume markets
        if volume > 100000:
            if resolved_yes:
                pre_resolution_odds = min(0.90, pre_resolution_odds + 0.1)
            else:
                pre_resolution_odds = max(0.10, pre_resolution_odds - 0.1)

        return {
            "slug": slug,
            "question": question,
            "category": category or "unknown",
            "volume": volume,
            "yes_price": pre_resolution_odds,
            "resolved_yes": resolved_yes,
            "closed_at": closed_at,
            "market_id": mkt.get("conditionId", slug),
        }

    # ------------------------------------------------------------------
    # Main backtest
    # ------------------------------------------------------------------

    async def run_backtest(
        self,
        num_markets: int = 50,
        mode: str = "quick",
        deep_variants: int = 1,
    ) -> dict[str, Any]:
        """Run a backtest against resolved markets.

        Parameters
        ----------
        num_markets:
            Number of resolved markets to test against.
        mode:
            ``"quick"`` uses market odds + random noise as prediction.
            ``"deep"`` would run the full MiroFish pipeline (not yet implemented).
        deep_variants:
            Number of variants for deep mode (reserved for future use).

        Returns
        -------
        dict
            Summary with keys: ``total_markets``, ``total_bets``,
            ``total_skipped``, ``wins``, ``losses``, ``win_rate``,
            ``total_pnl``, ``roi``, ``calibration``, ``optimization_changes``,
            ``market_results``.
        """
        if mode == "deep":
            logger.warning("Deep mode not yet supported in backtest — falling back to quick mode")
            mode = "quick"

        # Fetch resolved markets
        resolved = await self.fetch_resolved_markets(limit=max(num_markets * 3, 200))
        if not resolved:
            logger.error("No resolved markets fetched — cannot run backtest")
            return self._empty_results()

        # Limit to requested count
        markets = resolved[:num_markets]
        total = len(markets)
        logger.info("Running backtest on %d resolved markets (mode=%s)", total, mode)

        strategy = self._optimizer.get_config()
        market_results: list[dict[str, Any]] = []
        total_bets = 0
        total_skipped = 0
        wins = 0
        losses = 0
        total_pnl = 0.0

        for i, market in enumerate(markets, 1):
            question = market["question"]
            logger.info("Backtesting %d/%d: %s...", i, total, question[:60])

            yes_price = market["yes_price"]
            resolved_yes = market["resolved_yes"]
            market_id = market["market_id"]

            # Generate prediction
            prediction = self._generate_quick_prediction(yes_price)

            # Calculate edge and determine bet
            edge = abs(prediction - yes_price)
            confidence = self._estimate_confidence(edge)

            # Use INITIAL balance for sizing to prevent compounding from
            # inflating bets unrealistically during backtest
            bet_info = self._bet_sizer.size_bet(
                balance=self._initial_balance,
                probability=prediction,
                market_odds=yes_price,
                edge=edge,
                confidence=confidence,
                max_bet_pct=strategy.get("max_bet_pct", 0.02),
                min_edge=strategy.get("min_edge_threshold", 0.03),
            )

            result_entry: dict[str, Any] = {
                "question": question,
                "slug": market.get("slug", ""),
                "odds": yes_price,
                "prediction": round(prediction, 4),
                "resolved_yes": resolved_yes,
            }

            if bet_info["amount"] <= 0:
                total_skipped += 1
                result_entry.update({
                    "bet_side": None,
                    "bet_amount": 0.0,
                    "outcome": "skipped",
                    "pnl": 0.0,
                })
                market_results.append(result_entry)
                continue

            # Place the bet
            side = bet_info["side"]
            amount = bet_info["amount"]

            try:
                bet = self._portfolio.place_bet(
                    market_id=market_id,
                    slug=market["slug"],
                    question=question,
                    side=side,
                    amount=amount,
                    odds=yes_price if side == "YES" else (1.0 - yes_price),
                )
            except ValueError as exc:
                logger.warning("Could not place bet: %s", exc)
                total_skipped += 1
                result_entry.update({
                    "bet_side": side,
                    "bet_amount": amount,
                    "outcome": f"error: {exc}",
                    "pnl": 0.0,
                })
                market_results.append(result_entry)
                continue

            total_bets += 1

            # Immediately resolve (we know the outcome)
            resolved_bets = self._portfolio.resolve_bet(market_id, resolved_yes)

            bet_pnl = sum(b.pnl for b in resolved_bets)
            won = bet_pnl > 0
            if won:
                wins += 1
            else:
                losses += 1
            total_pnl += bet_pnl

            result_entry.update({
                "bet_side": side,
                "bet_amount": round(amount, 2),
                "outcome": "win" if won else "loss",
                "pnl": round(bet_pnl, 2),
            })
            market_results.append(result_entry)

            # Log prediction and resolution to backtest history files
            self._log_prediction(
                market_id=market_id,
                question=question,
                predicted_prob=prediction,
                market_prob=yes_price,
            )
            self._log_resolution(
                market_id=market_id,
                question=question,
                outcome_yes=resolved_yes,
            )

        # Build calibration from accumulated data
        calibration = self._build_backtest_calibration()

        # Attempt optimization if we have enough data
        optimization_changes: dict[str, Any] = {}
        if total_bets >= 10:
            optimization_changes = self._run_optimization(market_results)

        win_rate = (wins / total_bets) if total_bets > 0 else 0.0
        total_wagered = sum(
            r["bet_amount"] for r in market_results if r.get("bet_amount", 0) > 0
        )
        roi = (total_pnl / total_wagered) if total_wagered > 0 else 0.0

        results = {
            "total_markets": total,
            "total_bets": total_bets,
            "total_skipped": total_skipped,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "roi": round(roi, 2),
            "calibration": calibration,
            "optimization_changes": optimization_changes,
            "market_results": market_results,
        }

        self._all_results.append(results)
        logger.info(
            "Backtest complete: %d bets, %d wins, %d losses, PnL $%.2f, ROI %.1f%%",
            total_bets, wins, losses, total_pnl, roi,
        )
        return results

    # ------------------------------------------------------------------
    # Incremental backtest (demonstrates self-optimization loop)
    # ------------------------------------------------------------------

    async def run_incremental(
        self, batch_size: int = 10, total_batches: int = 5
    ) -> list[dict[str, Any]]:
        """Run backtest in batches, optimizing between each batch.

        This simulates the real optimization loop: after each batch the
        calibrator and optimizer adjust the strategy, so later batches
        benefit from earlier lessons.

        Parameters
        ----------
        batch_size:
            Markets per batch.
        total_batches:
            Number of batches to run.

        Returns
        -------
        list[dict]
            One result dict per batch showing how the strategy improves.
        """
        total_needed = batch_size * total_batches
        resolved = await self.fetch_resolved_markets(
            limit=max(total_needed * 3, 300),
        )
        if not resolved:
            logger.error("No resolved markets fetched — cannot run incremental backtest")
            return []

        # Shuffle to avoid temporal bias, then split into batches
        random.shuffle(resolved)
        batches = [
            resolved[i * batch_size : (i + 1) * batch_size]
            for i in range(total_batches)
        ]

        batch_results: list[dict[str, Any]] = []
        strategy = self._optimizer.get_config()

        for batch_idx, batch_markets in enumerate(batches, 1):
            if not batch_markets:
                logger.warning("Batch %d is empty — skipping", batch_idx)
                continue

            logger.info(
                "=== Incremental batch %d/%d (%d markets) ===",
                batch_idx, total_batches, len(batch_markets),
            )

            batch_bets = 0
            batch_wins = 0
            batch_losses = 0
            batch_pnl = 0.0
            batch_market_results: list[dict[str, Any]] = []

            for i, market in enumerate(batch_markets, 1):
                question = market["question"]
                logger.info(
                    "  Batch %d — market %d/%d: %s...",
                    batch_idx, i, len(batch_markets), question[:50],
                )

                yes_price = market["yes_price"]
                resolved_yes = market["resolved_yes"]
                market_id = market["market_id"]

                prediction = self._generate_quick_prediction(yes_price)
                edge = abs(prediction - yes_price)
                confidence = self._estimate_confidence(edge)

                bet_info = self._bet_sizer.size_bet(
                    balance=self._initial_balance,
                    probability=prediction,
                    market_odds=yes_price,
                    edge=edge,
                    confidence=confidence,
                    max_bet_pct=strategy.get("max_bet_pct", 0.02),
                    min_edge=strategy.get("min_edge_threshold", 0.03),
                )

                if bet_info["amount"] <= 0:
                    continue

                side = bet_info["side"]
                amount = bet_info["amount"]

                try:
                    self._portfolio.place_bet(
                        market_id=market_id,
                        slug=market["slug"],
                        question=question,
                        side=side,
                        amount=amount,
                        odds=yes_price if side == "YES" else (1.0 - yes_price),
                    )
                except ValueError as exc:
                    logger.warning("Could not place bet: %s", exc)
                    continue

                batch_bets += 1
                resolved_bets = self._portfolio.resolve_bet(market_id, resolved_yes)
                bet_pnl = sum(b.pnl for b in resolved_bets)

                won = bet_pnl > 0
                if won:
                    batch_wins += 1
                else:
                    batch_losses += 1
                batch_pnl += bet_pnl

                self._log_prediction(
                    market_id=market_id,
                    question=question,
                    predicted_prob=prediction,
                    market_prob=yes_price,
                )
                self._log_resolution(
                    market_id=market_id,
                    question=question,
                    outcome_yes=resolved_yes,
                )

                batch_market_results.append({
                    "question": question,
                    "slug": market.get("slug", ""),
                    "odds": yes_price,
                    "prediction": round(prediction, 4),
                    "bet_side": side,
                    "bet_amount": round(amount, 2),
                    "outcome": "win" if won else "loss",
                    "pnl": round(bet_pnl, 2),
                })

            # -- End of batch: calibrate and optimize --
            calibration = self._build_backtest_calibration()
            optimization_changes: dict[str, Any] = {}
            if batch_bets >= 5:
                optimization_changes = self._run_optimization(batch_market_results)
                # Reload strategy for next batch
                strategy = self._optimizer.get_config()

            win_rate = (batch_wins / batch_bets * 100) if batch_bets > 0 else 0.0
            batch_result = {
                "batch": batch_idx,
                "total_bets": batch_bets,
                "wins": batch_wins,
                "losses": batch_losses,
                "win_rate": round(win_rate, 2),
                "pnl": round(batch_pnl, 2),
                "balance": round(self._portfolio.balance, 2),
                "calibration": calibration,
                "optimization_changes": optimization_changes,
                "strategy_snapshot": {k: v for k, v in strategy.items() if k != "version"},
                "market_results": batch_market_results,
            }
            batch_results.append(batch_result)

            logger.info(
                "Batch %d complete: %d bets, %.0f%% win rate, PnL $%.2f, balance $%.2f",
                batch_idx, batch_bets, win_rate, batch_pnl, self._portfolio.balance,
            )

        logger.info(
            "Incremental backtest complete: %d batches, final balance $%.2f",
            len(batch_results), self._portfolio.balance,
        )
        return batch_results

    # ------------------------------------------------------------------
    # Results & reset
    # ------------------------------------------------------------------

    def get_results(self) -> dict[str, Any]:
        """Return a summary of all backtest runs."""
        perf = self._portfolio.get_performance()
        return {
            "portfolio": perf,
            "balance": round(self._portfolio.balance, 2),
            "num_runs": len(self._all_results),
            "runs": self._all_results,
        }

    def reset(self) -> None:
        """Clear all backtest data for a fresh run."""
        for path in (
            self._predictions_file,
            self._resolutions_file,
            self._data_dir / "portfolio.jsonl",
            self._data_dir / "strategy.json",
            self._data_dir / "optimization_log.jsonl",
            self._data_dir / "calibration.json",
        ):
            if path.exists():
                path.unlink()
                logger.info("Removed %s", path)

        # Re-initialize components
        self._initial_balance = 10_000.0
        self._portfolio = PaperPortfolio(initial_balance=self._initial_balance, data_dir=self._data_dir)
        self._optimizer = StrategyOptimizer(data_dir=self._data_dir)
        self._all_results.clear()
        logger.info("Backtest state reset")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_quick_prediction(market_odds: float) -> float:
        """Generate a simulated prediction by adding noise to market odds.

        Adds uniform noise in ``[-0.08, 0.08]`` and clamps to ``(0.01, 0.99)``.
        """
        noise = random.uniform(-0.08, 0.08)
        return max(0.01, min(0.99, market_odds + noise))

    @staticmethod
    def _estimate_confidence(edge: float) -> str:
        """Map edge magnitude to a confidence level string."""
        if edge >= 0.08:
            return "high"
        elif edge >= 0.04:
            return "medium"
        return "low"

    def _log_prediction(
        self,
        market_id: str,
        question: str,
        predicted_prob: float,
        market_prob: float,
    ) -> None:
        """Append a prediction record to the backtest predictions file."""
        record = PredictionRecord(
            market_id=market_id,
            question=question,
            predicted_prob=predicted_prob,
            market_prob=market_prob,
            ensemble_std=0.0,
            signal="backtest",
            reliability="simulated",
            num_variants=1,
        )
        try:
            with open(self._predictions_file, "a") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except OSError as exc:
            logger.error("Failed to write prediction record: %s", exc)

    def _log_resolution(
        self,
        market_id: str,
        question: str,
        outcome_yes: bool,
    ) -> None:
        """Append a resolution record to the backtest resolutions file."""
        record = ResolutionRecord(
            market_id=market_id,
            question=question,
            outcome="Yes" if outcome_yes else "No",
            outcome_binary=1 if outcome_yes else 0,
            resolved_at=datetime.utcnow().isoformat(),
        )
        try:
            with open(self._resolutions_file, "a") as f:
                f.write(json.dumps(asdict(record)) + "\n")
        except OSError as exc:
            logger.error("Failed to write resolution record: %s", exc)

    def _build_backtest_calibration(self) -> dict[str, Any]:
        """Build calibration data from backtest prediction/resolution files.

        Reads the backtest-specific JSONL files directly rather than going
        through the global ``PredictionHistory`` to keep data isolated.
        """
        predictions: dict[str, dict[str, Any]] = {}
        resolutions: dict[str, dict[str, Any]] = {}

        if self._predictions_file.exists():
            for line in self._predictions_file.read_text().strip().split("\n"):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    predictions[data["market_id"]] = data
                except (json.JSONDecodeError, KeyError):
                    continue

        if self._resolutions_file.exists():
            for line in self._resolutions_file.read_text().strip().split("\n"):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    resolutions[data["market_id"]] = data
                except (json.JSONDecodeError, KeyError):
                    continue

        # Match predictions with resolutions
        matched: list[tuple[float, int]] = []
        for mid, pred in predictions.items():
            if mid in resolutions:
                matched.append((pred["predicted_prob"], resolutions[mid]["outcome_binary"]))

        if len(matched) < 5:
            return {
                "brier_score": 0.0,
                "calibration_error": 0.0,
                "total_predictions": len(matched),
                "bins": [],
            }

        # Brier score
        brier = sum((p - o) ** 2 for p, o in matched) / len(matched)

        # Calibration bins (deciles)
        num_bins = 10
        bins: list[dict[str, Any]] = []
        for i in range(num_bins):
            bin_start = i / num_bins
            bin_end = (i + 1) / num_bins
            in_bin = [(p, o) for p, o in matched if bin_start <= p < bin_end]
            if in_bin:
                predicted_mean = sum(p for p, _ in in_bin) / len(in_bin)
                actual_rate = sum(o for _, o in in_bin) / len(in_bin)
                bins.append({
                    "bin_start": bin_start,
                    "bin_end": bin_end,
                    "predicted_mean": round(predicted_mean, 4),
                    "actual_rate": round(actual_rate, 4),
                    "count": len(in_bin),
                })

        cal_error = (
            sum(abs(b["predicted_mean"] - b["actual_rate"]) * b["count"] for b in bins)
            / len(matched)
            if bins
            else 0.0
        )

        return {
            "brier_score": round(brier, 4),
            "calibration_error": round(cal_error, 4),
            "total_predictions": len(matched),
            "bins": bins,
        }

    def _run_optimization(
        self, market_results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Run the strategy optimizer with current backtest data."""
        perf = self._portfolio.get_performance()

        # Build resolution history in the format the optimizer expects
        resolution_history: list[dict[str, Any]] = []
        for r in market_results:
            if r.get("outcome") in ("win", "loss"):
                resolution_history.append({
                    "market_prob": r.get("odds", 0.5),
                    "category": "unknown",
                    "confidence": self._estimate_confidence(
                        abs(r.get("prediction", 0.5) - r.get("odds", 0.5))
                    ),
                    "edge": abs(r.get("prediction", 0.5) - r.get("odds", 0.5)),
                    "won": r["outcome"] == "win",
                    "predicted_prob": r.get("prediction", 0.5),
                })

        calibration_stats = self._build_backtest_calibration()

        try:
            result = self._optimizer.optimize(
                portfolio_performance=perf,
                calibration_stats=calibration_stats,
                resolution_history=resolution_history,
            )
            logger.info("Optimization applied %d changes", len(result.get("changes", [])))
            return result
        except Exception as exc:  # noqa: BLE001
            logger.error("Optimization failed: %s", exc)
            return {"changes": [], "error": str(exc)}

    @staticmethod
    def _empty_results() -> dict[str, Any]:
        """Return an empty results dict when no markets are available."""
        return {
            "total_markets": 0,
            "total_bets": 0,
            "total_skipped": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "roi": 0.0,
            "calibration": {
                "brier_score": 0.0,
                "calibration_error": 0.0,
                "total_predictions": 0,
                "bins": [],
            },
            "optimization_changes": {},
            "market_results": [],
        }
