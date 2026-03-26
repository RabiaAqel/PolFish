"""Resilient overnight calibration and rolling trading loop.

Key guarantee: even if the process crashes, loses network, or hits API errors,
at most ONE prediction's work is lost. Everything else is checkpointed.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from polymarket_predictor.overnight.state import (
    StateManager, RunState, PredictionResult
)
from polymarket_predictor.config import DATA_DIR

logger = logging.getLogger(__name__)


class OvernightRunner:
    """Run N deep predictions with full crash recovery.

    Usage:
        runner = OvernightRunner(total=50, budget=25.0)
        await runner.run()  # Resumes from last checkpoint if interrupted
    """

    def __init__(self, total: int = 50, budget: float = 25.0, data_dir: Path = None):
        self._sm = StateManager(data_dir=data_dir or DATA_DIR)
        self._total = total
        self._budget = budget
        self._stop_requested = False

    def request_stop(self):
        """Gracefully stop after current prediction completes."""
        self._stop_requested = True
        logger.info("Stop requested — will pause after current prediction")

    async def run(self) -> RunState:
        """Run the overnight calibration. Resumes from checkpoint if one exists."""
        state = self._sm.load()

        # Check if we should resume or start fresh
        if state.status == "running" and state.mode == "overnight":
            logger.info("Resuming overnight run from prediction %d/%d",
                       state.completed + 1, state.total_target)
        elif state.status in ("completed", "idle", "failed", "paused"):
            # Start fresh
            state = RunState(
                run_id=f"overnight_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                mode="overnight",
                status="running",
                total_target=self._total,
                max_budget_usd=self._budget,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            self._sm.checkpoint(state, "Starting fresh overnight run")

        # Import here to avoid circular imports
        from polymarket_predictor.scrapers.polymarket import PolymarketScraper
        from polymarket_predictor.scrapers.news import NewsAggregator
        from polymarket_predictor.seeds.generator import SeedGenerator
        from polymarket_predictor.orchestrator.pipeline import MiroFishPipeline
        from polymarket_predictor.parser.prediction import PredictionParser
        from polymarket_predictor.paper_trader.portfolio import PaperPortfolio, BetSizer
        from polymarket_predictor.scanner.market_scanner import MarketScanner
        from polymarket_predictor.calibrator.calibrate import Calibrator
        from polymarket_predictor.calibrator.history import PredictionHistory
        from polymarket_predictor.optimizer.strategy import StrategyOptimizer
        from polymarket_predictor.resolver.resolver import MarketResolver
        from polymarket_predictor.ledger.decision_ledger import DecisionLedger

        # Try to import push_log for live UI updates
        try:
            from polymarket_predictor.dashboard.api import push_log
        except Exception:
            def push_log(msg, level="info"):
                logger.info("[overnight] %s", msg)

        portfolio = PaperPortfolio(data_dir=DATA_DIR)
        sizer = BetSizer()
        calibrator = Calibrator()
        history = PredictionHistory()
        optimizer = StrategyOptimizer(data_dir=DATA_DIR)
        ledger = DecisionLedger(data_dir=DATA_DIR)
        resolver = MarketResolver(portfolio, calibrator, history)

        push_log(f"Overnight run started: {state.completed}/{state.total_target} done, budget ${state.max_budget_usd - state.total_cost_usd:.2f} remaining")

        while state.completed + state.failed + state.skipped < state.total_target:
            # --- Guard: stop requested ---
            if self._stop_requested:
                state.status = "paused"
                state.paused_at = datetime.now(timezone.utc).isoformat()
                self._sm.checkpoint(state, "Paused by user request")
                push_log(f"Overnight run paused at {state.completed}/{state.total_target}", level="info")
                return state

            # --- Guard: budget exceeded ---
            if state.total_cost_usd >= state.max_budget_usd:
                state.status = "paused"
                state.paused_at = datetime.now(timezone.utc).isoformat()
                self._sm.checkpoint(state, f"Budget exhausted: ${state.total_cost_usd:.2f} >= ${state.max_budget_usd:.2f}")
                push_log(f"Budget exhausted at {state.completed} predictions, ${state.total_cost_usd:.2f} spent", level="info")
                return state

            prediction_num = state.completed + state.failed + state.skipped + 1
            push_log(f"[{prediction_num}/{state.total_target}] Scanning for next market...")

            # --- Phase 1: Find a market to predict ---
            state.current_phase = "scanning"
            self._sm.save(state)

            market = None
            try:
                async with MarketScanner() as scanner:
                    interesting = await scanner.scan_interesting(
                        days_ahead=30,
                        min_volume=100,
                        odds_range=(0.10, 0.90),
                    )
                    # Filter out already-processed and ultra-short HF markets
                    # 5m/15m too simple for deep — 1h/4h/daily are OK
                    SKIP_HF = ("-5m-", "-15m-")
                    candidates = [
                        m for m in interesting
                        if m.slug not in state.processed_slugs
                        and not any(p in m.slug for p in SKIP_HF)
                    ]

                if not candidates:
                    push_log("No new markets found — all available markets processed", level="info")
                    state.status = "completed"
                    state.completed_at = datetime.now(timezone.utc).isoformat()
                    self._sm.checkpoint(state, "No more markets to process")
                    break

                # --- Rank candidates by edge potential ---
                # Prefer markets that are NOT near 50/50 (more room for disagreement),
                # have lower volume (less efficient), and are niche topics.
                # Markets near 50% tend to produce SKIP because the simulation
                # agrees with the market consensus.

                def _edge_potential(m):
                    """Score a market's potential for finding edge. Higher = better."""
                    yes_price = 0.5
                    for o in m.outcomes:
                        if isinstance(o, dict) and o.get("name", "").lower() in ("yes", "up"):
                            yes_price = float(o.get("price", 0.5))
                            break

                    # Distance from 50% — markets at 20% or 80% have more potential
                    asymmetry = abs(yes_price - 0.5) * 2  # 0 at 50%, 1 at 0% or 100%

                    # Low volume = less efficient market
                    vol = getattr(m, "volume", 0) or 0
                    vol_score = 1.0 if vol < 5000 else (0.5 if vol < 50000 else 0.2)

                    return asymmetry * 0.6 + vol_score * 0.4

                candidates.sort(key=_edge_potential, reverse=True)

                # Take the best candidate
                market = candidates[0]
                score = _edge_potential(market)
                push_log(
                    f"Selected from {len(candidates)} candidates: "
                    f"{market.question[:50]}... (edge potential={score:.2f})",
                    level="success",
                )

            except Exception as e:
                logger.exception("Scan failed")
                state.errors.append({"phase": "scanning", "error": str(e), "time": time.strftime("%H:%M:%S")})
                self._sm.checkpoint(state, f"Scan error: {e}")
                await asyncio.sleep(30)  # Wait and retry
                continue

            # --- Phase 2: Deep predict ---
            slug = market.slug
            state.current_market = slug
            state.current_phase = "predicting"
            state.processed_slugs.append(slug)
            self._sm.save(state)

            result = PredictionResult(
                market_id=slug,
                slug=slug,
                question=market.question,
                market_odds=0.0,
                status="running",
            )

            # Extract market odds
            yes_price = 0.5
            for o in market.outcomes:
                if isinstance(o, dict) and o.get("name", "").lower() in ("yes", "up"):
                    yes_price = float(o.get("price", 0.5))
                    break
            result.market_odds = yes_price

            push_log(f"[{prediction_num}/{state.total_target}] Deep predicting: {market.question[:60]}...")

            start_time = time.time()
            try:
                # Gather news
                news = NewsAggregator()
                try:
                    articles = await news.search_articles(market.question, max_results=5)
                finally:
                    await news.close()

                # Generate seed
                gen = SeedGenerator()
                seed_path = gen.generate_seed(market, articles, variant="balanced")

                # Run full MiroFish pipeline
                pipeline = MiroFishPipeline()
                try:
                    report = await pipeline.run(
                        seed_file_path=seed_path,
                        simulation_requirement=market.question,
                    )
                finally:
                    await pipeline.client.aclose()

                # Extract prediction
                report_text = (
                    report.get("markdown_content", "")
                    or report.get("report_text", "")
                    or report.get("content", "")
                )
                parser = PredictionParser()
                prediction = await parser.parse(report_text, market.question)

                elapsed = time.time() - start_time

                result.prediction = prediction.probability
                result.edge = round(prediction.probability - yes_price, 4)
                result.confidence = prediction.confidence
                result.signal = "BUY_YES" if result.edge > 0.03 else ("BUY_NO" if result.edge < -0.03 else "SKIP")
                result.duration_seconds = round(elapsed, 1)
                result.status = "completed"
                result.completed_at = datetime.now(timezone.utc).isoformat()
                # TODO: add real cost from cost_tracker when wired
                result.cost_usd = 0.42  # estimated for hybrid

                push_log(
                    f"[{prediction_num}/{state.total_target}] {market.question[:40]}... "
                    f"pred={prediction.probability:.1%} vs market={yes_price:.1%} "
                    f"edge={result.edge:+.1%} ({elapsed:.0f}s, ~${result.cost_usd:.2f})",
                    level="success",
                )

                # --- Phase 3: Bet if edge is sufficient ---
                state.current_phase = "betting"
                self._sm.save(state)

                abs_edge = abs(result.edge)
                if abs_edge >= 0.03:
                    side = "YES" if result.edge > 0 else "NO"
                    bet_info = sizer.size_bet(
                        portfolio.balance, prediction.probability, yes_price,
                        abs_edge, prediction.confidence,
                    )
                    if bet_info["amount"] > 0:
                        closes_at = ""
                        if market.end_date:
                            closes_at = market.end_date.isoformat()
                        portfolio.place_bet(
                            market_id=slug, slug=slug, question=market.question,
                            side=side, amount=bet_info["amount"], odds=yes_price,
                            closes_at=closes_at,
                            prediction=prediction.probability,
                            edge=abs_edge,
                            confidence=prediction.confidence,
                            mode="deep",
                            kelly_fraction=bet_info.get("kelly_fraction", 0.0),
                            cost_usd=result.cost_usd,
                        )
                        result.side = side
                        result.bet_amount = bet_info["amount"]
                        result.bet_placed = True
                        push_log(f"  BET PLACED: ${bet_info['amount']:.2f} {side} (edge={abs_edge:.1%})", level="success")

                # Log to history for calibration
                from polymarket_predictor.calibrator.history import PredictionRecord
                history.log_prediction(PredictionRecord(
                    market_id=slug,
                    question=market.question,
                    predicted_prob=prediction.probability,
                    market_prob=yes_price,
                    ensemble_std=0.0,
                    signal=result.signal,
                    reliability=prediction.confidence,
                    num_variants=1,
                ))

                state.completed += 1
                state.total_cost_usd += result.cost_usd

            except Exception as e:
                elapsed = time.time() - start_time
                logger.exception("Prediction failed for %s", slug)
                result.status = "failed"
                result.error = str(e)
                result.duration_seconds = round(elapsed, 1)
                state.failed += 1
                state.errors.append({
                    "market": slug,
                    "error": str(e),
                    "phase": state.current_phase,
                    "time": time.strftime("%H:%M:%S"),
                })
                push_log(f"[{prediction_num}/{state.total_target}] FAILED: {slug} — {e}", level="error")

            # --- Checkpoint after every prediction ---
            state.results.append(asdict(result))
            state.current_market = None
            state.current_phase = ""
            self._sm.checkpoint(state, f"Prediction {prediction_num} {'completed' if result.status == 'completed' else 'failed'}")

            # --- Phase 4: Resolve any completed bets ---
            state.current_phase = "resolving"
            self._sm.save(state)
            try:
                resolved = await resolver.check_resolutions()
                if resolved:
                    for r in resolved:
                        push_log(f"  RESOLVED: {r.question[:40]}... -> {'YES' if r.outcome_yes else 'NO'} (P&L: ${r.pnl:+.2f})", level="success")
            except Exception as e:
                logger.warning("Resolution check failed: %s", e)

            # --- Phase 5: Calibrate + optimize every 10 predictions ---
            if state.completed > 0 and state.completed % 10 == 0:
                state.current_phase = "optimizing"
                self._sm.save(state)
                try:
                    calibrator.build_calibration()
                    perf = portfolio.get_performance()
                    if perf["total_bets"] >= 10:
                        changes = optimizer.optimize(perf, {}, [])
                        if changes:
                            push_log(f"  OPTIMIZER: {len(changes.get('changes', []))} params adjusted", level="info")
                            state.strategy_version += 1
                except Exception as e:
                    logger.warning("Optimization failed: %s", e)

            # Brief pause between predictions to avoid rate limits
            await asyncio.sleep(5)

        # --- Finalize ---
        if state.status == "running":
            state.status = "completed"
            state.completed_at = datetime.now(timezone.utc).isoformat()

        self._sm.checkpoint(state, f"Overnight run finished: {state.completed} completed, {state.failed} failed, ${state.total_cost_usd:.2f} spent")
        push_log(
            f"Overnight complete: {state.completed} predictions, "
            f"{state.failed} failures, ${state.total_cost_usd:.2f} total cost",
            level="success",
        )

        return state


class RollingLoop:
    """Continuous trading loop that runs indefinitely, improving each round.

    Usage:
        loop = RollingLoop(round_interval=3600, deep_per_round=3, budget_per_round=12.0)
        await loop.run()  # Runs forever, checkpointing each step
    """

    def __init__(
        self,
        round_interval: int = 3600,  # seconds between rounds
        deep_per_round: int = 3,
        budget_per_round: float = 12.0,
        max_total_budget: float = 100.0,
        data_dir: Path = None,
    ):
        self._sm = StateManager(data_dir=data_dir or DATA_DIR)
        self._round_interval = round_interval
        self._deep_per_round = deep_per_round
        self._budget_per_round = budget_per_round
        self._max_total_budget = max_total_budget
        self._stop_requested = False

    def request_stop(self):
        """Gracefully stop after current round completes."""
        self._stop_requested = True
        logger.info("Stop requested — will pause after current round")

    async def run(self) -> RunState:
        """Run the rolling loop. Resumes from checkpoint if one exists."""
        state = self._sm.load()

        if state.status == "running" and state.mode == "rolling":
            logger.info("Resuming rolling loop at round %d", state.current_round)
        else:
            state = RunState(
                run_id=f"rolling_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                mode="rolling",
                status="running",
                total_target=999999,  # unlimited
                max_budget_usd=self._max_total_budget,
                round_interval_seconds=self._round_interval,
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            self._sm.checkpoint(state, "Starting rolling loop")

        try:
            from polymarket_predictor.dashboard.api import push_log
        except Exception:
            def push_log(msg, level="info"):
                logger.info("[rolling] %s", msg)

        push_log(f"Rolling loop started (round {state.current_round + 1}, ${self._max_total_budget - state.total_cost_usd:.2f} budget remaining)")

        while not self._stop_requested:
            state.current_round += 1
            state.lifetime_rounds = state.current_round
            round_num = state.current_round

            push_log(f"=== ROUND {round_num} ===")

            # Budget guard
            if state.total_cost_usd >= self._max_total_budget:
                push_log(f"Total budget exhausted: ${state.total_cost_usd:.2f} >= ${self._max_total_budget:.2f}", level="info")
                state.status = "paused"
                self._sm.checkpoint(state, "Budget exhausted")
                break

            # Run one overnight-style mini batch (deep_per_round predictions)
            overnight = OvernightRunner(
                total=self._deep_per_round,
                budget=self._budget_per_round,
                data_dir=self._sm._dir,
            )

            # Override the state manager to share our state
            # (each round is a mini-overnight with its own target)
            round_state = RunState(
                run_id=f"round_{round_num}_{state.run_id}",
                mode="overnight",
                status="running",
                total_target=self._deep_per_round,
                max_budget_usd=self._budget_per_round,
                started_at=datetime.now(timezone.utc).isoformat(),
                processed_slugs=list(state.processed_slugs),  # carry forward
            )
            overnight._sm._state = round_state
            overnight._sm._state_file = self._sm._dir / f"round_{round_num}_state.json"

            try:
                round_result = await overnight.run()

                # Merge round results into rolling state
                state.completed += round_result.completed
                state.failed += round_result.failed
                state.skipped += round_result.skipped
                state.total_cost_usd += round_result.total_cost_usd
                state.results.extend(round_result.results)
                state.errors.extend(round_result.errors)
                state.processed_slugs = round_result.processed_slugs
                state.lifetime_bets = state.completed
                state.lifetime_cost = state.total_cost_usd

                push_log(
                    f"Round {round_num} done: {round_result.completed} predictions, "
                    f"${round_result.total_cost_usd:.2f} cost. "
                    f"Lifetime: {state.completed} total, ${state.total_cost_usd:.2f} spent",
                    level="success",
                )

            except Exception as e:
                logger.exception("Round %d failed", round_num)
                state.errors.append({
                    "round": round_num,
                    "error": str(e),
                    "time": time.strftime("%H:%M:%S"),
                })
                push_log(f"Round {round_num} failed: {e}", level="error")

            # Checkpoint after each round
            self._sm.checkpoint(state, f"Round {round_num} complete")

            # Sleep until next round
            if not self._stop_requested:
                push_log(f"Sleeping {self._round_interval}s until round {round_num + 1}...")
                state.current_phase = "sleeping"
                self._sm.save(state)

                # Sleep in small increments so we can respond to stop requests
                sleep_remaining = self._round_interval
                while sleep_remaining > 0 and not self._stop_requested:
                    await asyncio.sleep(min(30, sleep_remaining))
                    sleep_remaining -= 30

        if self._stop_requested:
            state.status = "paused"
            state.paused_at = datetime.now(timezone.utc).isoformat()
            push_log(f"Rolling loop paused at round {state.current_round}", level="info")

        self._sm.checkpoint(state, "Rolling loop stopped")
        return state
