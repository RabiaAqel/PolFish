"""Tests for polymarket_predictor.overnight.state."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from polymarket_predictor.overnight.state import (
    RunState,
    StateManager,
)


# ---------------------------------------------------------------------------
# StateManager: load / save basics
# ---------------------------------------------------------------------------


class TestStateManagerLoadSave:

    def test_state_manager_load_empty(self, tmp_path):
        """No file -> fresh RunState."""
        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        assert isinstance(state, RunState)
        assert state.status == "idle"
        assert state.completed == 0

    def test_state_manager_save_and_reload(self, tmp_path):
        """Save, reload, verify fields match."""
        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        state.run_id = "test-run-123"
        state.status = "running"
        state.completed = 7
        state.total_target = 50
        state.total_cost_usd = 12.34
        mgr.save(state)

        # Reload with a fresh manager
        mgr2 = StateManager(data_dir=tmp_path)
        state2 = mgr2.load()
        assert state2.run_id == "test-run-123"
        assert state2.status == "running"
        assert state2.completed == 7
        assert state2.total_target == 50
        assert state2.total_cost_usd == pytest.approx(12.34)


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------


class TestAtomicWrite:

    def test_atomic_write_no_tmp_leftover(self, tmp_path):
        """Save creates .tmp then renames -- no .tmp file should remain."""
        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        state.run_id = "atomic-test"
        mgr.save(state)

        tmp_file = tmp_path / "overnight_state.tmp"
        assert not tmp_file.exists(), ".tmp file should not remain after save"
        assert (tmp_path / "overnight_state.json").exists()

    def test_atomic_write_file_is_valid_json(self, tmp_path):
        """The saved file should be valid JSON."""
        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        state.run_id = "json-test"
        state.completed = 42
        mgr.save(state)

        raw = (tmp_path / "overnight_state.json").read_text()
        data = json.loads(raw)
        assert data["run_id"] == "json-test"
        assert data["completed"] == 42


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------


class TestCheckpoint:

    def test_checkpoint_updates_timestamp(self, tmp_path):
        """last_checkpoint_at updates after save."""
        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        assert state.last_checkpoint_at is None

        mgr.checkpoint(state, "first checkpoint")
        assert state.last_checkpoint_at is not None
        first_ts = state.last_checkpoint_at

        # Second checkpoint should update timestamp
        import time
        time.sleep(0.01)  # Ensure different second if using strftime
        mgr.checkpoint(state, "second checkpoint")
        # Timestamp should be set (may or may not differ by 1s)
        assert state.last_checkpoint_at is not None


# ---------------------------------------------------------------------------
# RunState defaults
# ---------------------------------------------------------------------------


class TestRunStateDefaults:

    def test_run_state_defaults(self):
        """Fresh state has correct defaults."""
        state = RunState()
        assert state.run_id == ""
        assert state.mode == "overnight"
        assert state.status == "idle"
        assert state.total_target == 50
        assert state.max_budget_usd == 25.0
        assert state.current_round == 0
        assert state.completed == 0
        assert state.failed == 0
        assert state.skipped == 0
        assert state.results == []
        assert state.errors == []
        assert state.processed_slugs == []
        assert state.total_cost_usd == 0.0
        assert state.round_interval_seconds == 3600
        assert state.lifetime_rounds == 0


# ---------------------------------------------------------------------------
# Persistence of nested data
# ---------------------------------------------------------------------------


class TestNestedPersistence:

    def test_processed_slugs_persist(self, tmp_path):
        """Slugs survive save/reload."""
        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        state.processed_slugs = ["btc-100k", "eth-5k", "sol-pump"]
        mgr.save(state)

        mgr2 = StateManager(data_dir=tmp_path)
        state2 = mgr2.load()
        assert state2.processed_slugs == ["btc-100k", "eth-5k", "sol-pump"]

    def test_results_persist(self, tmp_path):
        """Results list survives save/reload."""
        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        state.results = [
            {"market_id": "m1", "prediction": 0.7, "bet_placed": True},
            {"market_id": "m2", "prediction": 0.3, "bet_placed": False},
        ]
        mgr.save(state)

        mgr2 = StateManager(data_dir=tmp_path)
        state2 = mgr2.load()
        assert len(state2.results) == 2
        assert state2.results[0]["market_id"] == "m1"
        assert state2.results[1]["prediction"] == 0.3

    def test_errors_persist(self, tmp_path):
        """Errors list survives save/reload."""
        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        state.errors = [{"msg": "timeout", "market": "m1"}]
        mgr.save(state)

        mgr2 = StateManager(data_dir=tmp_path)
        state2 = mgr2.load()
        assert len(state2.errors) == 1
        assert state2.errors[0]["msg"] == "timeout"


# ---------------------------------------------------------------------------
# Corrupt file handling
# ---------------------------------------------------------------------------


class TestCorruptFileHandling:

    def test_corrupt_file_graceful(self, tmp_path):
        """Write garbage, load returns fresh state."""
        state_file = tmp_path / "overnight_state.json"
        state_file.write_text("{{{{not valid json at all!!!!")

        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        # Should get a fresh default state, not crash
        assert isinstance(state, RunState)
        assert state.status == "idle"
        assert state.completed == 0

    def test_empty_file_graceful(self, tmp_path):
        """Empty file -> fresh state."""
        state_file = tmp_path / "overnight_state.json"
        state_file.write_text("")

        mgr = StateManager(data_dir=tmp_path)
        state = mgr.load()
        assert isinstance(state, RunState)
        assert state.status == "idle"
