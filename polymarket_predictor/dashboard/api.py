"""Dashboard API blueprint for viewing prediction signals."""

import asyncio
from dataclasses import asdict
import json
import logging
import queue
import threading
import time
import uuid
from flask import Blueprint, jsonify, request, Response

from polymarket_predictor.calibrator.history import PredictionHistory
from polymarket_predictor.calibrator.calibrate import Calibrator
from polymarket_predictor.config import DATA_DIR, PIPELINE_MODELS, get_stage_config
from polymarket_predictor.cost_calculator import CostCalculator
from polymarket_predictor.ledger.decision_ledger import DecisionLedger
from polymarket_predictor.paper_trader.portfolio import PaperPortfolio
# AutopilotEngine imported lazily to avoid circular dependency

logger = logging.getLogger(__name__)

# In-memory store for background deep-prediction tasks
_deep_tasks: dict[str, dict] = {}

# --- Module-level singletons for ledger & autopilot ---
_ledger = DecisionLedger(data_dir=DATA_DIR)
_portfolio = PaperPortfolio(data_dir=DATA_DIR)
_autopilot = None  # Lazy init to avoid circular import


def _get_autopilot():
    global _autopilot
    if _autopilot is None:
        from polymarket_predictor.autopilot.engine import AutopilotEngine
        _autopilot = AutopilotEngine(portfolio=_portfolio, ledger=_ledger, data_dir=DATA_DIR)
    return _autopilot

# ---------------------------------------------------------------------------
# Real-time log streaming infrastructure
# ---------------------------------------------------------------------------
_log_subscribers: list[queue.Queue] = []


def push_log(message: str, level: str = "info"):
    """Push a log entry to all active subscribers."""
    entry = {"ts": time.time(), "msg": message, "level": level}
    dead = []
    for q in _log_subscribers:
        try:
            q.put_nowait(entry)
        except queue.Full:
            dead.append(q)
    for q in dead:
        _log_subscribers.remove(q)

dashboard_bp = Blueprint("polymarket_dashboard", __name__, url_prefix="/api/polymarket")


def _run_async(coro):
    """Run an async coroutine from sync Flask context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@dashboard_bp.route("/logs/stream", methods=["GET"])
def stream_logs():
    """SSE endpoint for real-time log streaming."""

    def generate():
        q = queue.Queue(maxsize=100)
        _log_subscribers.append(q)
        try:
            yield f"data: {json.dumps({'msg': 'Connected to log stream', 'level': 'info'})}\n\n"
            while True:
                try:
                    entry = q.get(timeout=15)
                    yield f"data: {json.dumps(entry)}\n\n"
                except queue.Empty:
                    # Send keepalive
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in _log_subscribers:
                _log_subscribers.remove(q)

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@dashboard_bp.route("/predict", methods=["POST"])
def predict_market():
    """Run a quick single-variant prediction for a market slug."""
    data = request.get_json(silent=True) or {}
    slug = data.get("slug", "").strip()
    if not slug:
        return jsonify({"success": False, "error": "Please provide a market slug"}), 400

    # Handle full URLs: extract slug from polymarket.com/event/<slug>
    if "polymarket.com" in slug:
        import re
        m = re.search(r"polymarket\.com/event/([^/?#]+)", slug)
        if m:
            slug = m.group(1)
        else:
            # Try stripping the domain entirely
            slug = slug.rstrip("/").rsplit("/", 1)[-1]

    async def _predict():
        from polymarket_predictor.scrapers.polymarket import PolymarketScraper
        from polymarket_predictor.scrapers.news import NewsAggregator
        from polymarket_predictor.seeds.generator import SeedGenerator
        from polymarket_predictor.parser.prediction import PredictionParser

        push_log(f"Fetching market: {slug}")
        async with PolymarketScraper() as scraper:
            market = await scraper.get_market_by_slug(slug)
            if not market:
                push_log(f"Market '{slug}' not found", level="error")
                return {"success": False, "error": f"Market '{slug}' not found on Polymarket"}

            push_log(f"Market found: {market.question}")

            push_log("Searching for news articles...")
            news = NewsAggregator()
            try:
                articles = await news.search_articles(market.question, max_results=3)
            finally:
                await news.close()
            push_log(f"Found {len(articles)} articles")

            push_log("Generating seed document...")
            gen = SeedGenerator()
            seed_path = gen.generate_seed(market, articles, variant="balanced")
            push_log("Seed ready", level="success")

            # Extract YES price from outcomes list
            yes_price = 0.0
            for o in market.outcomes:
                if isinstance(o, dict) and o.get("name", "").lower() in ("yes", "up"):
                    yes_price = float(o.get("price", 0))
                    break

            return {
                "success": True,
                "data": {
                    "market": {
                        "question": market.question,
                        "slug": market.slug,
                        "current_odds": round(yes_price, 3),
                        "volume": market.volume,
                        "category": market.category,
                    },
                    "seed_file": str(seed_path),
                    "articles_found": len(articles),
                    "status": "seed_ready",
                    "message": (
                        f"Seed document generated with {len(articles)} articles. "
                        f"Market odds: {yes_price:.1%} YES. "
                        f"To run the full simulation, use the CLI: "
                        f"python -m polymarket_predictor predict {slug}"
                    ),
                },
            }

    try:
        result = _run_async(_predict())
        status = 200 if result.get("success") else 404
        return jsonify(result), status
    except Exception as e:
        logger.exception("Predict endpoint error")
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/signals", methods=["GET"])
def get_signals():
    """Get current prediction signals sorted by edge size."""
    min_edge = float(request.args.get("min_edge", 0.05))
    history = PredictionHistory()
    predictions = history.get_predictions()

    signals = []
    for p in predictions:
        edge = p.predicted_prob - p.market_prob
        if abs(edge) < min_edge:
            continue
        signals.append({
            "market_id": p.market_id,
            "question": p.question,
            "predicted_prob": round(p.predicted_prob, 3),
            "market_prob": round(p.market_prob, 3),
            "edge": round(edge, 3),
            "signal": p.signal,
            "reliability": p.reliability,
            "ensemble_std": round(p.ensemble_std, 3),
            "num_variants": p.num_variants,
            "timestamp": p.timestamp,
        })

    signals.sort(key=lambda s: abs(s["edge"]), reverse=True)
    return jsonify({"success": True, "data": {"signals": signals, "count": len(signals)}})


@dashboard_bp.route("/predictions", methods=["GET"])
def get_predictions():
    """Get all recent predictions."""
    limit = int(request.args.get("limit", 50))
    history = PredictionHistory()
    predictions = history.get_predictions()

    # Most recent first
    predictions.sort(key=lambda p: p.timestamp, reverse=True)
    predictions = predictions[:limit]

    return jsonify({
        "success": True,
        "data": {
            "predictions": [
                {
                    "market_id": p.market_id,
                    "question": p.question,
                    "predicted_prob": round(p.predicted_prob, 3),
                    "market_prob": round(p.market_prob, 3),
                    "edge": round(p.predicted_prob - p.market_prob, 3),
                    "signal": p.signal,
                    "reliability": p.reliability,
                    "timestamp": p.timestamp,
                }
                for p in predictions
            ],
            "count": len(predictions),
        },
    })


@dashboard_bp.route("/calibration", methods=["GET"])
def get_calibration():
    """Get current calibration stats."""
    calibrator = Calibrator()
    report = calibrator.build_calibration()

    return jsonify({
        "success": True,
        "data": {
            "brier_score": round(report.brier_score, 4),
            "calibration_error": round(report.calibration_error, 4),
            "total_predictions": report.total_predictions,
            "bins": [
                {
                    "range": f"{b.bin_start:.0%}-{b.bin_end:.0%}",
                    "predicted_mean": round(b.predicted_mean, 3),
                    "actual_rate": round(b.actual_rate, 3),
                    "count": b.count,
                }
                for b in report.bins
            ],
        },
    })


@dashboard_bp.route("/stats", methods=["GET"])
def get_stats():
    """Get summary statistics."""
    history = PredictionHistory()
    predictions = history.get_predictions()
    resolutions = history.get_resolutions()
    matched = history.get_matched_records()

    # Accuracy on matched
    correct = 0
    for p, r in matched:
        predicted_yes = p.predicted_prob > 0.5
        actual_yes = r.outcome_binary == 1
        if predicted_yes == actual_yes:
            correct += 1

    accuracy = correct / len(matched) if matched else 0

    # Signal distribution
    buy_yes = sum(1 for p in predictions if p.signal == "BUY_YES")
    buy_no = sum(1 for p in predictions if p.signal == "BUY_NO")
    skip = sum(1 for p in predictions if p.signal == "SKIP")

    return jsonify({
        "success": True,
        "data": {
            "total_predictions": len(predictions),
            "total_resolutions": len(resolutions),
            "matched": len(matched),
            "accuracy": round(accuracy, 3),
            "signals": {"buy_yes": buy_yes, "buy_no": buy_no, "skip": skip},
        },
    })


# ---------------------------------------------------------------------------
# Deep prediction (background task)
# ---------------------------------------------------------------------------


def _run_deep_pipeline(task_id: str, slug: str, variants: int) -> None:
    """Execute the full MiroFish pipeline in a background thread.

    Results are written into ``_deep_tasks[task_id]``.
    """
    import re as _re

    async def _execute():
        from polymarket_predictor.scrapers.polymarket import PolymarketScraper
        from polymarket_predictor.scrapers.news import NewsAggregator
        from polymarket_predictor.seeds.generator import SeedGenerator
        from polymarket_predictor.orchestrator.pipeline import MiroFishPipeline
        from polymarket_predictor.parser.prediction import PredictionParser
        from polymarket_predictor.cost_tracker import CostTracker, set_tracker

        # Set up cost tracking for this pipeline run
        tracker = CostTracker(model="gpt-4o")
        set_tracker(tracker)

        # --- extract slug from full URL if needed ---
        clean_slug = slug
        if "polymarket.com" in clean_slug:
            m = _re.search(r"polymarket\.com/event/([^/?#]+)", clean_slug)
            if m:
                clean_slug = m.group(1)
            else:
                clean_slug = clean_slug.rstrip("/").rsplit("/", 1)[-1]

        def set_step(step: str):
            _deep_tasks[task_id]["step"] = step

        # 1. Fetch market data
        set_step("fetching_market")
        push_log(f"Fetching market: {clean_slug}")
        async with PolymarketScraper() as scraper:
            market = await scraper.get_market_by_slug(clean_slug)
            if not market:
                push_log(f"Market '{clean_slug}' not found", level="error")
                raise ValueError(f"Market '{clean_slug}' not found on Polymarket")

        push_log(f"Market found: {market.question}", level="success")

        # 2. Gather news articles
        push_log("Gathering news articles...")
        news = NewsAggregator()
        try:
            articles = await news.search_articles(market.question, max_results=5)
        finally:
            await news.close()
        push_log(f"Found {len(articles)} articles")

        # 3. Generate seed document(s) — one per variant
        gen = SeedGenerator()
        variant_names = ["balanced", "bullish", "bearish", "contrarian", "data_heavy"]
        results = []

        for i in range(variants):
            variant = variant_names[i % len(variant_names)]
            push_log(f"Generating seed for variant {i + 1}/{variants} ({variant})...")
            seed_path = gen.generate_seed(market, articles, variant=variant)

            # 4-7. Run MiroFish pipeline: upload → graph → simulate → report
            push_log(f"Uploading seed to MiroFish ({variant})...")
            set_step("building_graph")
            pipeline = MiroFishPipeline()
            try:
                # We run steps individually to update progress
                project_id = await pipeline.upload_and_generate_ontology(seed_path, market.question)
                push_log(f"Ontology generated, project: {project_id}", level="success")

                push_log(f"Building knowledge graph ({variant})...")
                graph_id = await pipeline.build_graph(project_id)
                push_log(f"Graph built: {graph_id}", level="success")

                set_step("setting_up")
                push_log(f"Creating simulation ({variant})...")
                sim_id = await pipeline.create_simulation(project_id)
                push_log(f"Preparing simulation ({variant})...")
                await pipeline.prepare_simulation(sim_id)
                push_log(f"Simulation prepared", level="success")

                set_step("running_simulation")
                push_log(f"Running simulation ({variant})...")
                await pipeline.run_simulation(sim_id)
                push_log(f"Simulation completed", level="success")

                set_step("generating_report")
                push_log(f"Generating report ({variant})...")
                report = await pipeline.generate_report(sim_id)
                push_log(f"Report generated", level="success")
            finally:
                await pipeline.client.aclose()

            # 8. Parse prediction from report
            set_step("extracting_prediction")
            report_text = report.get("markdown_content", "") or report.get("report_text", "") or report.get("content", "")
            parser = PredictionParser()
            push_log(f"Extracting prediction ({variant})...")
            prediction = await parser.parse(report_text, market.question)

            push_log(f"Variant {variant}: probability={prediction.probability:.2%}", level="success")

            results.append({
                "variant": variant,
                "probability": round(prediction.probability, 4),
                "confidence": prediction.confidence,
                "key_factors": prediction.key_factors,
                "extraction_method": prediction.extraction_method,
            })

        # Compute ensemble average
        avg_prob = sum(r["probability"] for r in results) / len(results)

        # Derive market YES price
        yes_price = 0.0
        for o in market.outcomes:
            if isinstance(o, dict) and o.get("name", "").lower() in ("yes", "up"):
                yes_price = float(o.get("price", 0))
                break

        edge = round(avg_prob - yes_price, 4)
        if edge > 0.03:
            signal = "BUY_YES"
        elif edge < -0.03:
            signal = "BUY_NO"
        else:
            signal = "SKIP"

        return {
            "market": {
                "question": market.question,
                "slug": market.slug,
                "current_odds": round(yes_price, 4),
                "volume": market.volume,
                "category": market.category,
            },
            "prediction": {
                "probability": round(avg_prob, 4),
                "edge": edge,
                "signal": signal,
                "variants_run": len(results),
                "variant_details": results,
            },
            "report_summary": report_text[:2000] if report_text else "",
        }

    try:
        result = asyncio.run(_execute())
        push_log(f"Deep prediction complete: signal={result['prediction']['signal']}, edge={result['prediction']['edge']:+.2%}", level="success")
        _deep_tasks[task_id].update({"status": "completed", "step": "completed", "result": result})
    except Exception as exc:
        logger.exception("Deep prediction task %s failed", task_id)
        push_log(f"Deep prediction failed: {exc}", level="error")
        _deep_tasks[task_id].update({"status": "failed", "error": str(exc)})


@dashboard_bp.route("/predict/deep", methods=["POST"])
def predict_deep_start():
    """Start a full deep prediction pipeline as a background task."""
    data = request.get_json(silent=True) or {}
    slug = data.get("slug", "").strip()
    if not slug:
        return jsonify({"success": False, "error": "Please provide a market slug"}), 400

    variants = int(data.get("variants", 1))
    if variants < 1:
        variants = 1
    if variants > 5:
        variants = 5

    task_id = uuid.uuid4().hex[:12]
    _deep_tasks[task_id] = {"status": "running", "slug": slug, "variants": variants, "step": "fetching_market"}

    thread = threading.Thread(
        target=_run_deep_pipeline,
        args=(task_id, slug, variants),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "task_id": task_id, "status": "running"}), 202


@dashboard_bp.route("/predict/deep/<task_id>", methods=["GET"])
def predict_deep_status(task_id: str):
    """Check the status of a deep prediction task."""
    task = _deep_tasks.get(task_id)
    if task is None:
        return jsonify({"success": False, "error": f"Task '{task_id}' not found"}), 404

    response: dict = {"success": True, "task_id": task_id, "status": task["status"]}

    if task.get("step"):
        response["step"] = task["step"]

    if task["status"] == "completed":
        response["result"] = task["result"]
    elif task["status"] == "failed":
        response["error"] = task.get("error", "Unknown error")

    return jsonify(response), 200


# ---------------------------------------------------------------------------
# Paper Trading Loop endpoints
# ---------------------------------------------------------------------------

_trading_loop = None
_loop_thread = None


def _get_loop():
    global _trading_loop
    if _trading_loop is None:
        from polymarket_predictor.loop.runner import TradingLoop
        _trading_loop = TradingLoop(data_dir=DATA_DIR)
    return _trading_loop


@dashboard_bp.route("/loop/start", methods=["POST"])
def loop_start():
    """Start the paper trading loop."""
    global _loop_thread
    loop = _get_loop()

    if loop.running:
        return jsonify({"success": False, "error": "Loop is already running"}), 400

    data = request.get_json(silent=True) or {}
    interval = float(data.get("interval_hours", 6.0))

    def _run():
        asyncio.run(loop.start(interval_hours=interval))

    _loop_thread = threading.Thread(target=_run, daemon=True)
    _loop_thread.start()

    return jsonify({"success": True, "message": f"Trading loop started (interval={interval}h)"}), 200


@dashboard_bp.route("/loop/stop", methods=["POST"])
def loop_stop():
    """Stop the paper trading loop."""
    loop = _get_loop()
    loop.stop()
    return jsonify({"success": True, "message": "Trading loop stopped"}), 200


@dashboard_bp.route("/loop/run-once", methods=["POST"])
def loop_run_once():
    """Run a single trading cycle immediately.

    Optional JSON body: {"prefer_deep": true/false}
    If omitted, reads the prefer_deep flag from the strategy config.
    """
    loop = _get_loop()
    data = request.get_json(silent=True) or {}
    prefer_deep = data.get("prefer_deep")  # None means "use config default"

    task_id = uuid.uuid4().hex[:12]
    _deep_tasks[task_id] = {"status": "running", "type": "cycle"}

    def _run():
        try:
            result = asyncio.run(loop.run_cycle(prefer_deep=prefer_deep))
            push_log(
                f"Trading cycle complete: scanned={result.get('scanned', 0)}, "
                f"bets={result.get('bets_placed', 0)}, resolved={result.get('resolved', 0)}",
                level="success",
            )
            _deep_tasks[task_id].update({"status": "completed", "result": result})
        except Exception as exc:
            logger.exception("Trading cycle failed")
            push_log(f"Trading cycle failed: {exc}", level="error")
            _deep_tasks[task_id].update({"status": "failed", "error": str(exc)})

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return jsonify({"success": True, "task_id": task_id, "status": "running"}), 202


@dashboard_bp.route("/loop/status", methods=["GET"])
def loop_status():
    """Get loop status and recent log."""
    loop = _get_loop()
    return jsonify({"success": True, "data": loop.get_status()}), 200


@dashboard_bp.route("/loop/log", methods=["GET"])
def loop_log():
    """Get recent loop log entries."""
    loop = _get_loop()
    limit = int(request.args.get("limit", 50))
    return jsonify({"success": True, "data": loop.get_log(limit)}), 200


@dashboard_bp.route("/portfolio", methods=["GET"])
def portfolio_status():
    """Get paper trading portfolio status."""
    try:
        from polymarket_predictor.paper_trader.portfolio import PaperPortfolio
        portfolio = PaperPortfolio(data_dir=DATA_DIR)
        return jsonify({
            "success": True,
            "data": {
                "balance": portfolio.balance,
                "total_value": portfolio.total_value,
                "open_positions": [asdict(b) for b in portfolio.get_open_positions()],
                "performance": portfolio.get_performance(),
            },
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@dashboard_bp.route("/portfolio/history", methods=["GET"])
def portfolio_history():
    """Get resolved positions history."""
    try:
        from polymarket_predictor.paper_trader.portfolio import PaperPortfolio
        portfolio = PaperPortfolio(data_dir=DATA_DIR)
        return jsonify({
            "success": True,
            "data": {
                "resolved": [asdict(b) for b in portfolio.get_resolved_positions()],
                "performance": portfolio.get_performance(),
            },
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@dashboard_bp.route("/portfolio/resolve", methods=["POST"])
def portfolio_resolve():
    """Manually trigger resolution check for all open positions."""
    try:
        from polymarket_predictor.resolver.resolver import MarketResolver
        from polymarket_predictor.calibrator.history import PredictionHistory
        from polymarket_predictor.calibrator.calibrate import Calibrator

        portfolio = PaperPortfolio(data_dir=DATA_DIR)
        history = PredictionHistory()
        calibrator = Calibrator()
        resolver = MarketResolver(portfolio, calibrator, history)

        results = asyncio.run(resolver.check_resolutions())
        resolved_count = len(results)

        push_log(
            f"Resolution check: {resolved_count} positions resolved",
            level="success" if resolved_count > 0 else "info",
        )

        return jsonify({
            "success": True,
            "data": {
                "resolved_count": resolved_count,
                "results": [
                    {
                        "market_id": r.market_id,
                        "question": r.question,
                        "outcome": "YES" if r.outcome_yes else "NO",
                        "pnl": r.pnl,
                    }
                    for r in results
                ],
            },
        }), 200
    except Exception as exc:
        logger.exception("Resolution check failed")
        return jsonify({"success": False, "error": str(exc)}), 500


# --- Background resolution checker (every 5 minutes) ---
_resolution_timer = None

def _auto_resolve():
    """Background thread that checks for resolved markets every 5 minutes."""
    global _resolution_timer
    try:
        from polymarket_predictor.resolver.resolver import MarketResolver
        from polymarket_predictor.calibrator.history import PredictionHistory
        from polymarket_predictor.calibrator.calibrate import Calibrator

        portfolio = PaperPortfolio(data_dir=DATA_DIR)
        if not portfolio.get_open_positions():
            return  # Nothing to check

        history = PredictionHistory()
        calibrator = Calibrator()
        resolver = MarketResolver(portfolio, calibrator, history)
        results = asyncio.run(resolver.check_resolutions())
        if results:
            push_log(
                f"Auto-resolve: {len(results)} positions resolved",
                level="success",
            )
    except Exception as exc:
        logger.warning("Auto-resolve failed: %s", exc)
    finally:
        # Schedule next check in 5 minutes
        _resolution_timer = threading.Timer(300, _auto_resolve)
        _resolution_timer.daemon = True
        _resolution_timer.start()

# Start the auto-resolution timer when the blueprint is imported
_resolution_timer = threading.Timer(60, _auto_resolve)  # First check after 1 minute
_resolution_timer.daemon = True
_resolution_timer.start()


@dashboard_bp.route("/portfolio/reset", methods=["POST"])
def portfolio_reset():
    """Reset portfolio to fresh $10K state. Clears all positions."""
    try:
        import os
        portfolio_file = DATA_DIR / "portfolio.jsonl"
        if portfolio_file.exists():
            os.remove(portfolio_file)
        # Reset the global portfolio instance
        global _portfolio
        from polymarket_predictor.paper_trader.portfolio import PaperPortfolio
        _portfolio = PaperPortfolio(data_dir=DATA_DIR)
        # Reset autopilot so it picks up new portfolio
        global _autopilot
        _autopilot = None
        push_log("Portfolio reset to $10,000", level="success")
        return jsonify({
            "success": True,
            "data": {"balance": _portfolio.balance, "message": "Portfolio reset to $10,000"}
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@dashboard_bp.route("/strategy", methods=["GET"])
def strategy_config():
    """Get current strategy config."""
    try:
        from polymarket_predictor.optimizer.strategy import StrategyOptimizer
        optimizer = StrategyOptimizer(data_dir=DATA_DIR)
        return jsonify({"success": True, "data": optimizer.get_config()}), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Backtest endpoints
# ---------------------------------------------------------------------------

_backtest_results: dict = {}


def _run_backtest(task_id: str, num_markets: int, mode: str) -> None:
    """Execute a backtest in a background thread."""

    async def _execute():
        from polymarket_predictor.backtest.engine import BacktestEngine

        engine = BacktestEngine(data_dir=DATA_DIR)

        push_log(f"Starting backtest: {num_markets} markets, mode={mode}")
        _deep_tasks[task_id]["progress"] = {"current": 0, "total": num_markets}

        def on_progress(current, total, detail=""):
            _deep_tasks[task_id]["progress"] = {"current": current, "total": total}
            push_log(f"Backtesting {current}/{total}... {detail}")

        results = await engine.run_backtest(
            num_markets=num_markets,
            mode=mode,
        )
        return results

    try:
        result = asyncio.run(_execute())
        push_log(
            f"Backtest complete: {result.get('total_bets', 0)} bets, "
            f"win rate {result.get('win_rate', 0):.1%}, "
            f"P&L ${result.get('total_pnl', 0):+.2f}",
            level="success",
        )
        _backtest_results["latest"] = result
        _deep_tasks[task_id].update({"status": "completed", "result": result})
    except Exception as exc:
        logger.exception("Backtest task %s failed", task_id)
        push_log(f"Backtest failed: {exc}", level="error")
        _deep_tasks[task_id].update({"status": "failed", "error": str(exc)})


def _run_incremental_backtest(task_id: str, batch_size: int, total_batches: int) -> None:
    """Execute an incremental backtest with optimization between batches."""

    async def _execute():
        from polymarket_predictor.backtest.engine import BacktestEngine

        engine = BacktestEngine(data_dir=DATA_DIR)

        push_log(f"Starting incremental backtest: {total_batches} batches x {batch_size} markets")
        _deep_tasks[task_id]["progress"] = {"current_batch": 0, "total_batches": total_batches}
        _deep_tasks[task_id]["batch_results"] = []

        def on_batch_progress(batch_num, current, total, detail=""):
            _deep_tasks[task_id]["progress"] = {
                "current_batch": batch_num,
                "total_batches": total_batches,
                "batch_current": current,
                "batch_total": total,
            }
            push_log(f"Batch {batch_num}/{total_batches}: {current}/{total} {detail}")

        results = await engine.run_incremental(
            batch_size=batch_size,
            total_batches=total_batches,
        )
        return results

    try:
        result = asyncio.run(_execute())
        # run_incremental returns a list of batch results or a dict with "batches"
        if isinstance(result, list):
            batches = result
        else:
            batches = result.get("batches", [])

        # Build aggregate summary across ALL batches
        all_markets = []
        total_bets = 0
        total_wins = 0
        total_losses = 0
        total_pnl = 0.0
        total_wagered = 0.0
        for b in batches:
            total_bets += b.get("total_bets", 0)
            total_wins += b.get("wins", 0)
            total_losses += b.get("losses", 0)
            total_pnl += b.get("pnl", 0)
            total_wagered += sum(
                m.get("bet_amount", 0) for m in b.get("market_results", []) if m.get("bet_amount", 0) > 0
            )
            all_markets.extend(b.get("market_results", []))

        summary = {
            "total_bets": total_bets,
            "wins": total_wins,
            "losses": total_losses,
            "win_rate": (total_wins / total_bets) if total_bets > 0 else 0,
            "total_pnl": round(total_pnl, 2),
            "pnl": round(total_pnl, 2),
            "roi": round(total_pnl / total_wagered, 4) if total_wagered > 0 else 0,
            "total_wagered": round(total_wagered, 2),
            "balance": round(10000 + total_pnl, 2),
            "market_results": all_markets,
        }
        wrapped = {"batches": batches, "summary": summary}
        if batches:
            push_log(
                f"Incremental backtest complete: {len(batches)} batches, "
                f"total bets: {total_bets}, wins: {total_wins}, P&L: ${total_pnl:+,.2f}",
                level="success",
            )
        else:
            push_log("Incremental backtest complete: no batches", level="success")
        _backtest_results["latest"] = wrapped.get("summary", wrapped)
        _backtest_results["incremental"] = wrapped
        _deep_tasks[task_id].update({"status": "completed", "result": wrapped})
    except Exception as exc:
        logger.exception("Incremental backtest task %s failed", task_id)
        push_log(f"Incremental backtest failed: {exc}", level="error")
        _deep_tasks[task_id].update({"status": "failed", "error": str(exc)})


@dashboard_bp.route("/backtest/run", methods=["POST"])
def backtest_run():
    """Run a backtest on resolved markets. Body: {num_markets: 50, mode: 'quick'}"""
    data = request.get_json(silent=True) or {}
    num_markets = int(data.get("num_markets", 50))
    mode = data.get("mode", "quick")

    task_id = uuid.uuid4().hex[:12]
    _deep_tasks[task_id] = {"status": "running", "type": "backtest", "progress": {}}

    thread = threading.Thread(
        target=_run_backtest,
        args=(task_id, num_markets, mode),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "task_id": task_id, "status": "running"}), 202


@dashboard_bp.route("/backtest/run/<task_id>", methods=["GET"])
def backtest_status(task_id):
    """Check backtest status. Returns progress + results when done."""
    task = _deep_tasks.get(task_id)
    if task is None:
        return jsonify({"success": False, "error": f"Task '{task_id}' not found"}), 404

    response: dict = {"success": True, "task_id": task_id, "status": task["status"]}

    if task.get("progress"):
        response["progress"] = task["progress"]
    if task.get("batch_results"):
        response["batch_results"] = task["batch_results"]

    if task["status"] == "completed":
        response["result"] = task["result"]
    elif task["status"] == "failed":
        response["error"] = task.get("error", "Unknown error")

    return jsonify(response), 200


@dashboard_bp.route("/backtest/incremental", methods=["POST"])
def backtest_incremental():
    """Run incremental backtest with optimization between batches.
    Body: {batch_size: 10, total_batches: 5}"""
    data = request.get_json(silent=True) or {}
    batch_size = int(data.get("batch_size", 10))
    total_batches = int(data.get("total_batches", 5))

    task_id = uuid.uuid4().hex[:12]
    _deep_tasks[task_id] = {
        "status": "running",
        "type": "incremental_backtest",
        "progress": {},
        "batch_results": [],
    }

    thread = threading.Thread(
        target=_run_incremental_backtest,
        args=(task_id, batch_size, total_batches),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "task_id": task_id, "status": "running"}), 202


@dashboard_bp.route("/backtest/results", methods=["GET"])
def backtest_results():
    """Get latest backtest results summary."""
    if not _backtest_results:
        return jsonify({"success": True, "data": None, "message": "No backtest results yet"}), 200

    return jsonify({
        "success": True,
        "data": {
            "latest": _backtest_results.get("latest"),
            "incremental": _backtest_results.get("incremental"),
        },
    }), 200


@dashboard_bp.route("/backtest/reset", methods=["POST"])
def backtest_reset():
    """Reset backtest data for fresh run."""
    _backtest_results.clear()
    # Also remove any completed/failed backtest tasks
    to_remove = [tid for tid, t in _deep_tasks.items() if t.get("type") in ("backtest", "incremental_backtest")]
    for tid in to_remove:
        del _deep_tasks[tid]
    push_log("Backtest data reset", level="info")
    return jsonify({"success": True, "message": "Backtest data reset"}), 200


# ---------------------------------------------------------------------------
# Decision Ledger endpoints
# ---------------------------------------------------------------------------


@dashboard_bp.route("/ledger/entries", methods=["GET"])
def ledger_entries():
    """Get ledger entries. Query params: type, market_id, cycle_id, limit, offset"""
    entry_type = request.args.get("type")
    market_id = request.args.get("market_id")
    cycle_id = request.args.get("cycle_id")
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))

    try:
        entries = _ledger.get_entries(
            entry_type=entry_type,
            market_id=market_id,
            cycle_id=cycle_id,
            limit=limit,
            offset=offset,
        )
        return jsonify({
            "success": True,
            "data": {
                "entries": [e.to_dict() for e in entries],
                "count": len(entries),
            },
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@dashboard_bp.route("/ledger/recent", methods=["GET"])
def ledger_recent():
    """Get most recent N entries. Query param: limit (default 20)"""
    limit = int(request.args.get("limit", 20))

    try:
        entries = _ledger.get_recent(limit=limit)
        return jsonify({
            "success": True,
            "data": {
                "entries": [e.to_dict() for e in entries],
                "count": len(entries),
            },
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@dashboard_bp.route("/ledger/stats", methods=["GET"])
def ledger_stats():
    """Get ledger summary stats."""
    try:
        stats = _ledger.get_stats()
        return jsonify({"success": True, "data": stats}), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@dashboard_bp.route("/ledger/search", methods=["GET"])
def ledger_search():
    """Search entries. Query param: q, limit"""
    query = request.args.get("q", "").strip()
    limit = int(request.args.get("limit", 50))

    if not query:
        return jsonify({"success": False, "error": "Query parameter 'q' is required"}), 400

    try:
        entries = _ledger.search(query=query, limit=limit)
        return jsonify({
            "success": True,
            "data": {
                "entries": [e.to_dict() for e in entries],
                "count": len(entries),
                "query": query,
            },
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@dashboard_bp.route("/ledger/cycle/<cycle_id>", methods=["GET"])
def ledger_cycle(cycle_id):
    """Get all entries for a specific cycle."""
    try:
        entries = _ledger.get_cycle_entries(cycle_id)
        return jsonify({
            "success": True,
            "data": {
                "entries": [e.to_dict() for e in entries],
                "count": len(entries),
                "cycle_id": cycle_id,
            },
        }), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Autopilot endpoints
# ---------------------------------------------------------------------------


_autopilot_tasks: dict[str, dict] = {}


def _run_autopilot_cycle(task_id: str, quick_only: bool) -> None:
    """Execute an autopilot cycle in a background thread."""
    try:
        engine = _get_autopilot()
        if quick_only:
            result = asyncio.run(engine.run_cycle_quick_only())
        else:
            result = asyncio.run(engine.run_cycle())
        _autopilot_tasks[task_id].update({"status": "completed", "result": result})
    except Exception as exc:
        logger.exception("Autopilot cycle %s failed", task_id)
        push_log(f"Autopilot cycle failed: {exc}", level="error")
        _autopilot_tasks[task_id].update({"status": "failed", "error": str(exc)})


@dashboard_bp.route("/autopilot/run", methods=["POST"])
def autopilot_run():
    """Start an autopilot cycle. Body: {quick_only: false}"""
    data = request.get_json(silent=True) or {}
    quick_only = bool(data.get("quick_only", False))

    task_id = uuid.uuid4().hex[:12]
    _autopilot_tasks[task_id] = {"status": "running", "quick_only": quick_only}

    thread = threading.Thread(
        target=_run_autopilot_cycle,
        args=(task_id, quick_only),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": "running",
    }), 202


@dashboard_bp.route("/autopilot/run/<task_id>", methods=["GET"])
def autopilot_status(task_id):
    """Check autopilot cycle status."""
    task = _autopilot_tasks.get(task_id)
    if task is None:
        return jsonify({"success": False, "error": f"Task '{task_id}' not found"}), 404

    response = {"success": True, "task_id": task_id, "status": task["status"]}

    if task["status"] == "completed":
        response["result"] = task.get("result")
    elif task["status"] == "failed":
        response["error"] = task.get("error", "Unknown error")

    return jsonify(response), 200


@dashboard_bp.route("/autopilot/config", methods=["GET"])
def autopilot_config_get():
    """Get current autopilot config."""
    return jsonify({
        "success": True,
        "data": _get_autopilot().get_config(),
    }), 200


@dashboard_bp.route("/autopilot/config", methods=["PUT"])
def autopilot_config_update():
    """Update autopilot config. Body: {max_deep_per_cycle: 3, ...}"""
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"success": False, "error": "No config values provided"}), 400

    try:
        _get_autopilot().update_config(**data)
        return jsonify({"success": True, "data": _get_autopilot().get_config()}), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Cost Calculator & Pipeline Config endpoints
# ---------------------------------------------------------------------------

@dashboard_bp.route("/cost/estimate", methods=["GET"])
def cost_estimate():
    """Estimate cost for a single deep prediction with current config."""
    rounds = int(request.args.get("rounds", 15))
    agents = int(request.args.get("agents", 10))
    calc = CostCalculator()
    return jsonify({"success": True, "data": calc.estimate_prediction_cost(rounds, agents).to_dict()})


@dashboard_bp.route("/cost/compare", methods=["GET"])
def cost_compare():
    """Compare cost across different model configurations."""
    rounds = int(request.args.get("rounds", 15))
    agents = int(request.args.get("agents", 10))
    calc = CostCalculator()
    return jsonify({"success": True, "data": calc.compare_configurations(rounds, agents)})


@dashboard_bp.route("/cost/batch", methods=["GET"])
def cost_batch():
    """Estimate cost for a batch of predictions."""
    num = int(request.args.get("num", 50))
    rounds = int(request.args.get("rounds", 15))
    agents = int(request.args.get("agents", 10))
    calc = CostCalculator()
    return jsonify({"success": True, "data": calc.estimate_batch_cost(num, rounds, agents)})


@dashboard_bp.route("/pipeline/config", methods=["GET"])
def pipeline_config():
    """Get current pipeline model configuration (keys redacted)."""
    stages = {}
    for stage in ["ontology", "graph", "profiles", "simulation", "report"]:
        cfg = get_stage_config(stage)
        stages[stage] = {
            "model": cfg["model"],
            "base_url": cfg["base_url"],
            "has_api_key": bool(cfg["api_key"]),
            "price_input": cfg["price_input"],
            "price_output": cfg["price_output"],
        }
    return jsonify({"success": True, "data": stages})


# ---------------------------------------------------------------------------
# Overnight / Rolling Loop Endpoints
# ---------------------------------------------------------------------------

_overnight_runner = None
_overnight_thread = None


@dashboard_bp.route("/overnight/start", methods=["POST"])
def overnight_start():
    """Start an overnight calibration run.
    Body: {total: 50, budget: 25.0}
    Resumes from checkpoint if interrupted.
    """
    global _overnight_runner, _overnight_thread

    data = request.get_json(silent=True) or {}
    total = int(data.get("total", 50))
    budget = float(data.get("budget", 25.0))

    from polymarket_predictor.overnight.runner import OvernightRunner
    _overnight_runner = OvernightRunner(total=total, budget=budget)

    def _run():
        asyncio.run(_overnight_runner.run())

    _overnight_thread = threading.Thread(target=_run, daemon=True)
    _overnight_thread.start()

    return jsonify({"success": True, "status": "started", "total": total, "budget": budget}), 202


@dashboard_bp.route("/overnight/stop", methods=["POST"])
def overnight_stop():
    """Gracefully stop the overnight run after current prediction."""
    global _overnight_runner
    if _overnight_runner:
        _overnight_runner.request_stop()
        return jsonify({"success": True, "status": "stop_requested"})
    return jsonify({"success": False, "error": "No run in progress"}), 400


@dashboard_bp.route("/overnight/status", methods=["GET"])
def overnight_status():
    """Get current overnight run state."""
    from polymarket_predictor.overnight.state import StateManager
    sm = StateManager()
    state = sm.load()
    return jsonify({
        "success": True,
        "data": {
            "run_id": state.run_id,
            "mode": state.mode,
            "status": state.status,
            "current_round": state.current_round,
            "completed": state.completed,
            "failed": state.failed,
            "skipped": state.skipped,
            "total_target": state.total_target,
            "total_cost_usd": round(state.total_cost_usd, 2),
            "max_budget_usd": state.max_budget_usd,
            "current_market": state.current_market,
            "current_phase": state.current_phase,
            "started_at": state.started_at,
            "last_checkpoint_at": state.last_checkpoint_at,
            "results_count": len(state.results),
            "recent_results": state.results[-5:] if state.results else [],
            "recent_errors": state.errors[-5:] if state.errors else [],
            "strategy_version": state.strategy_version,
        },
    })


@dashboard_bp.route("/overnight/results", methods=["GET"])
def overnight_results():
    """Get all overnight results."""
    from polymarket_predictor.overnight.state import StateManager
    sm = StateManager()
    state = sm.load()
    return jsonify({
        "success": True,
        "data": {
            "results": state.results,
            "summary": {
                "completed": state.completed,
                "failed": state.failed,
                "total_cost_usd": round(state.total_cost_usd, 2),
                "avg_cost": round(state.total_cost_usd / max(state.completed, 1), 4),
                "predictions_with_edge": sum(1 for r in state.results if abs(r.get("edge", 0) or 0) > 0.03),
                "bets_placed": sum(1 for r in state.results if r.get("bet_placed")),
            },
        },
    })


# Rolling loop endpoints
_rolling_loop = None
_rolling_thread = None


@dashboard_bp.route("/rolling/start", methods=["POST"])
def rolling_start():
    """Start a continuous rolling trading loop.
    Body: {round_interval: 3600, deep_per_round: 3, budget_per_round: 12, max_budget: 100}
    """
    global _rolling_loop, _rolling_thread

    data = request.get_json(silent=True) or {}

    from polymarket_predictor.overnight.runner import RollingLoop
    _rolling_loop = RollingLoop(
        round_interval=int(data.get("round_interval", 3600)),
        deep_per_round=int(data.get("deep_per_round", 3)),
        budget_per_round=float(data.get("budget_per_round", 12.0)),
        max_total_budget=float(data.get("max_budget", 100.0)),
    )

    def _run():
        asyncio.run(_rolling_loop.run())

    _rolling_thread = threading.Thread(target=_run, daemon=True)
    _rolling_thread.start()

    return jsonify({"success": True, "status": "started"}), 202


@dashboard_bp.route("/rolling/stop", methods=["POST"])
def rolling_stop():
    """Gracefully stop the rolling loop after current round."""
    global _rolling_loop
    if _rolling_loop:
        _rolling_loop.request_stop()
        return jsonify({"success": True, "status": "stop_requested"})
    return jsonify({"success": False, "error": "No loop running"}), 400


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------
_monte_carlo_results: dict = {}


def _run_monte_carlo(task_id: str, num_simulations: int, num_bets: int,
                     accuracies: list[float] | None, edge_thresholds: list[float] | None,
                     kelly_factors: list[float] | None):
    """Background worker for Monte Carlo simulation."""
    from polymarket_predictor.monte_carlo.simulator import MonteCarloSimulator

    try:
        push_log(f"[Monte Carlo] Starting simulation (task={task_id})", level="info")
        sim = MonteCarloSimulator()

        # Fetch resolved markets
        push_log("[Monte Carlo] Fetching resolved markets from Polymarket...")
        markets = asyncio.run(sim.fetch_resolved_markets(limit=200, min_volume=500))
        push_log(f"[Monte Carlo] Loaded {len(markets)} resolved markets")

        _deep_tasks[task_id]["progress"] = {
            "markets_loaded": len(markets),
            "status": "running_sweep",
        }

        def on_progress(idx, total, label):
            pct = round(idx / total * 100, 1)
            _deep_tasks[task_id]["progress"] = {
                "markets_loaded": len(markets),
                "combo_index": idx,
                "total_combos": total,
                "percent": pct,
                "current": label,
            }
            if idx % 8 == 0 or idx == total:
                push_log(f"[Monte Carlo] {pct}% — {label} ({idx}/{total})")

        results = sim.run_parameter_sweep(
            markets=markets,
            num_simulations=num_simulations,
            accuracies=accuracies,
            edge_thresholds=edge_thresholds,
            kelly_factors=kelly_factors,
            num_bets=num_bets,
            progress_callback=on_progress,
        )

        # Store results globally and in the task
        global _monte_carlo_results
        _monte_carlo_results = results

        # Also persist to disk
        results_path = DATA_DIR / "monte_carlo_results.json"
        results_path.write_text(json.dumps(results, indent=2))

        _deep_tasks[task_id]["status"] = "completed"
        _deep_tasks[task_id]["result"] = results

        be = results.get("break_even")
        if be:
            push_log(
                f"[Monte Carlo] DONE — Break-even accuracy: {be['accuracy']:.0%} "
                f"(edge={be['edge_threshold']:.0%}, kelly={be['kelly_factor']}, "
                f"P(profit)={be['probability_of_profit']:.0%})",
                level="info",
            )
        else:
            push_log("[Monte Carlo] DONE — No break-even found in tested range", level="warn")

    except Exception as exc:
        logger.exception("Monte Carlo failed")
        _deep_tasks[task_id]["status"] = "failed"
        _deep_tasks[task_id]["error"] = str(exc)
        push_log(f"[Monte Carlo] FAILED: {exc}", level="error")


@dashboard_bp.route("/monte-carlo/run", methods=["POST"])
def monte_carlo_run():
    """Run Monte Carlo simulation. Body: {num_simulations: 1000, num_bets: 50}"""
    data = request.get_json(silent=True) or {}
    num_simulations = int(data.get("num_simulations", 1000))
    num_bets = int(data.get("num_bets", 50))
    accuracies = data.get("accuracies")
    edge_thresholds = data.get("edge_thresholds")
    kelly_factors = data.get("kelly_factors")

    task_id = uuid.uuid4().hex[:12]
    _deep_tasks[task_id] = {"status": "running", "type": "monte_carlo", "progress": {}}

    thread = threading.Thread(
        target=_run_monte_carlo,
        args=(task_id, num_simulations, num_bets, accuracies, edge_thresholds, kelly_factors),
        daemon=True,
    )
    thread.start()

    return jsonify({"success": True, "task_id": task_id, "status": "running"}), 202


@dashboard_bp.route("/monte-carlo/run/<task_id>", methods=["GET"])
def monte_carlo_status(task_id):
    """Check Monte Carlo status."""
    task = _deep_tasks.get(task_id)
    if task is None:
        return jsonify({"success": False, "error": f"Task '{task_id}' not found"}), 404

    response: dict = {"success": True, "task_id": task_id, "status": task["status"]}

    if task.get("progress"):
        response["progress"] = task["progress"]

    if task["status"] == "completed":
        response["result"] = task["result"]
    elif task["status"] == "failed":
        response["error"] = task.get("error", "Unknown error")

    return jsonify(response), 200


@dashboard_bp.route("/monte-carlo/results", methods=["GET"])
def monte_carlo_results():
    """Get latest Monte Carlo results."""
    global _monte_carlo_results

    # Try in-memory first
    if _monte_carlo_results:
        return jsonify({"success": True, "data": _monte_carlo_results}), 200

    # Try disk cache
    results_path = DATA_DIR / "monte_carlo_results.json"
    if results_path.exists():
        _monte_carlo_results = json.loads(results_path.read_text())
        return jsonify({"success": True, "data": _monte_carlo_results}), 200

    return jsonify({"success": True, "data": None, "message": "No Monte Carlo results yet"}), 200


# ---------------------------------------------------------------------------
# Method Comparison endpoints
# ---------------------------------------------------------------------------

@dashboard_bp.route("/methods/performance", methods=["GET"])
def methods_performance():
    """Get prediction method comparison performance."""
    from polymarket_predictor.analyzer.method_tracker import MethodTracker
    tracker = MethodTracker()
    return jsonify({"success": True, "data": tracker.get_performance()})


@dashboard_bp.route("/methods/comparisons", methods=["GET"])
def methods_comparisons():
    """Get recent method comparisons."""
    from polymarket_predictor.analyzer.method_tracker import MethodTracker
    limit = int(request.args.get("limit", 20))
    tracker = MethodTracker()
    return jsonify({"success": True, "data": tracker.get_recent_comparisons(limit)})


@dashboard_bp.route("/methods/weights", methods=["GET"])
def methods_weights():
    """Get current blending weights."""
    from polymarket_predictor.analyzer.method_tracker import MethodTracker
    tracker = MethodTracker()
    return jsonify({
        "success": True,
        "data": {
            "llm_weight": tracker.llm_weight,
            "quant_weight": tracker.quant_weight,
        },
    })
