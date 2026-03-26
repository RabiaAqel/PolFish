"""Integration tests for end-to-end flows.

Each test exercises a complete workflow across multiple components to verify
that the system hangs together correctly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polymarket_predictor.paper_trader.portfolio import (
    BetRecord,
    BetSizer,
    PaperPortfolio,
)


# ---------------------------------------------------------------------------
# Flow 1: Place bet -> resolve -> check P&L -> verify portfolio state
# ---------------------------------------------------------------------------


class TestFullBetLifecycle:
    """End-to-end: place bet, resolve market, verify P&L and balance."""

    def test_yes_bet_wins(self, tmp_path: Path):
        portfolio = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)

        # Place bet
        bet = portfolio.place_bet(
            "btc-test", "btc-test", "Will BTC hit 72K?", "YES", 100, 0.65
        )
        assert portfolio.balance == pytest.approx(9900.0)
        assert len(portfolio.get_open_positions()) == 1

        # Resolve as YES (win)
        resolved = portfolio.resolve_bet("btc-test", True)
        assert len(resolved) == 1
        assert resolved[0].pnl > 0  # Won
        assert resolved[0].payout == pytest.approx(100 / 0.65, rel=1e-4)

        # Check final state
        expected_balance = 9900 + 100 / 0.65
        assert portfolio.balance == pytest.approx(expected_balance, rel=1e-4)
        assert len(portfolio.get_open_positions()) == 0
        assert len(portfolio.get_resolved_positions()) == 1

        perf = portfolio.get_performance()
        assert perf["win_rate"] == 100.0
        assert perf["total_pnl"] > 0
        assert perf["total_bets"] == 1
        assert perf["wins"] == 1
        assert perf["losses"] == 0

    def test_no_bet_loses(self, tmp_path: Path):
        portfolio = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)

        # Place NO bet
        bet = portfolio.place_bet(
            "eth-test", "eth-test", "Will ETH hit 5K?", "NO", 200, 0.40
        )
        assert portfolio.balance == pytest.approx(9800.0)

        # Resolve as YES (NO bet loses)
        resolved = portfolio.resolve_bet("eth-test", True)
        assert len(resolved) == 1
        assert resolved[0].pnl < 0
        assert resolved[0].payout == 0.0

        assert portfolio.balance == pytest.approx(9800.0)  # No payout
        perf = portfolio.get_performance()
        assert perf["win_rate"] == 0.0
        assert perf["total_pnl"] == -200.0


# ---------------------------------------------------------------------------
# Flow 2: Multiple bets, mixed outcomes, verify aggregate performance
# ---------------------------------------------------------------------------


class TestMixedOutcomesPerformance:
    """Place 5 bets, resolve 3 wins and 2 losses, verify aggregate metrics."""

    def test_mixed_outcomes(self, tmp_path: Path):
        portfolio = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)

        bets = [
            # (market_id, side, amount, odds, outcome_yes, should_win)
            ("m1", "YES", 100, 0.60, True, True),    # YES wins
            ("m2", "YES", 100, 0.70, True, True),    # YES wins
            ("m3", "NO", 100, 0.55, False, True),    # NO wins
            ("m4", "YES", 100, 0.50, False, False),  # YES loses
            ("m5", "NO", 100, 0.60, True, False),    # NO loses
        ]

        for mid, side, amount, odds, _, _ in bets:
            portfolio.place_bet(mid, mid, f"Market {mid}?", side, amount, odds)

        assert portfolio.balance == pytest.approx(10_000 - 500)

        total_pnl = 0.0
        for mid, side, amount, odds, outcome_yes, should_win in bets:
            resolved = portfolio.resolve_bet(mid, outcome_yes)
            assert len(resolved) == 1
            if should_win:
                assert resolved[0].pnl > 0, f"{mid} should win"
            else:
                assert resolved[0].pnl < 0, f"{mid} should lose"
            total_pnl += resolved[0].pnl

        perf = portfolio.get_performance()
        assert perf["total_bets"] == 5
        assert perf["wins"] == 3
        assert perf["losses"] == 2
        assert perf["win_rate"] == 60.0
        assert perf["total_pnl"] == pytest.approx(total_pnl, rel=1e-2)

        # Balance should be consistent
        expected = 10_000 - 500  # initial - all bets
        for mid, side, amount, odds, outcome_yes, should_win in bets:
            if should_win:
                if side == "YES":
                    expected += amount / odds
                else:
                    expected += amount / (1.0 - odds)
            # losers add 0 payout
        assert portfolio.balance == pytest.approx(expected, rel=1e-2)


# ---------------------------------------------------------------------------
# Flow 3: Calibration loop -- predict, resolve, calibrate, re-predict
# ---------------------------------------------------------------------------


class TestCalibrationImproves:
    """After enough predictions and resolutions, the calibrator should
    adjust future predictions based on historical accuracy."""

    def test_calibrator_adjusts_probability(self, tmp_path: Path):
        """Calibrator.calibrate() should modify raw probability when there
        is enough calibration data showing systematic bias."""
        from polymarket_predictor.calibrator.calibrate import Calibrator

        # Use temp file so we don't load stale calibration data from disk
        calibrator = Calibrator(calibration_file=tmp_path / "calibration.json")

        # Before any calibration data, calibrate should return raw probability
        raw = 0.65
        calibrated = calibrator.calibrate(raw)
        # With no curve, should return the raw value
        assert calibrated == raw, (
            "Without calibration data, calibrate() should return the raw probability"
        )

        # Simulate building a calibration curve by writing one
        # (In practice this comes from build_calibration() after many predictions)
        curve = {
            "bins": [
                {"start": 0.6, "end": 0.7, "predicted": 0.65, "actual": 0.55, "count": 20},
            ],
            "brier_score": 0.15,
            "total_predictions": 50,
        }
        cal_file = tmp_path / "calibration.json"
        cal_file.write_text(json.dumps(curve))

        # Reload the calibrator with the curve file
        calibrator2 = Calibrator(calibration_file=cal_file)
        calibrated2 = calibrator2.calibrate(0.65)

        # The calibrator should adjust: raw(0.65) + (actual(0.55) - predicted(0.65)) = 0.55
        assert calibrated2 == pytest.approx(0.55, rel=1e-2), (
            f"Calibrator should adjust 0.65 to ~0.55 based on historical bias, "
            f"got {calibrated2}"
        )


# ---------------------------------------------------------------------------
# Flow 4: Optimizer changes strategy based on results
# ---------------------------------------------------------------------------


class TestOptimizerAdjustsEdgeThreshold:
    """After a batch of losing bets, the optimizer should increase
    the min_edge_threshold to be more selective."""

    def test_optimizer_raises_threshold_on_low_win_rate(self, tmp_path: Path):
        from polymarket_predictor.optimizer.strategy import StrategyOptimizer

        optimizer = StrategyOptimizer(data_dir=tmp_path)
        initial_config = optimizer.get_config()
        initial_threshold = initial_config["min_edge_threshold"]

        # Simulate poor performance (win_rate below 50%)
        poor_perf = {
            "win_rate": 0.35,  # 35% -- bad
            "roi": -0.10,
            "max_drawdown": 0.15,
            "total_pnl": -500.0,
        }

        result = optimizer.optimize(
            portfolio_performance=poor_perf,
            calibration_stats={"brier_score": 0.20, "calibration_error": 0.10},
            resolution_history=[],
        )

        new_config = optimizer.get_config()

        # Edge threshold should have increased
        assert new_config["min_edge_threshold"] > initial_threshold, (
            f"Optimizer should raise edge threshold from {initial_threshold} "
            f"after poor performance, but got {new_config['min_edge_threshold']}"
        )

        # There should be at least one change
        assert len(result["changes"]) > 0, "Optimizer should make changes for poor performance"


# ---------------------------------------------------------------------------
# Flow 5: Decision ledger records all actions
# ---------------------------------------------------------------------------


class TestLedgerCapturesFullCycle:
    """A complete autopilot cycle should produce ledger entries for:
    scan, predict, bet/skip, resolve, optimize."""

    def test_ledger_records_bet_placed_and_skipped(self, tmp_path: Path):
        from polymarket_predictor.ledger.decision_ledger import DecisionLedger

        ledger = DecisionLedger(data_dir=tmp_path)

        cycle_id = "test-cycle-123"

        # Simulate a complete cycle's worth of ledger entries
        ledger.log(
            entry_type="BET_SKIPPED",
            market_id="low-edge-market",
            question="Low edge market?",
            data={"edge": 0.02, "reason": "edge_too_low"},
            explanation="Edge 2% below threshold 3%",
            cycle_id=cycle_id,
        )

        ledger.log(
            entry_type="BET_PLACED",
            market_id="good-market",
            question="Good market?",
            data={"side": "YES", "amount": 50.0, "odds": 0.65},
            explanation="Edge 12% exceeds threshold; Kelly suggests 3.2% allocation.",
            cycle_id=cycle_id,
        )

        ledger.log(
            entry_type="BET_RESOLVED",
            market_id="resolved-market",
            question="Resolved market?",
            data={"outcome_yes": True, "pnl": 25.0},
            explanation="Market resolved YES. P&L: +$25.00",
            cycle_id=cycle_id,
        )

        ledger.log(
            entry_type="CYCLE_SUMMARY",
            data={"bets_placed": 1, "bets_skipped": 1, "resolved": 1},
            explanation="Cycle complete.",
            cycle_id=cycle_id,
        )

        # Verify all entries are retrievable
        cycle_entries = ledger.get_cycle_entries(cycle_id)
        assert len(cycle_entries) == 4

        types = {e.entry_type for e in cycle_entries}
        assert "BET_SKIPPED" in types
        assert "BET_PLACED" in types
        assert "BET_RESOLVED" in types
        assert "CYCLE_SUMMARY" in types

        # Verify stats
        stats = ledger.get_stats()
        assert stats["total_entries"] == 4
        assert stats["total_cycles"] == 1

    def test_ledger_search(self, tmp_path: Path):
        from polymarket_predictor.ledger.decision_ledger import DecisionLedger

        ledger = DecisionLedger(data_dir=tmp_path)

        ledger.log(
            entry_type="BET_PLACED",
            market_id="btc-market",
            question="Will Bitcoin reach 100K?",
            data={},
            explanation="Bitcoin prediction with high edge",
            cycle_id="cycle-1",
        )

        results = ledger.search("bitcoin")
        assert len(results) >= 1
        assert results[0].market_id == "btc-market"


# ---------------------------------------------------------------------------
# Flow 6: Portfolio persistence across restarts
# ---------------------------------------------------------------------------


class TestPortfolioSurvivesRestart:
    """Place bets, save, create new portfolio from same file, verify state."""

    def test_portfolio_persists_open_bets(self, tmp_path: Path):
        # Create portfolio and place bets
        p1 = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)
        p1.place_bet("m1", "m1", "Q1?", "YES", 100, 0.60)
        p1.place_bet("m2", "m2", "Q2?", "NO", 200, 0.40)

        # Create a new portfolio from the same directory (simulates restart)
        p2 = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)

        # All open positions should be restored
        assert len(p2.get_open_positions()) == 2
        assert p2.balance == pytest.approx(10_000 - 300)

    def test_portfolio_persists_resolved_bets(self, tmp_path: Path):
        # Create portfolio, place and resolve a bet
        p1 = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)
        p1.place_bet("m1", "m1", "Q1?", "YES", 100, 0.60)
        p1.resolve_bet("m1", True)

        expected_balance = p1.balance

        # Reload
        p2 = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)

        assert len(p2.get_resolved_positions()) == 1
        assert len(p2.get_open_positions()) == 0
        assert p2.balance == pytest.approx(expected_balance, rel=1e-4)

        perf = p2.get_performance()
        assert perf["total_bets"] == 1
        assert perf["wins"] == 1

    def test_portfolio_mixed_state_persistence(self, tmp_path: Path):
        """Portfolio with both open and resolved bets persists correctly."""
        p1 = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)
        p1.place_bet("m1", "m1", "Q1?", "YES", 100, 0.60)
        p1.place_bet("m2", "m2", "Q2?", "NO", 200, 0.45)
        p1.resolve_bet("m1", True)  # Win

        balance_before = p1.balance

        p2 = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)

        assert len(p2.get_open_positions()) == 1  # m2 still open
        assert len(p2.get_resolved_positions()) == 1  # m1 resolved
        assert p2.balance == pytest.approx(balance_before, rel=1e-4)


# ---------------------------------------------------------------------------
# Flow 7: Backtest isolation doesn't affect live portfolio
# ---------------------------------------------------------------------------


class TestBacktestIsolation:
    """Running a backtest should not modify the live portfolio balance."""

    def test_backtest_uses_separate_directory(self, tmp_path: Path):
        """Backtest engine creates its data in a 'backtest/' subdirectory."""
        from polymarket_predictor.backtest.engine import BacktestEngine

        engine = BacktestEngine(data_dir=tmp_path)

        # Backtest data dir should be a subdirectory
        assert engine._data_dir == tmp_path / "backtest"
        assert engine._data_dir.exists()

    def test_backtest_does_not_touch_live_portfolio(self, tmp_path: Path):
        """Placing bets in backtest must not affect a live portfolio in the
        parent directory."""
        from polymarket_predictor.backtest.engine import BacktestEngine

        # Create a "live" portfolio in the parent dir
        live_portfolio = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)
        live_portfolio.place_bet("live-m1", "live-m1", "Live?", "YES", 500, 0.50)
        live_balance = live_portfolio.balance

        # Create backtest engine (uses tmp_path/backtest/)
        engine = BacktestEngine(data_dir=tmp_path)

        # Place a bet in the backtest portfolio
        engine._portfolio.place_bet("bt-m1", "bt-m1", "Backtest?", "YES", 1000, 0.50)

        # Reload live portfolio -- should be unchanged
        live_portfolio_reloaded = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)
        assert live_portfolio_reloaded.balance == pytest.approx(live_balance), (
            "Backtest bet should not affect live portfolio balance"
        )
        assert len(live_portfolio_reloaded.get_open_positions()) == 1

    def test_backtest_reset_clears_only_backtest_data(self, tmp_path: Path):
        """Backtest reset must only clear backtest/ directory, not live data."""
        from polymarket_predictor.backtest.engine import BacktestEngine

        # Create live portfolio data
        live_portfolio = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)
        live_portfolio.place_bet("live-m1", "live-m1", "Live?", "YES", 200, 0.50)

        live_file = tmp_path / "portfolio.jsonl"
        assert live_file.exists()

        # Create and reset backtest
        engine = BacktestEngine(data_dir=tmp_path)
        engine._portfolio.place_bet("bt-m1", "bt-m1", "Backtest?", "YES", 100, 0.50)
        engine.reset()

        # Live data should still exist
        assert live_file.exists(), "Backtest reset must not delete live portfolio data"
        live_portfolio_after = PaperPortfolio(data_dir=tmp_path, initial_balance=10_000)
        assert len(live_portfolio_after.get_open_positions()) == 1
