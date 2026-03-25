"""Tests for polymarket_predictor.optimizer.strategy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polymarket_predictor.optimizer.strategy import (
    DEFAULT_STRATEGY_CONFIG,
    PerformanceAnalyzer,
    StrategyOptimizer,
)


# ---------------------------------------------------------------------------
# StrategyOptimizer -- initialization
# ---------------------------------------------------------------------------


class TestStrategyOptimizerInit:
    def test_loads_defaults_if_no_file(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        cfg = opt.get_config()
        assert cfg["min_edge_threshold"] == DEFAULT_STRATEGY_CONFIG["min_edge_threshold"]
        assert cfg["kelly_factor"] == DEFAULT_STRATEGY_CONFIG["kelly_factor"]

    def test_loads_from_existing_file(self, tmp_path):
        (tmp_path / "strategy.json").write_text(json.dumps({"min_edge_threshold": 0.07, "version": 5}))
        opt = StrategyOptimizer(data_dir=tmp_path)
        cfg = opt.get_config()
        assert cfg["min_edge_threshold"] == 0.07
        assert cfg["version"] == 5
        # defaults are merged for missing keys
        assert "kelly_factor" in cfg


# ---------------------------------------------------------------------------
# optimize -- edge threshold
# ---------------------------------------------------------------------------


class TestTuneEdgeThreshold:
    def test_low_win_rate_increases_threshold(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old = opt.get_config()["min_edge_threshold"]
        result = opt.optimize(
            portfolio_performance={"win_rate": 0.40},
            calibration_stats={},
            resolution_history=[],
        )
        new = opt.get_config()["min_edge_threshold"]
        assert new > old

    def test_high_win_rate_decreases_threshold(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old = opt.get_config()["min_edge_threshold"]
        result = opt.optimize(
            portfolio_performance={"win_rate": 0.70},
            calibration_stats={},
            resolution_history=[],
        )
        new = opt.get_config()["min_edge_threshold"]
        assert new < old

    def test_moderate_win_rate_no_change(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old = opt.get_config()["min_edge_threshold"]
        opt.optimize(
            portfolio_performance={"win_rate": 0.55},
            calibration_stats={},
            resolution_history=[],
        )
        new = opt.get_config()["min_edge_threshold"]
        assert new == old


# ---------------------------------------------------------------------------
# optimize -- kelly factor
# ---------------------------------------------------------------------------


class TestTuneKellyFactor:
    def test_high_drawdown_reduces_kelly(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old = opt.get_config()["kelly_factor"]
        opt.optimize(
            portfolio_performance={"win_rate": 0.55, "max_drawdown": 0.25, "roi": 0.05},
            calibration_stats={},
            resolution_history=[],
        )
        new = opt.get_config()["kelly_factor"]
        assert new < old

    def test_good_roi_low_drawdown_increases_kelly(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old = opt.get_config()["kelly_factor"]
        opt.optimize(
            portfolio_performance={"win_rate": 0.55, "max_drawdown": 0.05, "roi": 0.15},
            calibration_stats={},
            resolution_history=[],
        )
        new = opt.get_config()["kelly_factor"]
        assert new > old


# ---------------------------------------------------------------------------
# optimize -- category weights
# ---------------------------------------------------------------------------


class TestTuneCategoryWeights:
    def test_high_win_rate_category_increases_weight(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old = opt.get_config()["category_weights"].get("crypto", 0.7)
        opt.optimize(
            portfolio_performance={
                "win_rate": 0.55,
                "by_category": {"crypto": {"win_rate": 0.70}},
            },
            calibration_stats={},
            resolution_history=[],
        )
        new = opt.get_config()["category_weights"]["crypto"]
        assert new > old

    def test_low_win_rate_category_decreases_weight(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old = opt.get_config()["category_weights"].get("sports", 0.5)
        opt.optimize(
            portfolio_performance={
                "win_rate": 0.55,
                "by_category": {"sports": {"win_rate": 0.30}},
            },
            calibration_stats={},
            resolution_history=[],
        )
        new = opt.get_config()["category_weights"]["sports"]
        assert new < old


# ---------------------------------------------------------------------------
# optimize -- odds range
# ---------------------------------------------------------------------------


class TestTuneOddsRange:
    def test_extreme_odds_losing_tightens_range(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old_range = list(opt.get_config()["odds_range"])
        # Create 10 extreme-odds bets that all lost
        history = [
            {"market_prob": 0.10, "won": False, "category": "crypto", "confidence": "high", "edge": 0.05}
            for _ in range(10)
        ]
        opt.optimize(
            portfolio_performance={"win_rate": 0.55},
            calibration_stats={},
            resolution_history=history,
        )
        new_range = opt.get_config()["odds_range"]
        assert new_range[0] >= old_range[0]  # lower bound increased or same
        assert new_range[1] <= old_range[1]  # upper bound decreased or same

    def test_no_history_no_change(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old_range = list(opt.get_config()["odds_range"])
        opt.optimize(
            portfolio_performance={"win_rate": 0.55},
            calibration_stats={},
            resolution_history=[],
        )
        new_range = opt.get_config()["odds_range"]
        assert new_range == old_range


# ---------------------------------------------------------------------------
# optimize -- confidence multipliers
# ---------------------------------------------------------------------------


class TestTuneConfidenceMultipliers:
    def test_low_confidence_negative_pnl_reduces(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old = opt.get_config()["confidence_multipliers"]["low"]
        opt.optimize(
            portfolio_performance={
                "win_rate": 0.55,
                "by_confidence": {"low": {"pnl": -50.0}},
            },
            calibration_stats={},
            resolution_history=[],
        )
        new = opt.get_config()["confidence_multipliers"]["low"]
        assert new < old

    def test_medium_confidence_negative_pnl_reduces(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        old = opt.get_config()["confidence_multipliers"]["medium"]
        opt.optimize(
            portfolio_performance={
                "win_rate": 0.55,
                "by_confidence": {"medium": {"pnl": -30.0}},
            },
            calibration_stats={},
            resolution_history=[],
        )
        new = opt.get_config()["confidence_multipliers"]["medium"]
        assert new < old


# ---------------------------------------------------------------------------
# save and load
# ---------------------------------------------------------------------------


class TestSaveAndLoad:
    def test_persist_and_reload(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        opt.optimize(
            portfolio_performance={"win_rate": 0.40},
            calibration_stats={},
            resolution_history=[],
        )
        cfg_before = opt.get_config()

        # Create a new instance that loads from the same file
        opt2 = StrategyOptimizer(data_dir=tmp_path)
        cfg_after = opt2.get_config()

        assert cfg_before["min_edge_threshold"] == cfg_after["min_edge_threshold"]
        assert cfg_before["version"] == cfg_after["version"]


# ---------------------------------------------------------------------------
# optimization log
# ---------------------------------------------------------------------------


class TestOptimizationLog:
    def test_log_records_changes(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        opt.optimize(
            portfolio_performance={"win_rate": 0.40},
            calibration_stats={},
            resolution_history=[],
        )
        log = opt.get_optimization_log()
        assert len(log) == 1
        assert "changes" in log[0]
        assert "portfolio_snapshot" in log[0]

    def test_multiple_optimizations_append(self, tmp_path):
        opt = StrategyOptimizer(data_dir=tmp_path)
        for wr in [0.40, 0.35, 0.30]:
            opt.optimize(
                portfolio_performance={"win_rate": wr},
                calibration_stats={},
                resolution_history=[],
            )
        log = opt.get_optimization_log()
        assert len(log) == 3


# ---------------------------------------------------------------------------
# PerformanceAnalyzer
# ---------------------------------------------------------------------------


class TestPerformanceAnalyzer:
    def test_empty_portfolio(self):
        pa = PerformanceAnalyzer(
            portfolio={"balance": 1000, "initial_balance": 1000, "peak_balance": 1000},
            history=[],
        )
        report = pa.analyze()
        assert report["overall"]["total_bets"] == 0
        assert report["overall"]["win_rate"] == 0.0
        assert report["overall"]["total_pnl"] == 0.0
        assert report["by_category"] == {}
        assert report["by_confidence"] == {}

    def test_wins_and_losses(self):
        history = [
            {"won": True, "pnl": 10.0, "category": "crypto", "confidence": "high", "edge": 0.05, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-01T00:00:00"},
            {"won": True, "pnl": 15.0, "category": "crypto", "confidence": "high", "edge": 0.08, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-02T00:00:00"},
            {"won": False, "pnl": -5.0, "category": "politics", "confidence": "low", "edge": 0.03, "market_prob": 0.5, "predicted_prob": 0.55, "timestamp": "2025-01-03T00:00:00"},
        ]
        pa = PerformanceAnalyzer(
            portfolio={"balance": 1020, "initial_balance": 1000, "peak_balance": 1025},
            history=history,
        )
        report = pa.analyze()
        overall = report["overall"]
        assert overall["total_bets"] == 3
        assert overall["wins"] == 2
        assert overall["losses"] == 1
        assert abs(overall["win_rate"] - 2 / 3) < 0.01
        assert overall["total_pnl"] == 20.0

    def test_by_category_breakdown(self):
        history = [
            {"won": True, "pnl": 10.0, "category": "crypto", "confidence": "high", "edge": 0.05, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-01T00:00:00"},
            {"won": False, "pnl": -5.0, "category": "politics", "confidence": "low", "edge": 0.03, "market_prob": 0.5, "predicted_prob": 0.55, "timestamp": "2025-01-02T00:00:00"},
            {"won": True, "pnl": 8.0, "category": "crypto", "confidence": "medium", "edge": 0.06, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-03T00:00:00"},
        ]
        pa = PerformanceAnalyzer(
            portfolio={"balance": 1013, "initial_balance": 1000, "peak_balance": 1013},
            history=history,
        )
        report = pa.analyze()
        by_cat = report["by_category"]
        assert "crypto" in by_cat
        assert "politics" in by_cat
        assert by_cat["crypto"]["num_bets"] == 2
        assert by_cat["crypto"]["win_rate"] == 1.0
        assert by_cat["politics"]["win_rate"] == 0.0

    def test_by_confidence_breakdown(self):
        history = [
            {"won": True, "pnl": 10.0, "category": "crypto", "confidence": "high", "edge": 0.05, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-01T00:00:00"},
            {"won": False, "pnl": -5.0, "category": "crypto", "confidence": "low", "edge": 0.03, "market_prob": 0.5, "predicted_prob": 0.55, "timestamp": "2025-01-02T00:00:00"},
        ]
        pa = PerformanceAnalyzer(
            portfolio={"balance": 1005, "initial_balance": 1000, "peak_balance": 1010},
            history=history,
        )
        report = pa.analyze()
        by_conf = report["by_confidence"]
        assert "high" in by_conf
        assert "low" in by_conf
        assert by_conf["high"]["win_rate"] == 1.0
        assert by_conf["low"]["win_rate"] == 0.0

    def test_time_series_sorted_by_date(self):
        history = [
            {"won": True, "pnl": 10.0, "category": "c", "confidence": "h", "edge": 0.05, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-03T12:00:00"},
            {"won": False, "pnl": -5.0, "category": "c", "confidence": "h", "edge": 0.05, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-01T08:00:00"},
            {"won": True, "pnl": 3.0, "category": "c", "confidence": "h", "edge": 0.05, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-02T15:00:00"},
        ]
        pa = PerformanceAnalyzer(
            portfolio={"balance": 1008, "initial_balance": 1000, "peak_balance": 1008},
            history=history,
        )
        report = pa.analyze()
        daily = report["time_series"]["daily_pnl"]
        dates = [d["date"] for d in daily]
        assert dates == sorted(dates)

    def test_edge_buckets(self):
        history = [
            {"won": True, "pnl": 5.0, "category": "c", "confidence": "h", "edge": 0.04, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-01T00:00:00"},
            {"won": False, "pnl": -3.0, "category": "c", "confidence": "h", "edge": 0.07, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-02T00:00:00"},
            {"won": True, "pnl": 20.0, "category": "c", "confidence": "h", "edge": 0.12, "market_prob": 0.5, "predicted_prob": 0.6, "timestamp": "2025-01-03T00:00:00"},
        ]
        pa = PerformanceAnalyzer(
            portfolio={"balance": 1022, "initial_balance": 1000, "peak_balance": 1022},
            history=history,
        )
        report = pa.analyze()
        buckets = report["by_edge_bucket"]
        assert buckets["3-5%"]["num_bets"] == 1
        assert buckets["5-10%"]["num_bets"] == 1
        assert buckets["10%+"]["num_bets"] == 1
        assert buckets["10%+"]["win_rate"] == 1.0
