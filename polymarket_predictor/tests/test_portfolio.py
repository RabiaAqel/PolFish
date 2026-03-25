"""Tests for polymarket_predictor.paper_trader.portfolio — PaperPortfolio."""

import json
import pytest
from pathlib import Path

from polymarket_predictor.paper_trader.portfolio import BetRecord, PaperPortfolio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_portfolio(tmp_path, balance=10_000.0):
    """Create a PaperPortfolio backed by a temp directory."""
    return PaperPortfolio(initial_balance=balance, data_dir=tmp_path)


def _place_default_bet(portfolio, **overrides):
    """Place a bet with sensible defaults, overrideable via kwargs."""
    defaults = dict(
        market_id="m1",
        slug="test-market",
        question="Will it rain?",
        side="YES",
        amount=100.0,
        odds=0.65,
    )
    defaults.update(overrides)
    return portfolio.place_bet(**defaults)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestPaperPortfolioInit:

    def test_default_balance(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        assert pf.balance == 10_000.0

    def test_custom_balance(self, tmp_path):
        pf = _make_portfolio(tmp_path, balance=5_000.0)
        assert pf.balance == 5_000.0

    def test_empty_positions(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        assert pf.get_open_positions() == []
        assert pf.get_resolved_positions() == []

    def test_total_value_equals_balance_initially(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        assert pf.total_value == 10_000.0


# ---------------------------------------------------------------------------
# place_bet
# ---------------------------------------------------------------------------

class TestPlaceBet:

    def test_valid_bet_reduces_balance(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        bet = _place_default_bet(pf, amount=250.0)
        assert pf.balance == pytest.approx(10_000.0 - 250.0)
        assert isinstance(bet, BetRecord)

    def test_returns_bet_record(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        bet = _place_default_bet(pf, market_id="abc", side="NO", amount=50.0, odds=0.4)
        assert bet.market_id == "abc"
        assert bet.side == "NO"
        assert bet.amount == 50.0
        assert bet.odds == 0.4
        assert bet.resolved is False

    def test_insufficient_balance(self, tmp_path):
        pf = _make_portfolio(tmp_path, balance=100.0)
        with pytest.raises(ValueError, match="Insufficient balance"):
            _place_default_bet(pf, amount=200.0)

    def test_zero_amount(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        with pytest.raises(ValueError, match="positive"):
            _place_default_bet(pf, amount=0.0)

    def test_negative_amount(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        with pytest.raises(ValueError, match="positive"):
            _place_default_bet(pf, amount=-50.0)

    def test_invalid_side(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        with pytest.raises(ValueError, match="YES.*NO"):
            _place_default_bet(pf, side="MAYBE")

    def test_odds_out_of_range_zero(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        with pytest.raises(ValueError, match="odds"):
            _place_default_bet(pf, odds=0.0)

    def test_odds_out_of_range_one(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        with pytest.raises(ValueError, match="odds"):
            _place_default_bet(pf, odds=1.0)

    def test_metadata_fields_stored(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        bet = pf.place_bet(
            market_id="m1",
            slug="slug",
            question="Q?",
            side="YES",
            amount=100.0,
            odds=0.5,
            prediction=0.65,
            edge=0.15,
            confidence="high",
            mode="deep",
            kelly_fraction=0.04,
            cost_usd=0.003,
        )
        assert bet.prediction == 0.65
        assert bet.edge == 0.15
        assert bet.confidence == "high"
        assert bet.mode == "deep"
        assert bet.kelly_fraction == 0.04
        assert bet.cost_usd == 0.003

    def test_side_case_insensitive(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        bet = _place_default_bet(pf, side="yes")
        assert bet.side == "YES"

    def test_bet_id_auto_generated(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        bet = _place_default_bet(pf)
        assert bet.bet_id  # non-empty
        assert bet.market_id in bet.bet_id


# ---------------------------------------------------------------------------
# resolve_bet — YES wins
# ---------------------------------------------------------------------------

class TestResolveBetYesWins:

    def test_payout_yes_wins(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="YES", amount=100.0, odds=0.65)
        resolved = pf.resolve_bet("m1", outcome_yes=True)
        assert len(resolved) == 1
        bet = resolved[0]
        expected_payout = 100.0 / 0.65
        assert bet.payout == pytest.approx(expected_payout)
        assert bet.pnl == pytest.approx(expected_payout - 100.0)
        assert bet.resolved is True
        assert bet.outcome_yes is True

    def test_balance_updated_yes_wins(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="YES", amount=100.0, odds=0.5)
        # balance after bet: 9900
        pf.resolve_bet("m1", outcome_yes=True)
        # payout = 100/0.5 = 200, so balance = 9900 + 200 = 10100
        assert pf.balance == pytest.approx(10_100.0)


# ---------------------------------------------------------------------------
# resolve_bet — YES loses
# ---------------------------------------------------------------------------

class TestResolveBetYesLoses:

    def test_payout_yes_loses(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="YES", amount=100.0, odds=0.65)
        resolved = pf.resolve_bet("m1", outcome_yes=False)
        bet = resolved[0]
        assert bet.payout == 0.0
        assert bet.pnl == pytest.approx(-100.0)

    def test_balance_updated_yes_loses(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="YES", amount=100.0, odds=0.65)
        pf.resolve_bet("m1", outcome_yes=False)
        assert pf.balance == pytest.approx(10_000.0 - 100.0)


# ---------------------------------------------------------------------------
# resolve_bet — NO wins
# ---------------------------------------------------------------------------

class TestResolveBetNoWins:

    def test_payout_no_wins(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="NO", amount=100.0, odds=0.65)
        resolved = pf.resolve_bet("m1", outcome_yes=False)
        bet = resolved[0]
        expected_payout = 100.0 / (1.0 - 0.65)
        assert bet.payout == pytest.approx(expected_payout)
        assert bet.pnl == pytest.approx(expected_payout - 100.0)


# ---------------------------------------------------------------------------
# resolve_bet — NO loses
# ---------------------------------------------------------------------------

class TestResolveBetNoLoses:

    def test_payout_no_loses(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="NO", amount=100.0, odds=0.65)
        resolved = pf.resolve_bet("m1", outcome_yes=True)
        bet = resolved[0]
        assert bet.payout == 0.0
        assert bet.pnl == pytest.approx(-100.0)


# ---------------------------------------------------------------------------
# resolve_bet — extreme odds
# ---------------------------------------------------------------------------

class TestResolveBetExtremeOdds:

    def test_very_low_odds_yes_wins(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="YES", amount=10.0, odds=0.01)
        resolved = pf.resolve_bet("m1", outcome_yes=True)
        assert resolved[0].payout == pytest.approx(10.0 / 0.01)  # 1000

    def test_very_high_odds_yes_wins(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="YES", amount=100.0, odds=0.99)
        resolved = pf.resolve_bet("m1", outcome_yes=True)
        assert resolved[0].payout == pytest.approx(100.0 / 0.99)


# ---------------------------------------------------------------------------
# resolve_bet — edge cases
# ---------------------------------------------------------------------------

class TestResolveBetEdgeCases:

    def test_unknown_market(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1")
        resolved = pf.resolve_bet("nonexistent", outcome_yes=True)
        assert resolved == []

    def test_already_resolved_not_doubled(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", amount=100.0, odds=0.5)
        pf.resolve_bet("m1", outcome_yes=True)
        balance_after = pf.balance
        # Resolve again — should be a no-op
        resolved = pf.resolve_bet("m1", outcome_yes=True)
        assert resolved == []
        assert pf.balance == pytest.approx(balance_after)

    def test_multiple_bets_same_market(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", amount=100.0, odds=0.5)
        _place_default_bet(pf, market_id="m1", amount=200.0, odds=0.6)
        resolved = pf.resolve_bet("m1", outcome_yes=True)
        assert len(resolved) == 2


# ---------------------------------------------------------------------------
# get_open_positions / get_resolved_positions
# ---------------------------------------------------------------------------

class TestPositionFiltering:

    def test_get_open_positions(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1")
        _place_default_bet(pf, market_id="m2")
        pf.resolve_bet("m1", outcome_yes=True)
        open_positions = pf.get_open_positions()
        assert len(open_positions) == 1
        assert open_positions[0].market_id == "m2"

    def test_get_resolved_positions(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1")
        _place_default_bet(pf, market_id="m2")
        pf.resolve_bet("m1", outcome_yes=True)
        resolved = pf.get_resolved_positions()
        assert len(resolved) == 1
        assert resolved[0].market_id == "m1"


# ---------------------------------------------------------------------------
# get_performance
# ---------------------------------------------------------------------------

class TestGetPerformance:

    def test_empty_portfolio(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        perf = pf.get_performance()
        assert perf["total_bets"] == 0
        assert perf["wins"] == 0
        assert perf["losses"] == 0
        assert perf["win_rate"] == 0.0
        assert perf["total_pnl"] == 0.0
        assert perf["roi"] == 0.0

    def test_win_rate_calculation(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        # 2 wins, 1 loss
        _place_default_bet(pf, market_id="m1", amount=100.0, odds=0.5)
        _place_default_bet(pf, market_id="m2", amount=100.0, odds=0.5)
        _place_default_bet(pf, market_id="m3", amount=100.0, odds=0.5)
        pf.resolve_bet("m1", outcome_yes=True)   # win
        pf.resolve_bet("m2", outcome_yes=True)   # win
        pf.resolve_bet("m3", outcome_yes=False)  # loss
        perf = pf.get_performance()
        assert perf["total_bets"] == 3
        assert perf["wins"] == 2
        assert perf["losses"] == 1
        assert perf["win_rate"] == pytest.approx(200 / 3)

    def test_total_pnl(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="YES", amount=100.0, odds=0.5)
        pf.resolve_bet("m1", outcome_yes=True)
        perf = pf.get_performance()
        # Payout = 100/0.5 = 200 → P&L = 100
        assert perf["total_pnl"] == pytest.approx(100.0)

    def test_roi_calculation(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="YES", amount=100.0, odds=0.5)
        pf.resolve_bet("m1", outcome_yes=True)
        perf = pf.get_performance()
        # ROI = (100 / 100) * 100 = 100%
        assert perf["roi"] == pytest.approx(100.0)

    def test_all_wins(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        for i in range(5):
            _place_default_bet(pf, market_id=f"m{i}", side="YES", amount=50.0, odds=0.5)
            pf.resolve_bet(f"m{i}", outcome_yes=True)
        perf = pf.get_performance()
        assert perf["wins"] == 5
        assert perf["losses"] == 0
        assert perf["win_rate"] == 100.0

    def test_all_losses(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        for i in range(3):
            _place_default_bet(pf, market_id=f"m{i}", side="YES", amount=50.0, odds=0.5)
            pf.resolve_bet(f"m{i}", outcome_yes=False)
        perf = pf.get_performance()
        assert perf["wins"] == 0
        assert perf["losses"] == 3
        assert perf["win_rate"] == 0.0
        assert perf["total_pnl"] == pytest.approx(-150.0)

    def test_performance_has_sharpe_and_drawdown(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", amount=100.0, odds=0.5)
        pf.resolve_bet("m1", outcome_yes=True)
        perf = pf.get_performance()
        assert "sharpe_ratio" in perf
        assert "max_drawdown" in perf


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_save_and_reload(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1", side="YES", amount=100.0, odds=0.5)
        _place_default_bet(pf, market_id="m2", side="NO", amount=200.0, odds=0.6)
        pf.resolve_bet("m1", outcome_yes=True)

        # Reload from disk
        pf2 = PaperPortfolio(initial_balance=10_000.0, data_dir=tmp_path)
        assert len(pf2.get_open_positions()) == 1
        assert len(pf2.get_resolved_positions()) == 1
        assert pf2.balance == pytest.approx(pf.balance)

    def test_jsonl_file_written(self, tmp_path):
        pf = _make_portfolio(tmp_path)
        _place_default_bet(pf, market_id="m1")
        filepath = tmp_path / "portfolio.jsonl"
        assert filepath.exists()
        lines = filepath.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["market_id"] == "m1"

    def test_empty_file_loads_cleanly(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "portfolio.jsonl").write_text("")
        pf = PaperPortfolio(initial_balance=10_000.0, data_dir=tmp_path)
        assert pf.balance == 10_000.0
        assert pf.get_open_positions() == []


# ---------------------------------------------------------------------------
# Balance tracking across multiple operations
# ---------------------------------------------------------------------------

class TestBalanceTracking:

    def test_multiple_bets_and_resolves(self, tmp_path):
        pf = _make_portfolio(tmp_path, balance=1000.0)
        _place_default_bet(pf, market_id="m1", amount=100.0, odds=0.5)
        _place_default_bet(pf, market_id="m2", amount=200.0, odds=0.5)
        assert pf.balance == pytest.approx(700.0)

        # Resolve m1 as win: payout = 100/0.5 = 200
        pf.resolve_bet("m1", outcome_yes=True)
        assert pf.balance == pytest.approx(900.0)

        # Resolve m2 as loss: payout = 0
        pf.resolve_bet("m2", outcome_yes=False)
        assert pf.balance == pytest.approx(900.0)

    def test_total_value_includes_open_positions(self, tmp_path):
        pf = _make_portfolio(tmp_path, balance=1000.0)
        _place_default_bet(pf, market_id="m1", amount=100.0, odds=0.5)
        # balance = 900, open bet = 100, total_value = 1000
        assert pf.total_value == pytest.approx(1000.0)
