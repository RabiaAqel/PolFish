"""Rapid calibration experiment runner.

Runs the same market through multiple configurations to compare
prediction quality across different agent counts, round counts,
and model choices.

Each round produces paired predictions on the same market,
enabling direct A/B comparison when the market resolves.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """A single prediction configuration to test."""
    name: str                    # e.g., "50_agents_deepseek"
    agents: int                  # MAX_TEMPLATE_AGENTS value
    rounds: int                  # MAX_SIMULATION_ROUNDS value
    preset: str                  # Pipeline preset
    description: str = ""       # Human description

    def to_dict(self):
        return asdict(self)


@dataclass
class PredictionResult:
    """Result of one prediction within an experiment round."""
    config_name: str
    market_slug: str
    market_question: str
    market_odds: float
    prediction: Optional[float] = None
    edge: Optional[float] = None
    signal: Optional[str] = None
    confidence: Optional[str] = None
    side: Optional[str] = None
    bet_placed: bool = False
    bet_amount: float = 0.0
    agents_count: int = 0
    rounds_run: int = 0
    preset: str = ""
    simulation_model: str = ""
    report_model: str = ""
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    status: str = "pending"     # pending, running, completed, failed
    error: Optional[str] = None
    # Outcome (filled when market resolves)
    resolved: bool = False
    outcome_yes: Optional[bool] = None
    was_correct: Optional[bool] = None


@dataclass
class ExperimentRound:
    """One round = one market tested with multiple configurations."""
    round_id: str
    market_slug: str
    market_question: str
    market_odds: float
    market_category: str
    market_closes_at: str
    configs: list[ExperimentConfig] = field(default_factory=list)
    results: list[PredictionResult] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    status: str = "pending"     # pending, running, completed


@dataclass
class ExperimentState:
    """Full experiment state, checkpointed to disk."""
    experiment_id: str = ""
    description: str = ""
    rounds: list[dict] = field(default_factory=list)  # List of ExperimentRound dicts
    total_rounds: int = 0
    completed_rounds: int = 0
    total_predictions: int = 0
    completed_predictions: int = 0
    total_cost_usd: float = 0.0
    started_at: str = ""
    status: str = "idle"


class ExperimentRunner:
    """Run paired prediction experiments across configurations."""

    def __init__(self, data_dir: Path = None):
        from polymarket_predictor.config import DATA_DIR
        self._dir = data_dir or DATA_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "experiment_state.json"
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def _save_state(self, state: ExperimentState):
        state_dict = asdict(state)
        tmp = self._state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state_dict, indent=2, default=str))
        import os
        os.replace(tmp, self._state_file)

    def _load_state(self) -> ExperimentState:
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                return ExperimentState(**{k: v for k, v in data.items() if k in ExperimentState.__dataclass_fields__})
            except:
                pass
        return ExperimentState()

    def get_state(self) -> dict:
        return asdict(self._load_state())

    async def run_round(
        self,
        market_slug: str,
        configs: list[ExperimentConfig],
        include_control: bool = True,
    ) -> ExperimentRound:
        """Run one experiment round: same market, multiple configurations.

        Args:
            market_slug: Polymarket market slug to predict
            configs: List of configurations to test
            include_control: If True, also run a single LLM call (no simulation) as control
        """
        try:
            from polymarket_predictor.dashboard.api import push_log
        except:
            def push_log(msg, level="info"):
                logger.info("[experiment] %s", msg)

        from polymarket_predictor.scrapers.polymarket import PolymarketScraper
        from polymarket_predictor.scrapers.news import NewsAggregator
        from polymarket_predictor.seeds.generator import SeedGenerator
        from polymarket_predictor.orchestrator.pipeline import MiroFishPipeline
        from polymarket_predictor.parser.prediction import PredictionParser
        from polymarket_predictor.paper_trader.portfolio import PaperPortfolio, BetSizer
        from polymarket_predictor.analyzer.simulation_analyzer import SimulationAnalyzer
        from polymarket_predictor.analyzer.method_tracker import MethodTracker
        from polymarket_predictor.knowledge.context_store import ContextStore, MarketContext
        from polymarket_predictor.config import DATA_DIR, get_stage_config

        # Fetch market info
        push_log(f"[EXPERIMENT] Fetching market: {market_slug}")
        async with PolymarketScraper() as scraper:
            market = await scraper.get_market_by_slug(market_slug)
            if not market:
                raise ValueError(f"Market not found: {market_slug}")

        yes_price = 0.5
        for o in market.outcomes:
            if isinstance(o, dict) and o.get('name', '').lower() in ('yes', 'up'):
                yes_price = float(o.get('price', 0.5))
                break

        closes_at = market.end_date.isoformat() if market.end_date else ""
        category = market.category or "other"

        round_obj = ExperimentRound(
            round_id=f"round_{uuid.uuid4().hex[:8]}",
            market_slug=market_slug,
            market_question=market.question,
            market_odds=yes_price,
            market_category=category,
            market_closes_at=closes_at,
            configs=configs,
            started_at=datetime.now(timezone.utc).isoformat(),
            status="running",
        )

        push_log(f"[EXPERIMENT] Market: {market.question[:60]}")
        push_log(f"[EXPERIMENT] Odds: {yes_price:.0%} | Category: {category} | Closes: {closes_at[:10]}")
        push_log(f"[EXPERIMENT] Running {len(configs)} configurations" + (" + control" if include_control else ""))

        # Generate seed ONCE (shared across all configs) — use DEEP research
        push_log("[EXPERIMENT] Generating shared seed document (deep research)...")
        news = NewsAggregator()
        gen = SeedGenerator()
        try:
            try:
                research = await news.search_articles_deep(
                    market.question, max_results=10, market_slug=market_slug,
                )
                seed_path = gen.generate_deep_seed(market, research, variant="balanced")
                push_log(
                    f"[EXPERIMENT] Deep seed: {seed_path.stat().st_size:,} bytes, "
                    f"{research.sources_count} sources, {research.total_words} words"
                )
            except Exception as e:
                logger.warning("Deep research failed, falling back to basic: %s", e)
                push_log(f"[EXPERIMENT] Deep research failed ({e}), using basic seed")
                articles = await news.search_articles(market.question, max_results=5)
                seed_path = gen.generate_seed(market, articles, variant="balanced")
                push_log(f"[EXPERIMENT] Basic seed: {seed_path.stat().st_size} bytes, {len(articles)} articles")
        finally:
            await news.close()

        portfolio = PaperPortfolio(data_dir=DATA_DIR)
        sizer = BetSizer()

        # Run each configuration sequentially
        for i, config in enumerate(configs):
            if self._stop_requested:
                push_log("[EXPERIMENT] Stop requested, skipping remaining configs")
                break

            result = PredictionResult(
                config_name=config.name,
                market_slug=market_slug,
                market_question=market.question,
                market_odds=yes_price,
                preset=config.preset,
                status="running",
            )

            push_log(f"\n[EXPERIMENT] Config {i+1}/{len(configs)}: {config.name}")
            push_log(f"  Agents: {config.agents} | Rounds: {config.rounds} | Preset: {config.preset}")

            start_time = time.time()

            try:
                import os
                old_preset = os.environ.get("PIPELINE_PRESET")
                old_rounds = os.environ.get("MAX_SIMULATION_ROUNDS")
                old_agents = os.environ.get("MAX_TEMPLATE_AGENTS")

                os.environ["PIPELINE_PRESET"] = config.preset
                os.environ["MAX_SIMULATION_ROUNDS"] = str(config.rounds)
                os.environ["MAX_TEMPLATE_AGENTS"] = str(config.agents)

                # Reload config
                import importlib
                import polymarket_predictor.config as cfg_mod
                importlib.reload(cfg_mod)

                enhanced_req = (
                    f"{market.question}\n\n"
                    f"[MARKET CONTEXT: Current YES price is {yes_price:.1%}. "
                    f"Category: {category}. Closes: {closes_at[:10]}]"
                )

                pipeline = MiroFishPipeline()
                try:
                    report = await pipeline.run(
                        seed_file_path=seed_path,
                        simulation_requirement=enhanced_req,
                        max_rounds=config.rounds,
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

                sim_id = report.get("simulation_id", "")

                # Quantitative analysis
                quant_pred = prediction.probability
                try:
                    analyzer = SimulationAnalyzer()
                    quant = analyzer.analyze(sim_id, market.question, yes_price)
                    tracker = MethodTracker()
                    quant_pred = tracker.blend(prediction.probability, quant.computed_probability)
                    result.agents_count = quant.total_agents
                    push_log(f"  LLM: {prediction.probability:.1%} | Quant: {quant.computed_probability:.1%} | Blend: {quant_pred:.1%}")
                except Exception as e:
                    logger.warning("Quant analysis failed: %s", e)
                    result.agents_count = config.agents

                elapsed = time.time() - start_time

                result.prediction = quant_pred
                result.edge = round(quant_pred - yes_price, 4)
                result.signal = "BUY_YES" if result.edge > 0.03 else ("BUY_NO" if result.edge < -0.03 else "SKIP")
                result.confidence = prediction.confidence
                result.side = "YES" if result.edge > 0 else "NO"
                result.rounds_run = config.rounds
                result.simulation_model = cfg_mod.get_stage_config("simulation")["model"]
                result.report_model = cfg_mod.get_stage_config("report")["model"]
                result.duration_seconds = round(elapsed, 1)
                result.cost_usd = 0.10  # TODO: get from cost tracker
                result.status = "completed"

                push_log(
                    f"  RESULT: pred={quant_pred:.1%} edge={result.edge:+.1%} "
                    f"signal={result.signal} ({elapsed:.0f}s)"
                )

                # Place paper bet
                abs_edge = abs(result.edge)
                if abs_edge >= 0.03:
                    bet_info = sizer.size_bet(
                        portfolio.balance, quant_pred, yes_price,
                        abs_edge, prediction.confidence,
                    )
                    if bet_info["amount"] > 0:
                        portfolio.place_bet(
                            market_id=market_slug, slug=market_slug,
                            question=market.question,
                            side=result.side, amount=bet_info["amount"],
                            odds=yes_price, closes_at=closes_at,
                            prediction=quant_pred,
                            edge=abs_edge, confidence=prediction.confidence,
                            mode=f"experiment_{config.name}",
                            kelly_fraction=bet_info.get("kelly_fraction", 0.0),
                            cost_usd=result.cost_usd,
                        )
                        result.bet_placed = True
                        result.bet_amount = bet_info["amount"]
                        push_log(f"  BET: ${bet_info['amount']:.2f} {result.side}")

            except Exception as e:
                elapsed = time.time() - start_time
                result.status = "failed"
                result.error = str(e)[:200]
                result.duration_seconds = round(elapsed, 1)
                push_log(f"  FAILED: {e}", level="error")
                logger.exception("Experiment config %s failed", config.name)
            finally:
                # Restore env
                if old_preset: os.environ["PIPELINE_PRESET"] = old_preset
                elif "PIPELINE_PRESET" in os.environ: del os.environ["PIPELINE_PRESET"]
                if old_rounds: os.environ["MAX_SIMULATION_ROUNDS"] = old_rounds
                elif "MAX_SIMULATION_ROUNDS" in os.environ: del os.environ["MAX_SIMULATION_ROUNDS"]
                if old_agents: os.environ["MAX_TEMPLATE_AGENTS"] = old_agents
                elif "MAX_TEMPLATE_AGENTS" in os.environ: del os.environ["MAX_TEMPLATE_AGENTS"]
                importlib.reload(cfg_mod)

            round_obj.results.append(asdict(result))

        # Run control (single LLM call, no simulation) if requested
        if include_control and not self._stop_requested:
            push_log(f"\n[EXPERIMENT] Control: Single LLM call (no simulation)")
            ctrl_result = PredictionResult(
                config_name="control_single_llm",
                market_slug=market_slug,
                market_question=market.question,
                market_odds=yes_price,
                preset="n/a",
                status="running",
            )

            start_time = time.time()
            try:
                import httpx
                # Single LLM call with same context
                seed_text = seed_path.read_text()[:3000]
                prompt = (
                    f"You are a prediction market analyst. Based on the following context, "
                    f"what is the probability that the answer to this question is YES?\n\n"
                    f"Question: {market.question}\n"
                    f"Current market price: {yes_price:.1%} YES\n\n"
                    f"Context:\n{seed_text}\n\n"
                    f"Respond with ONLY a number between 0 and 100 representing the percentage probability."
                )

                from polymarket_predictor.config import get_stage_config
                cfg = get_stage_config("report")  # Use the report model for control

                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        f"{cfg['base_url']}/chat/completions",
                        headers={"Authorization": f"Bearer {cfg['api_key']}"},
                        json={
                            "model": cfg["model"],
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 20,
                            "temperature": 0.3,
                        },
                    )
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"].strip()

                    # Extract number
                    import re
                    match = re.search(r'(\d{1,3}(?:\.\d+)?)', content)
                    if match:
                        ctrl_prob = float(match.group(1)) / 100.0
                        ctrl_prob = max(0.01, min(0.99, ctrl_prob))
                    else:
                        ctrl_prob = 0.5

                elapsed = time.time() - start_time
                ctrl_result.prediction = ctrl_prob
                ctrl_result.edge = round(ctrl_prob - yes_price, 4)
                ctrl_result.signal = "BUY_YES" if ctrl_result.edge > 0.03 else ("BUY_NO" if ctrl_result.edge < -0.03 else "SKIP")
                ctrl_result.confidence = "medium"
                ctrl_result.side = "YES" if ctrl_result.edge > 0 else "NO"
                ctrl_result.agents_count = 0
                ctrl_result.rounds_run = 0
                ctrl_result.simulation_model = "none"
                ctrl_result.report_model = cfg["model"]
                ctrl_result.duration_seconds = round(elapsed, 1)
                ctrl_result.cost_usd = 0.01
                ctrl_result.status = "completed"

                push_log(f"  CONTROL: pred={ctrl_prob:.1%} edge={ctrl_result.edge:+.1%} ({elapsed:.0f}s, ${ctrl_result.cost_usd})")

            except Exception as e:
                ctrl_result.status = "failed"
                ctrl_result.error = str(e)[:200]
                push_log(f"  CONTROL FAILED: {e}", level="error")

            round_obj.results.append(asdict(ctrl_result))

        round_obj.completed_at = datetime.now(timezone.utc).isoformat()
        round_obj.status = "completed"

        # Save to experiment state
        state = self._load_state()
        if not state.experiment_id:
            state.experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            state.started_at = datetime.now(timezone.utc).isoformat()
            state.status = "running"
        state.rounds.append(asdict(round_obj))
        state.total_rounds += 1
        state.completed_rounds += 1
        state.total_predictions += len(round_obj.results)
        state.completed_predictions += sum(1 for r in round_obj.results if r.get("status") == "completed")
        state.total_cost_usd += sum(r.get("cost_usd", 0) for r in round_obj.results)
        self._save_state(state)

        # Summary
        push_log(f"\n[EXPERIMENT] Round complete: {round_obj.round_id}")
        push_log(f"  Market: {market.question[:50]}")
        for r in round_obj.results:
            status = "OK" if r["status"] == "completed" else "FAIL"
            pred = f"{r['prediction']:.1%}" if r.get("prediction") else "N/A"
            push_log(f"  {status} {r['config_name']:25s} pred={pred} edge={r.get('edge',0):+.1%} bet={'$'+str(round(r.get('bet_amount',0),2)) if r.get('bet_placed') else 'skip'}")

        return round_obj
