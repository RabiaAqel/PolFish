"""Automated paper trading loop — scans, predicts, bets, resolves, optimizes."""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

import httpx

from polymarket_predictor.config import DATA_DIR, MIROFISH_API_URL

logger = logging.getLogger(__name__)


class TradingLoop:
    """Runs the full scan -> predict -> bet -> resolve -> optimize cycle."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.running = False
        self._cycle_count = 0
        self._last_cycle: dict | None = None
        self._log: list[dict] = []

    def _push(self, msg: str, level: str = "info") -> None:
        entry = {"ts": time.time(), "msg": msg, "level": level, "cycle": self._cycle_count}
        self._log.append(entry)
        if len(self._log) > 500:
            self._log = self._log[-300:]
        getattr(logger, level, logger.info)(msg)

    # ------------------------------------------------------------------
    # Deep prediction helper
    # ------------------------------------------------------------------

    async def _predict_deep(self, slug: str) -> dict | None:
        """Call the deep prediction endpoint and poll until complete.

        Returns the prediction result dict or None on failure.
        """
        base_url = MIROFISH_API_URL  # e.g. http://localhost:5001/api
        start_url = f"{base_url}/polymarket/predict/deep"

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
                # Start the deep prediction task
                resp = await client.post(start_url, json={"slug": slug, "variants": 1})
                resp.raise_for_status()
                data = resp.json()
                if not data.get("success") or not data.get("task_id"):
                    self._push(f"    Deep predict start failed: {data}", "error")
                    return None

                task_id = data["task_id"]
                poll_url = f"{base_url}/polymarket/predict/deep/{task_id}"

                # Poll for completion (max ~5 minutes)
                for _ in range(60):
                    await asyncio.sleep(5)
                    poll_resp = await client.get(poll_url)
                    poll_data = poll_resp.json()
                    status = poll_data.get("status")

                    if status == "completed":
                        return poll_data.get("result", {})
                    elif status == "failed":
                        self._push(f"    Deep prediction failed: {poll_data.get('error')}", "error")
                        return None
                    # else still running, keep polling

                self._push("    Deep prediction timed out after 5 minutes", "error")
                return None

        except Exception as exc:
            self._push(f"    Deep prediction request error: {exc}", "error")
            return None

    # ------------------------------------------------------------------
    # Single cycle
    # ------------------------------------------------------------------

    async def run_cycle(self, prefer_deep: bool | None = None) -> dict:
        """Execute one full cycle: scan -> predict -> bet -> resolve -> optimize.

        Parameters
        ----------
        prefer_deep:
            If True, use the deep MiroFish prediction pipeline instead of
            quick mode.  If None, reads the ``prefer_deep`` flag from the
            strategy config.
        """
        from polymarket_predictor.scanner.market_scanner import MarketScanner
        from polymarket_predictor.paper_trader.portfolio import PaperPortfolio, BetSizer
        from polymarket_predictor.resolver.resolver import MarketResolver
        from polymarket_predictor.optimizer.strategy import StrategyOptimizer
        from polymarket_predictor.calibrator.history import PredictionHistory, PredictionRecord
        from polymarket_predictor.calibrator.calibrate import Calibrator

        self._cycle_count += 1
        cycle_start = time.time()
        self._push(f"=== Cycle {self._cycle_count} started at {datetime.now().strftime('%H:%M:%S')} ===", "info")

        # Load state
        portfolio = PaperPortfolio(data_dir=self.data_dir)
        history = PredictionHistory()
        calibrator = Calibrator()
        optimizer = StrategyOptimizer(data_dir=self.data_dir)
        config = optimizer.get_config()

        # Determine prediction mode
        use_deep = prefer_deep if prefer_deep is not None else config.get("prefer_deep", False)
        mode_label = "deep" if use_deep else "quick"
        self._push(f"Prediction mode: {mode_label}")

        result = {
            "cycle": self._cycle_count,
            "started_at": datetime.now().isoformat(),
            "mode": mode_label,
            "scanned": 0,
            "predicted": 0,
            "bets_placed": 0,
            "resolved": 0,
            "optimized": False,
            "errors": [],
        }

        # --- Step 1: Resolve any existing open positions ---
        self._push("Step 1: Checking resolutions for open positions...")
        try:
            resolver = MarketResolver(portfolio, calibrator, history)
            resolutions = await resolver.check_resolutions()
            result["resolved"] = len(resolutions)
            for r in resolutions:
                self._push(
                    f"  Resolved: {r.question[:50]} -> "
                    f"{'YES' if r.outcome_yes else 'NO'} | P&L: ${r.pnl:+.2f}",
                    "success" if r.pnl >= 0 else "error",
                )
        except Exception as exc:
            self._push(f"Resolution check failed: {exc}", "error")
            result["errors"].append(f"resolve: {exc}")

        # --- Step 2: Scan for interesting expiring markets ---
        self._push("Step 2: Scanning for expiring markets...")
        markets = []
        try:
            async with MarketScanner() as scanner:
                markets = await scanner.scan_interesting(
                    days_ahead=config.get("days_ahead", 14),
                    min_volume=config.get("min_volume", 100),
                    odds_range=tuple(config.get("odds_range", [0.10, 0.90])),
                )
            result["scanned"] = len(markets)
            self._push(f"  Found {len(markets)} interesting markets expiring soon")
        except Exception as exc:
            self._push(f"Scan failed: {exc}", "error")
            result["errors"].append(f"scan: {exc}")

        # --- Step 3: Predict + Paper bet ---
        self._push(f"Step 3: Running {mode_label} predictions and placing paper bets...")
        sizer = BetSizer()
        max_markets = config.get("max_markets_per_scan", 10)

        for i, market in enumerate(markets[:max_markets]):
            try:
                result["predicted"] += 1

                # Get YES price directly from market data
                odds = 0.5
                if hasattr(market, 'outcomes') and market.outcomes:
                    for o in market.outcomes:
                        if isinstance(o, str):
                            break
                        if isinstance(o, dict) and o.get("name", "").lower() in ("yes", "up"):
                            odds = float(o.get("price", 0.5))
                            break
                elif hasattr(market, 'yes_price'):
                    odds = market.yes_price or 0.5

                prediction_prob = None
                confidence = "low"
                num_variants = 1

                if use_deep:
                    # --- Deep mode: call the MiroFish deep prediction endpoint ---
                    self._push(f"  [{i+1}/{min(len(markets), max_markets)}] Deep predicting: {market.question[:60]}...")
                    deep_result = await self._predict_deep(market.slug)
                    if deep_result and deep_result.get("prediction"):
                        pred = deep_result["prediction"]
                        prediction_prob = pred.get("probability")
                        num_variants = pred.get("variants_run", 1)
                        # Determine confidence from edge size and variant count
                        if num_variants >= 3:
                            confidence = "high"
                        elif num_variants >= 2:
                            confidence = "medium"
                        else:
                            confidence = "medium"
                        self._push(
                            f"    Deep result: prob={prediction_prob:.1%}, signal={pred.get('signal')}, "
                            f"edge={pred.get('edge', 0):+.1%}, variants={num_variants}",
                            "success",
                        )

                if prediction_prob is None:
                    # --- Quick mode: use market odds + small random noise ---
                    import random
                    noise = random.uniform(-0.05, 0.05)
                    prediction_prob = max(0.05, min(0.95, odds + noise))
                    confidence = "low"
                    num_variants = 1
                    if use_deep:
                        self._push(f"    Deep prediction failed, falling back to quick mode", "warning")

                edge_estimate = abs(prediction_prob - odds)

                self._push(
                    f"  [{i+1}/{min(len(markets), max_markets)}] {market.question[:60]}... "
                    f"odds={odds:.1%} pred={prediction_prob:.1%} mode={mode_label}"
                )

                # Derive signal
                edge = prediction_prob - odds
                if edge > 0.03:
                    signal = "BUY_YES"
                elif edge < -0.03:
                    signal = "BUY_NO"
                else:
                    signal = "SKIP"

                # Record in history for tracking
                history.log_prediction(PredictionRecord(
                    market_id=market.slug,
                    question=market.question,
                    predicted_prob=prediction_prob,
                    market_prob=odds,
                    ensemble_std=0.0,
                    signal=signal,
                    reliability=confidence,
                    num_variants=num_variants,
                ))

                # Size bet
                bet = sizer.size_bet(
                    balance=portfolio.balance,
                    probability=prediction_prob,
                    market_odds=odds,
                    edge=edge_estimate,
                    confidence=confidence,
                    min_edge=config.get("min_edge_threshold", 0.03),
                    max_bet_pct=config.get("max_bet_pct", 0.05),
                )

                if bet["amount"] > 0:
                    portfolio.place_bet(
                        market_id=market.slug,
                        slug=market.slug,
                        question=market.question,
                        side=bet["side"],
                        amount=bet["amount"],
                        odds=odds,
                        closes_at=market.end_date.isoformat() if market.end_date else "",
                    )
                    result["bets_placed"] += 1
                    self._push(
                        f"    BET {bet['side']} ${bet['amount']:.2f} (kelly={bet['kelly_fraction']:.3f})",
                        "success",
                    )

            except Exception as exc:
                self._push(f"  Prediction failed for {getattr(market, 'slug', '?')}: {exc}", "error")
                result["errors"].append(f"predict: {exc}")

        # --- Step 4: Optimize strategy if enough data ---
        self._push("Step 4: Checking optimization...")
        try:
            perf = portfolio.get_performance()
            cal_report = calibrator.build_calibration()
            from dataclasses import asdict
            cal_stats = asdict(cal_report) if hasattr(cal_report, '__dataclass_fields__') else {}

            if perf.get("total_bets", 0) >= 10:
                opt_result = optimizer.optimize(perf, cal_stats, [])
                change_list = opt_result.get("changes", []) if isinstance(opt_result, dict) else []
                if change_list:
                    result["optimized"] = True
                    for change in change_list:
                        self._push(
                            f"  Optimized {change.get('parameter')}: {change.get('before')} -> "
                            f"{change.get('after')} ({change.get('reason', '')})",
                            "info",
                        )
                else:
                    self._push("  No optimization needed yet")
            else:
                self._push(f"  Need >=10 bets for optimization (have {perf.get('total_bets', 0)})")
        except Exception as exc:
            self._push(f"Optimization failed: {exc}", "error")
            result["errors"].append(f"optimize: {exc}")

        # --- Summary ---
        elapsed = time.time() - cycle_start
        result["elapsed_seconds"] = round(elapsed, 1)
        result["portfolio_balance"] = portfolio.balance
        result["portfolio_value"] = portfolio.total_value

        self._push(
            f"=== Cycle {self._cycle_count} complete in {elapsed:.1f}s | "
            f"Scanned: {result['scanned']} | Bets: {result['bets_placed']} | "
            f"Resolved: {result['resolved']} | Balance: ${portfolio.balance:,.2f} ===",
            "success",
        )

        self._last_cycle = result
        return result

    # ------------------------------------------------------------------
    # Continuous loop
    # ------------------------------------------------------------------

    async def start(self, interval_hours: float = 6.0) -> None:
        """Run cycles continuously with a sleep interval."""
        self.running = True
        self._push(f"Trading loop started (interval={interval_hours}h)")

        while self.running:
            try:
                await self.run_cycle()
            except Exception as exc:
                self._push(f"Cycle failed: {exc}", "error")

            if self.running:
                sleep_seconds = interval_hours * 3600
                self._push(f"Next cycle in {interval_hours}h...")
                await asyncio.sleep(sleep_seconds)

    def stop(self) -> None:
        """Stop the trading loop."""
        self.running = False
        self._push("Trading loop stopped")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return current loop status."""
        return {
            "running": self.running,
            "cycle_count": self._cycle_count,
            "last_cycle": self._last_cycle,
            "log": self._log[-50:],
        }

    def get_log(self, limit: int = 50) -> list[dict]:
        """Return recent log entries."""
        return self._log[-limit:]
