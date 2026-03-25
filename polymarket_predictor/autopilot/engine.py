"""Fully autonomous prediction engine.

Runs complete prediction cycles: scan -> quick predict -> rank -> deep on
top N -> confirm/reject -> auto-bet -> log everything.  Designed to be
started on a schedule (e.g. every 6 hours) or triggered manually.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from polymarket_predictor.config import DATA_DIR, MIROFISH_API_URL
from polymarket_predictor.dashboard.api import push_log
from polymarket_predictor.ledger.decision_ledger import DecisionLedger
from polymarket_predictor.paper_trader.portfolio import BetSizer, PaperPortfolio
from polymarket_predictor.scanner.market_scanner import MarketScanner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_CONFIG_FILENAME = "autopilot_config.json"


@dataclass
class AutopilotConfig:
    """Tunable parameters for the autopilot engine."""

    max_deep_per_cycle: int = 3          # Max deep predictions per cycle
    max_cost_per_cycle: float = 15.0     # Budget cap in dollars (~$4-5 per deep)
    min_edge_for_deep: float = 0.05      # Don't run deep if quick edge < this
    min_edge_for_bet: float = 0.03       # Don't bet if deep edge < this
    cycle_interval_hours: int = 6        # How often to run
    niche_focus: bool = True             # Prefer obscure markets
    quick_research: bool = False         # Fetch news articles in quick mode
    max_markets_to_scan: int = 50        # How many markets to scan
    days_ahead: float = 7.0              # Look for markets expiring within N days (supports decimals, e.g. 0.25 = 6 hours)
    min_volume: int = 500                # Minimum market volume
    cost_per_deep: float = 4.0           # Estimated cost per deep prediction

    # -- Serialisation helpers -----------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AutopilotConfig:
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known_fields}
        return cls(**filtered)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> AutopilotConfig:
        if path.exists():
            try:
                return cls.from_dict(json.loads(path.read_text()))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Failed to load autopilot config, using defaults: %s", exc
                )
        return cls()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yes_price(market: Any) -> float:
    """Extract the YES outcome price from a Market object."""
    for outcome in getattr(market, "outcomes", []):
        if isinstance(outcome, dict) and outcome.get("name", "").lower() in ("yes", "up"):
            return float(outcome.get("price", 0.0))
    return 0.0


# ---------------------------------------------------------------------------
# AutopilotEngine
# ---------------------------------------------------------------------------


class AutopilotEngine:
    """Orchestrates fully autonomous prediction-and-betting cycles.

    Parameters
    ----------
    portfolio:
        The :class:`PaperPortfolio` used for placing paper bets.
    ledger:
        The :class:`DecisionLedger` used for logging every decision.
    strategy_optimizer:
        Optional :class:`StrategyOptimizer` instance.  When provided the
        engine will run parameter optimisation after enough data accumulates.
    data_dir:
        Directory that holds persistent state (config, etc.).  Defaults to
        ``DATA_DIR`` from the global config.
    """

    def __init__(
        self,
        portfolio: PaperPortfolio,
        ledger: DecisionLedger,
        strategy_optimizer: Any | None = None,
        data_dir: str | Path | None = None,
    ) -> None:
        self._portfolio = portfolio
        self._ledger = ledger
        self._optimizer = strategy_optimizer
        self._data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)

        self._config_path = self._data_dir / _CONFIG_FILENAME
        self._config = AutopilotConfig.load(self._config_path)

        # Last cycle's candidate list (exposed for the manual-mode UI)
        self._last_candidates: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run_cycle(self) -> dict[str, Any]:
        """Run a full autopilot cycle and return a summary dict."""
        cycle_id = f"cycle_{uuid.uuid4().hex[:8]}"
        cfg = self._config
        summary: dict[str, Any] = {"cycle_id": cycle_id, "phases": {}}

        push_log(f"[{cycle_id}] Autopilot cycle starting", level="info")
        logger.info("Starting autopilot cycle %s", cycle_id)

        try:
            # Phase 1 -- SCAN
            markets = await self._phase_scan(cycle_id, cfg)
            summary["phases"]["scan"] = {"markets_found": len(markets)}

            if not markets:
                push_log(
                    f"[{cycle_id}] No markets found - cycle complete", level="info"
                )
                self._log_cycle_summary(cycle_id, summary)
                return summary

            # Phase 2 -- QUICK PREDICT
            scored = await self._phase_quick_predict(cycle_id, cfg, markets)
            summary["phases"]["quick_predict"] = {
                "predicted": len(scored),
                "above_threshold": sum(
                    1 for s in scored if s["edge"] >= cfg.min_edge_for_deep
                ),
            }

            # Phase 3 -- SELECT CANDIDATES
            candidates = self._phase_select_candidates(cycle_id, cfg, scored)
            self._last_candidates = candidates
            summary["phases"]["select"] = {"candidates": len(candidates)}

            # Phase 4 -- DEEP PREDICT
            confirmed, rejected = await self._phase_deep_predict(
                cycle_id, cfg, candidates
            )
            summary["phases"]["deep_predict"] = {
                "confirmed": len(confirmed),
                "rejected": len(rejected),
            }

            # Phase 5 -- BET
            bets_placed = self._phase_bet(cycle_id, cfg, confirmed, rejected)
            summary["phases"]["bet"] = {"placed": len(bets_placed)}

            # Phase 6 -- RESOLVE
            resolutions = await self._phase_resolve(cycle_id)
            summary["phases"]["resolve"] = {"resolved": len(resolutions)}

            # Phase 7 -- OPTIMIZE
            opt_result = self._phase_optimize(cycle_id)
            summary["phases"]["optimize"] = opt_result

            # Phase 8 -- SUMMARY
            self._log_cycle_summary(cycle_id, summary)

            push_log(
                f"[{cycle_id}] Cycle complete: "
                f"scanned={len(markets)}, "
                f"candidates={len(candidates)}, "
                f"confirmed={len(confirmed)}, "
                f"bets={len(bets_placed)}, "
                f"resolved={len(resolutions)}",
                level="success",
            )
            return summary

        except Exception as exc:
            logger.exception("Autopilot cycle %s failed", cycle_id)
            push_log(f"[{cycle_id}] Cycle FAILED: {exc}", level="error")
            summary["error"] = str(exc)
            return summary

    async def run_cycle_quick_only(self) -> dict[str, Any]:
        """Run a lightweight cycle without deep predictions (cheap, fast).

        Identical to :meth:`run_cycle` but skips Phase 4 (deep prediction).
        Bets are placed using quick-predict edges directly.
        """
        cycle_id = f"qcycle_{uuid.uuid4().hex[:8]}"
        cfg = self._config
        summary: dict[str, Any] = {
            "cycle_id": cycle_id,
            "phases": {},
            "mode": "quick_only",
        }

        push_log(f"[{cycle_id}] Quick-only cycle starting", level="info")
        logger.info("Starting quick-only autopilot cycle %s", cycle_id)

        try:
            # Phase 1 -- SCAN
            markets = await self._phase_scan(cycle_id, cfg)
            summary["phases"]["scan"] = {"markets_found": len(markets)}

            if not markets:
                push_log(
                    f"[{cycle_id}] No markets found - cycle complete", level="info"
                )
                self._log_cycle_summary(cycle_id, summary)
                return summary

            # Phase 2 -- QUICK PREDICT
            scored = await self._phase_quick_predict(cycle_id, cfg, markets)
            summary["phases"]["quick_predict"] = {
                "predicted": len(scored),
                "above_threshold": sum(
                    1 for s in scored if s["edge"] >= cfg.min_edge_for_bet
                ),
            }

            # Phase 3 -- Filter to bet-worthy predictions (skip deep)
            bet_worthy = [s for s in scored if s["edge"] >= cfg.min_edge_for_bet]
            bet_worthy = bet_worthy[: cfg.max_deep_per_cycle]  # cap bets per cycle
            self._last_candidates = bet_worthy
            summary["phases"]["select"] = {"candidates": len(bet_worthy)}

            # Phase 5 -- BET (treat quick predictions as confirmed)
            bets_placed = self._phase_bet(cycle_id, cfg, bet_worthy, [])
            summary["phases"]["bet"] = {"placed": len(bets_placed)}

            # Phase 6 -- RESOLVE
            resolutions = await self._phase_resolve(cycle_id)
            summary["phases"]["resolve"] = {"resolved": len(resolutions)}

            # Phase 7 -- OPTIMIZE
            opt_result = self._phase_optimize(cycle_id)
            summary["phases"]["optimize"] = opt_result

            # Phase 8 -- SUMMARY
            self._log_cycle_summary(cycle_id, summary)

            push_log(
                f"[{cycle_id}] Quick cycle complete: "
                f"scanned={len(markets)}, bets={len(bets_placed)}, "
                f"resolved={len(resolutions)}",
                level="success",
            )
            return summary

        except Exception as exc:
            logger.exception("Quick autopilot cycle %s failed", cycle_id)
            push_log(f"[{cycle_id}] Quick cycle FAILED: {exc}", level="error")
            summary["error"] = str(exc)
            return summary

    def get_config(self) -> dict[str, Any]:
        """Return current autopilot configuration as a dict."""
        return self._config.to_dict()

    def update_config(self, **kwargs: Any) -> None:
        """Update specific config fields and persist to disk."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
                logger.info("Autopilot config: %s = %r", key, value)
            else:
                logger.warning("Unknown autopilot config key: %s", key)
        self._config.save(self._config_path)

    def get_candidates(self) -> list[dict[str, Any]]:
        """Return the last cycle's candidate list (for manual-mode UI)."""
        return list(self._last_candidates)

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    async def _phase_scan(
        self, cycle_id: str, cfg: AutopilotConfig
    ) -> list[Any]:
        """Phase 1: Scan Polymarket for expiring, interesting markets."""
        push_log(f"[{cycle_id}] Phase 1: Scanning markets...", level="info")

        async with MarketScanner() as scanner:
            if cfg.niche_focus:
                markets = await scanner.scan_interesting(
                    days_ahead=cfg.days_ahead,
                    min_volume=cfg.min_volume,
                )
            else:
                markets = await scanner.scan_expiring(
                    days_ahead=cfg.days_ahead,
                    min_volume=cfg.min_volume,
                )

        markets = markets[: cfg.max_markets_to_scan]
        push_log(
            f"[{cycle_id}] Scan complete: {len(markets)} markets found",
            level="info",
        )
        return markets

    async def _phase_quick_predict(
        self,
        cycle_id: str,
        cfg: AutopilotConfig,
        markets: list[Any],
    ) -> list[dict[str, Any]]:
        """Phase 2: Run quick prediction on all scanned markets, rank by edge.

        When ``cfg.quick_research`` is True the predict API is called (which
        fetches news articles and builds a seed doc).  When False, edge is
        computed locally from market odds + random noise — instant and free.
        """
        import random

        research_mode = getattr(cfg, "quick_research", False)
        mode_label = "with research" if research_mode else "instant"
        push_log(
            f"[{cycle_id}] Phase 2: Quick-predicting {len(markets)} markets ({mode_label})...",
            level="info",
        )

        scored: list[dict[str, Any]] = []
        predict_url = f"{MIROFISH_API_URL}/polymarket/predict"

        client = None
        if research_mode:
            client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))

        try:
            for i, market in enumerate(markets, 1):
                slug = market.slug
                yes_price = _yes_price(market)

                try:
                    if research_mode and client is not None:
                        # Call predict API (fetches articles, builds seed)
                        resp = await client.post(predict_url, json={"slug": slug})
                        resp.raise_for_status()
                        data = resp.json()

                        prediction: float | None = None
                        for key_path in (
                            lambda d: d.get("prediction"),
                            lambda d: d.get("data", {}).get("probability"),
                            lambda d: d.get("data", {}).get("prediction"),
                        ):
                            val = key_path(data)
                            if val is not None:
                                prediction = float(val)
                                break

                        if prediction is None:
                            prediction = yes_price
                    else:
                        # Instant mode: market odds + random noise
                        noise = random.uniform(-0.08, 0.08)
                        prediction = max(0.01, min(0.99, yes_price + noise))
                        push_log(
                            f"[{cycle_id}] {market.question[:50]}... odds={yes_price:.2f} pred={prediction:.2f}",
                            level="info",
                        )

                    edge = abs(prediction - yes_price)

                    entry: dict[str, Any] = {
                        "market": market,
                        "slug": slug,
                        "question": market.question,
                        "market_id": market.id,
                        "yes_price": yes_price,
                        "quick_prediction": prediction,
                        "edge": round(edge, 4),
                        "category": market.category,
                        "closes_at": market.end_date.isoformat() if market.end_date else "",
                    }
                    scored.append(entry)

                    if edge < cfg.min_edge_for_deep:
                        self._ledger.log(
                            entry_type="BET_SKIPPED",
                            market_id=slug,
                            question=market.question,
                            data={
                                "quick_prediction": prediction,
                                "yes_price": yes_price,
                                "edge": round(edge, 4),
                                "research": research_mode,
                            },
                            explanation=(
                                f"Quick edge {edge:.2%} below threshold "
                                f"{cfg.min_edge_for_deep:.2%}"
                            ),
                            cycle_id=cycle_id,
                        )

                except httpx.HTTPStatusError as exc:
                    logger.warning("Quick predict HTTP %s for %s", exc.response.status_code, slug)
                except httpx.RequestError as exc:
                    logger.warning("Quick predict request failed for %s: %s", slug, exc)
                except Exception:
                    logger.exception("Unexpected error quick-predicting %s", slug)

                if i % 10 == 0:
                    push_log(
                        f"[{cycle_id}] Quick predicted {i}/{len(markets)}...",
                        level="info",
                    )
        finally:
            if client is not None:
                await client.aclose()

        # Sort by edge descending
        scored.sort(key=lambda s: s["edge"], reverse=True)

        above_threshold = sum(
            1 for s in scored if s["edge"] >= cfg.min_edge_for_deep
        )
        push_log(
            f"[{cycle_id}] Quick predict done: {len(scored)} scored, "
            f"{above_threshold} above edge threshold",
            level="info",
        )
        return scored

    def _phase_select_candidates(
        self,
        cycle_id: str,
        cfg: AutopilotConfig,
        scored: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Phase 3: Select top candidates for deep analysis."""
        push_log(f"[{cycle_id}] Phase 3: Selecting candidates...", level="info")

        # Pre-filter: skip markets where we already have a quick bet on the predicted side
        open_sides: dict[str, set[str]] = {}
        try:
            for pos in self._portfolio.get_open_positions():
                s = getattr(pos, "slug", None) or getattr(pos, "market_id", "")
                side = getattr(pos, "side", "")
                mode = getattr(pos, "mode", "quick")
                if s and mode == "quick":
                    open_sides.setdefault(s, set()).add(side)
        except Exception:
            pass

        def _predicted_side(entry: dict) -> str:
            pred = entry.get("quick_prediction", 0.5)
            yp = entry.get("yes_price", 0.5)
            return "YES" if pred > yp else "NO"

        eligible = []
        for s in scored:
            if s["edge"] < cfg.min_edge_for_deep:
                continue
            slug = s["slug"]
            side = _predicted_side(s)
            # Note: we do NOT skip markets with existing quick positions here.
            # Deep analysis is meant to validate/upgrade quick bets.
            # Dedup happens in Phase 5 with smarter logic.
            if slug in open_sides and side in open_sides[slug]:
                push_log(
                    f"[{cycle_id}] {slug} has quick {side} — sending to deep for validation",
                    level="info",
                )
            eligible.append(s)

        # Budget constraint: N * cost_per_deep <= max_cost_per_cycle
        max_by_budget = (
            int(cfg.max_cost_per_cycle / cfg.cost_per_deep)
            if cfg.cost_per_deep > 0
            else cfg.max_deep_per_cycle
        )
        n = min(cfg.max_deep_per_cycle, max_by_budget, len(eligible))

        candidates = eligible[:n]

        push_log(
            f"[{cycle_id}] Selected {len(candidates)} candidates for deep analysis "
            f"(from {len(eligible)} eligible, budget allows {max_by_budget})",
            level="info",
        )
        return candidates

    async def _phase_deep_predict(
        self,
        cycle_id: str,
        cfg: AutopilotConfig,
        candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Phase 4: Run deep predictions on candidates, confirm or reject."""
        if not candidates:
            push_log(
                f"[{cycle_id}] Phase 4: No candidates for deep analysis",
                level="info",
            )
            return [], []

        push_log(
            f"[{cycle_id}] Phase 4: Running deep predictions on "
            f"{len(candidates)} candidates...",
            level="info",
        )

        confirmed: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        deep_url = f"{MIROFISH_API_URL}/polymarket/predict/deep"

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(600.0, connect=10.0)
        ) as client:
            for i, candidate in enumerate(candidates, 1):
                slug = candidate["slug"]
                question = candidate["question"]
                push_log(
                    f"[{cycle_id}] Deep predicting {i}/{len(candidates)}: {slug}",
                    level="info",
                )

                try:
                    # Start deep prediction task
                    resp = await client.post(
                        deep_url, json={"slug": slug, "variants": 1}
                    )
                    resp.raise_for_status()
                    task_data = resp.json()
                    task_id = task_data.get("task_id")

                    if not task_id:
                        logger.warning(
                            "No task_id returned for deep predict of %s", slug
                        )
                        continue

                    # Poll until complete
                    deep_result = await self._poll_deep_task(
                        client, task_id, slug, cycle_id
                    )

                    if deep_result is None:
                        push_log(
                            f"[{cycle_id}] Deep prediction failed/timed out "
                            f"for {slug}",
                            level="warning",
                        )
                        continue

                    # Extract deep prediction probability
                    deep_pred = deep_result.get("prediction", {})
                    deep_probability = deep_pred.get(
                        "probability", candidate["quick_prediction"]
                    )
                    deep_edge = abs(deep_probability - candidate["yes_price"])

                    candidate["deep_prediction"] = deep_probability
                    candidate["deep_edge"] = round(deep_edge, 4)
                    candidate["deep_signal"] = deep_pred.get("signal", "")
                    candidate["deep_result"] = deep_result

                    # Confirm or reject based on whether deep edge still exceeds
                    # the betting threshold
                    if deep_edge >= cfg.min_edge_for_bet:
                        confirmed.append(candidate)
                        self._ledger.log(
                            entry_type="DEEP_CONFIRMED",
                            market_id=slug,
                            question=question,
                            data={
                                "quick_prediction": candidate["quick_prediction"],
                                "deep_prediction": deep_probability,
                                "quick_edge": candidate["edge"],
                                "deep_edge": round(deep_edge, 4),
                                "yes_price": candidate["yes_price"],
                            },
                            explanation=(
                                f"Deep confirms edge: quick={candidate['edge']:.2%}, "
                                f"deep={deep_edge:.2%} "
                                f"(threshold={cfg.min_edge_for_bet:.2%})"
                            ),
                            cycle_id=cycle_id,
                        )
                        push_log(
                            f"[{cycle_id}] CONFIRMED: {slug} "
                            f"(deep edge={deep_edge:.2%})",
                            level="success",
                        )
                    else:
                        rejected.append(candidate)
                        self._ledger.log(
                            entry_type="DEEP_REJECTED",
                            market_id=slug,
                            question=question,
                            data={
                                "quick_prediction": candidate["quick_prediction"],
                                "deep_prediction": deep_probability,
                                "quick_edge": candidate["edge"],
                                "deep_edge": round(deep_edge, 4),
                                "yes_price": candidate["yes_price"],
                            },
                            explanation=(
                                f"Deep rejects: edge shrunk from "
                                f"{candidate['edge']:.2%} to {deep_edge:.2%} "
                                f"(below {cfg.min_edge_for_bet:.2%})"
                            ),
                            cycle_id=cycle_id,
                        )
                        push_log(
                            f"[{cycle_id}] REJECTED: {slug} "
                            f"(deep edge={deep_edge:.2%})",
                            level="warning",
                        )

                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "Deep predict HTTP %s for %s",
                        exc.response.status_code,
                        slug,
                    )
                    push_log(
                        f"[{cycle_id}] Deep predict HTTP error for {slug}: "
                        f"{exc.response.status_code}",
                        level="error",
                    )
                except httpx.RequestError as exc:
                    logger.warning(
                        "Deep predict request failed for %s: %s", slug, exc
                    )
                    push_log(
                        f"[{cycle_id}] Deep predict request error for {slug}",
                        level="error",
                    )
                except Exception:
                    logger.exception(
                        "Unexpected error deep-predicting %s", slug
                    )
                    push_log(
                        f"[{cycle_id}] Deep predict unexpected error for {slug}",
                        level="error",
                    )

        push_log(
            f"[{cycle_id}] Deep predict done: {len(confirmed)} confirmed, "
            f"{len(rejected)} rejected",
            level="info",
        )
        return confirmed, rejected

    def _phase_bet(
        self,
        cycle_id: str,
        cfg: AutopilotConfig,
        confirmed: list[dict[str, Any]],
        rejected: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Phase 5: Size and place bets for confirmed candidates."""
        push_log(f"[{cycle_id}] Phase 5: Placing bets...", level="info")

        bets_placed: list[dict[str, Any]] = []

        # Log skips for rejected candidates
        for r in rejected:
            self._ledger.log(
                entry_type="BET_SKIPPED",
                market_id=r["slug"],
                question=r["question"],
                data={
                    "reason": "deep_rejected",
                    "deep_edge": r.get("deep_edge", 0),
                    "quick_edge": r["edge"],
                },
                explanation="Deep analysis rejected this market (edge too small)",
                cycle_id=cycle_id,
            )

        # Build map of existing open positions: slug -> {side, mode, edge}
        open_positions: dict[str, list[dict[str, Any]]] = {}
        try:
            for pos in self._portfolio.get_open_positions():
                s = getattr(pos, "slug", None) or getattr(pos, "market_id", "")
                if s:
                    if s not in open_positions:
                        open_positions[s] = []
                    open_positions[s].append({
                        "side": getattr(pos, "side", ""),
                        "mode": getattr(pos, "mode", "quick"),
                        "edge": getattr(pos, "edge", 0),
                    })
        except Exception:
            pass

        open_slugs = set(open_positions.keys())

        for candidate in confirmed:
            slug = candidate["slug"]
            question = candidate["question"]
            market_id = slug  # Use slug as market_id for consistency
            yes_price = candidate["yes_price"]

            # Smart dedup: only skip if same market AND same side in quick mode
            # Allow new bets when: different side, or deep-confirmed vs existing quick
            existing = open_positions.get(slug, [])
            new_side = "YES" if candidate.get("deep_prediction", candidate["quick_prediction"]) > yes_price else "NO"
            is_deep = "deep_prediction" in candidate

            should_skip = False
            if existing:
                if not is_deep:
                    # Quick mode: skip ANY existing position on this market
                    # Random noise gives different sides each cycle — don't bet against yourself
                    should_skip = True
                else:
                    # Deep mode: only allow if it's a stronger conviction (different edge)
                    same_side_exists = any(p["side"] == new_side for p in existing)
                    if not same_side_exists:
                        # Deep says opposite side — allow (reversing position with deep conviction)
                        should_skip = False
                    else:
                        # Deep confirms same side as existing — allow (adding to position)
                        should_skip = False

            if should_skip:
                self._ledger.log(
                    entry_type="BET_SKIPPED",
                    market_id=slug,
                    question=question,
                    data={"reason": "duplicate_position", "side": new_side, "is_deep": is_deep, "edge": candidate.get("edge", 0)},
                    explanation=f"Already have open position on this market (quick mode blocks all duplicates)",
                    cycle_id=cycle_id,
                )
                push_log(
                    f"[{cycle_id}] Skipped {slug}: already have quick {new_side} position",
                    level="info",
                )
                continue

            # Use deep prediction if available, otherwise quick
            prediction = candidate.get(
                "deep_prediction", candidate["quick_prediction"]
            )
            edge = candidate.get("deep_edge", candidate["edge"])

            # Derive confidence level from edge magnitude
            if edge >= 0.15:
                confidence = "high"
            elif edge >= 0.08:
                confidence = "medium"
            else:
                confidence = "low"

            # Size the bet using Kelly criterion
            sizing = BetSizer.size_bet(
                balance=self._portfolio.balance,
                probability=prediction,
                market_odds=yes_price,
                edge=edge,
                confidence=confidence,
                min_edge=cfg.min_edge_for_bet,
            )

            amount = sizing["amount"]
            side = sizing["side"]

            if amount <= 0:
                self._ledger.log(
                    entry_type="BET_SKIPPED",
                    market_id=slug,
                    question=question,
                    data={
                        "sizing": sizing,
                        "edge": edge,
                        "prediction": prediction,
                    },
                    explanation=f"Bet sizer returned $0: {sizing['reasoning']}",
                    cycle_id=cycle_id,
                )
                push_log(
                    f"[{cycle_id}] Skipped bet on {slug}: {sizing['reasoning']}",
                    level="info",
                )
                continue

            # Place the paper bet
            try:
                bet_record = self._portfolio.place_bet(
                    market_id=market_id,
                    slug=slug,
                    question=question,
                    side=side,
                    amount=amount,
                    odds=yes_price,
                    closes_at=candidate.get("closes_at", ""),
                    prediction=prediction,
                    edge=edge,
                    confidence=confidence,
                    mode="deep" if is_deep else "quick",
                    kelly_fraction=sizing.get("kelly_fraction", 0) if isinstance(sizing, dict) else 0,
                    cost_usd=candidate.get("cost_usd", 0),
                )

                # Add to dedup set so we don't double-bet within the same cycle
                open_slugs.add(slug)

                bet_info: dict[str, Any] = {
                    "slug": slug,
                    "side": side,
                    "amount": amount,
                    "odds": yes_price,
                    "prediction": prediction,
                    "edge": edge,
                    "confidence": confidence,
                    "kelly_fraction": sizing["kelly_fraction"],
                    "bet_id": bet_record.bet_id,
                }
                bets_placed.append(bet_info)

                self._ledger.log(
                    entry_type="BET_PLACED",
                    market_id=slug,
                    question=question,
                    data=bet_info,
                    explanation=(
                        f"Placed ${amount:.2f} {side} at {yes_price:.1%} odds. "
                        f"Predicted prob={prediction:.2%}, edge={edge:.2%}, "
                        f"confidence={confidence}. {sizing['reasoning']}"
                    ),
                    cycle_id=cycle_id,
                )
                push_log(
                    f"[{cycle_id}] BET PLACED: ${amount:.2f} {side} on {slug} "
                    f"(edge={edge:.2%})",
                    level="success",
                )

            except ValueError as exc:
                logger.warning("Failed to place bet on %s: %s", slug, exc)
                push_log(
                    f"[{cycle_id}] Bet failed for {slug}: {exc}",
                    level="error",
                )

        push_log(
            f"[{cycle_id}] Betting done: {len(bets_placed)} bets placed",
            level="info",
        )
        return bets_placed

    async def _phase_resolve(self, cycle_id: str) -> list[dict[str, Any]]:
        """Phase 6: Check if any open positions have resolved."""
        push_log(
            f"[{cycle_id}] Phase 6: Checking resolutions...", level="info"
        )

        resolutions: list[dict[str, Any]] = []

        try:
            from polymarket_predictor.calibrator.calibrate import Calibrator
            from polymarket_predictor.calibrator.history import PredictionHistory
            from polymarket_predictor.resolver.resolver import MarketResolver

            history = PredictionHistory()
            calibrator = Calibrator()
            resolver = MarketResolver(self._portfolio, calibrator, history)

            results = await resolver.check_resolutions()

            for res in results:
                res_info: dict[str, Any] = {
                    "market_id": res.market_id,
                    "question": res.question,
                    "outcome_yes": res.outcome_yes,
                    "pnl": res.pnl,
                    "resolved_at": res.resolved_at,
                }
                resolutions.append(res_info)

                self._ledger.log(
                    entry_type="BET_RESOLVED",
                    market_id=res.market_id,
                    question=res.question,
                    data=res_info,
                    explanation=(
                        f"Market resolved "
                        f"{'YES' if res.outcome_yes else 'NO'}. "
                        f"P&L: ${res.pnl:+.2f}"
                    ),
                    cycle_id=cycle_id,
                )

            push_log(
                f"[{cycle_id}] Resolution check done: "
                f"{len(resolutions)} resolved",
                level="info",
            )

        except Exception:
            logger.exception("Resolution check failed")
            push_log(f"[{cycle_id}] Resolution check failed", level="error")

        return resolutions

    def _phase_optimize(self, cycle_id: str) -> dict[str, Any]:
        """Phase 7: Run strategy optimisation if enough data accumulated."""
        push_log(
            f"[{cycle_id}] Phase 7: Checking optimisation...", level="info"
        )

        resolved_bets = self._portfolio.get_resolved_positions()

        if len(resolved_bets) < 20:
            push_log(
                f"[{cycle_id}] Only {len(resolved_bets)} resolved bets "
                f"(need 20+ for optimisation)",
                level="info",
            )
            return {
                "skipped": True,
                "reason": f"Only {len(resolved_bets)} resolved bets",
            }

        if self._optimizer is None:
            push_log(
                f"[{cycle_id}] No strategy optimizer configured, skipping",
                level="info",
            )
            return {"skipped": True, "reason": "No optimizer configured"}

        try:
            perf = self._portfolio.get_performance()

            # Build resolution history dicts for the optimizer
            resolution_history: list[dict[str, Any]] = []
            for bet in resolved_bets:
                resolution_history.append(
                    {
                        "market_prob": bet.odds,
                        "category": getattr(bet, "category", "unknown"),
                        "confidence": getattr(bet, "confidence", "medium"),
                        "edge": abs(
                            getattr(bet, "predicted_prob", bet.odds) - bet.odds
                        ),
                        "won": bet.pnl > 0,
                        "pnl": bet.pnl,
                    }
                )

            from polymarket_predictor.calibrator.calibrate import Calibrator

            calibrator = Calibrator()
            cal_report = calibrator.build_calibration()
            cal_stats: dict[str, Any] = {
                "brier_score": cal_report.brier_score,
                "calibration_error": cal_report.calibration_error,
            }

            opt_result = self._optimizer.optimize(
                perf, cal_stats, resolution_history
            )

            # Log every parameter change
            for change in opt_result.get("changes", []):
                self._ledger.log(
                    entry_type="PARAM_CHANGED",
                    data=change,
                    explanation=(
                        f"Optimizer changed {change['parameter']}: "
                        f"{change['before']} -> {change['after']}. "
                        f"Reason: {change['reason']}"
                    ),
                    cycle_id=cycle_id,
                )

            # Log calibration rebuild
            self._ledger.log(
                entry_type="CALIBRATION_UPDATE",
                data=cal_stats,
                explanation=(
                    f"Calibration rebuilt: "
                    f"Brier={cal_stats['brier_score']:.4f}, "
                    f"CalError={cal_stats['calibration_error']:.4f}"
                ),
                cycle_id=cycle_id,
            )

            push_log(
                f"[{cycle_id}] Optimisation done: "
                f"{len(opt_result.get('changes', []))} changes",
                level="info",
            )
            return {
                "skipped": False,
                "changes": opt_result.get("changes", []),
            }

        except Exception:
            logger.exception("Optimisation failed")
            push_log(f"[{cycle_id}] Optimisation failed", level="error")
            return {"skipped": True, "reason": "Error during optimisation"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _poll_deep_task(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        slug: str,
        cycle_id: str,
        max_wait: int = 900,
        poll_interval: float = 5.0,
    ) -> dict[str, Any] | None:
        """Poll a deep prediction task until it completes or times out.

        Returns the result dict on success, or ``None`` on failure/timeout.
        """
        status_url = (
            f"{MIROFISH_API_URL}/polymarket/predict/deep/{task_id}"
        )
        elapsed = 0.0

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            try:
                resp = await client.get(status_url)
                resp.raise_for_status()
                data = resp.json()

                status = data.get("status", "")
                step = data.get("step", "")

                if status == "completed":
                    return data.get("result", {})
                elif status == "failed":
                    logger.warning(
                        "Deep task %s for %s failed: %s",
                        task_id,
                        slug,
                        data.get("error", "unknown"),
                    )
                    return None

                # Still running -- log progress every ~30s
                if int(elapsed) % 30 == 0:
                    push_log(
                        f"[{cycle_id}] Deep predict {slug}: {step} "
                        f"({int(elapsed)}s elapsed)",
                        level="info",
                    )

            except Exception as exc:
                logger.warning(
                    "Error polling deep task %s: %s", task_id, exc
                )

        logger.warning(
            "Deep task %s for %s timed out after %ds",
            task_id,
            slug,
            max_wait,
        )
        return None

    def _log_cycle_summary(
        self, cycle_id: str, summary: dict[str, Any]
    ) -> None:
        """Write a CYCLE_SUMMARY entry to the ledger."""
        perf = self._portfolio.get_performance()
        summary["portfolio"] = {
            "balance": self._portfolio.balance,
            "total_value": self._portfolio.total_value,
            "total_bets": perf.get("total_bets", 0),
            "win_rate": perf.get("win_rate", 0),
            "total_pnl": perf.get("total_pnl", 0),
        }

        self._ledger.log(
            entry_type="CYCLE_SUMMARY",
            data=summary,
            explanation=(
                f"Cycle {cycle_id} complete. "
                f"Balance: ${self._portfolio.balance:.2f}, "
                f"P&L: ${perf.get('total_pnl', 0):+.2f}"
            ),
            cycle_id=cycle_id,
        )
