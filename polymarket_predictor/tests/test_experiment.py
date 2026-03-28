"""Tests for experiment runner."""
import json
import tempfile
from pathlib import Path

import pytest
from polymarket_predictor.experiment.runner import (
    ExperimentRunner, ExperimentConfig, ExperimentRound, ExperimentState
)


class TestExperimentConfig:
    def test_config_creation(self):
        cfg = ExperimentConfig(name="test", agents=50, rounds=10, preset="cheapest")
        assert cfg.agents == 50

    def test_config_to_dict(self):
        cfg = ExperimentConfig(name="test", agents=50, rounds=10, preset="cheapest")
        d = cfg.to_dict()
        assert d["name"] == "test"
        assert d["agents"] == 50


class TestExperimentState:
    def test_state_save_load(self):
        tmp = Path(tempfile.mkdtemp())
        runner = ExperimentRunner(data_dir=tmp)

        state = ExperimentState(
            experiment_id="test_exp",
            total_rounds=2,
            completed_rounds=1,
        )
        runner._save_state(state)

        loaded = runner._load_state()
        assert loaded.experiment_id == "test_exp"
        assert loaded.completed_rounds == 1

    def test_empty_state(self):
        tmp = Path(tempfile.mkdtemp())
        runner = ExperimentRunner(data_dir=tmp)
        state = runner._load_state()
        assert state.experiment_id == ""
        assert state.total_rounds == 0

    def test_get_state_returns_dict(self):
        tmp = Path(tempfile.mkdtemp())
        runner = ExperimentRunner(data_dir=tmp)
        state = runner.get_state()
        assert isinstance(state, dict)
        assert "experiment_id" in state
