"""Crash-safe state management with atomic writes."""

import json
import os
import time
import uuid
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Result of a single prediction attempt."""
    market_id: str
    slug: str
    question: str
    market_odds: float
    prediction: Optional[float] = None
    edge: Optional[float] = None
    signal: Optional[str] = None
    confidence: Optional[str] = None
    side: Optional[str] = None
    bet_amount: float = 0.0
    bet_placed: bool = False
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    status: str = "pending"  # pending | running | completed | failed | skipped
    completed_at: Optional[str] = None


@dataclass
class RunState:
    """Full state of an overnight/rolling run. Checkpointed after every action."""
    run_id: str = ""
    mode: str = "overnight"  # overnight | rolling
    status: str = "idle"     # idle | running | paused | completed | failed

    # Targets
    total_target: int = 50
    max_budget_usd: float = 25.0

    # Progress
    current_round: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0

    # Current work
    current_market: Optional[str] = None
    current_phase: str = ""  # scanning | predicting | betting | resolving | optimizing | sleeping

    # Accumulated results
    results: list = field(default_factory=list)  # List of PredictionResult dicts
    errors: list = field(default_factory=list)   # List of error dicts

    # Cost tracking
    total_cost_usd: float = 0.0

    # Timing
    started_at: Optional[str] = None
    last_checkpoint_at: Optional[str] = None
    paused_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Rolling loop specific
    round_interval_seconds: int = 3600  # 1 hour between rounds
    lifetime_rounds: int = 0
    lifetime_bets: int = 0
    lifetime_pnl: float = 0.0
    lifetime_cost: float = 0.0
    strategy_version: int = 1

    # Markets already processed (don't repeat)
    processed_slugs: list = field(default_factory=list)


class StateManager:
    """Atomic state persistence — writes to temp file then renames (atomic on POSIX)."""

    def __init__(self, data_dir: Path = None):
        from polymarket_predictor.config import DATA_DIR
        self._dir = data_dir or DATA_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "overnight_state.json"
        self._state: Optional[RunState] = None

    def load(self) -> RunState:
        """Load state from disk, or return fresh state."""
        if self._state_file.exists():
            try:
                with open(self._state_file) as f:
                    data = json.load(f)
                self._state = RunState(**{
                    k: v for k, v in data.items()
                    if k in RunState.__dataclass_fields__
                })
                logger.info("Loaded state: run=%s, completed=%d/%d, status=%s",
                           self._state.run_id, self._state.completed,
                           self._state.total_target, self._state.status)
                return self._state
            except Exception as e:
                logger.error("Failed to load state: %s", e)

        self._state = RunState()
        return self._state

    def save(self, state: RunState = None):
        """Atomic save — write to temp, then rename."""
        state = state or self._state
        if state is None:
            return

        state.last_checkpoint_at = time.strftime("%Y-%m-%dT%H:%M:%S")

        # Write to temp file first
        tmp_file = self._state_file.with_suffix(".tmp")
        with open(tmp_file, "w") as f:
            json.dump(asdict(state), f, indent=2, default=str)

        # Atomic rename (POSIX guarantees this is atomic)
        os.replace(tmp_file, self._state_file)
        self._state = state

    def checkpoint(self, state: RunState, msg: str = ""):
        """Save + log what happened."""
        self.save(state)
        if msg:
            logger.info("Checkpoint [%d/%d]: %s", state.completed, state.total_target, msg)

    @property
    def state(self) -> Optional[RunState]:
        return self._state
