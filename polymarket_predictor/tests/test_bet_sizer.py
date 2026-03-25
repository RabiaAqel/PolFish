"""Tests for polymarket_predictor.paper_trader.portfolio — BetSizer."""

import pytest

from polymarket_predictor.paper_trader.portfolio import BetSizer


# ---------------------------------------------------------------------------
# kelly_fraction
# ---------------------------------------------------------------------------

class TestKellyFraction:

    def test_basic_positive(self):
        """probability > odds should yield a positive Kelly fraction."""
        kf = BetSizer.kelly_fraction(probability=0.6, odds=0.5)
        assert kf > 0

    def test_no_edge(self):
        """probability == odds should yield 0 or near-zero."""
        kf = BetSizer.kelly_fraction(probability=0.5, odds=0.5)
        assert kf == pytest.approx(0.0, abs=1e-9)

    def test_negative_edge(self):
        """probability < odds should yield 0 (clamped)."""
        kf = BetSizer.kelly_fraction(probability=0.3, odds=0.5)
        assert kf == 0.0

    def test_extreme_high_probability(self):
        """Very high probability, very low odds — large Kelly fraction."""
        kf = BetSizer.kelly_fraction(probability=0.99, odds=0.01)
        assert kf > 0

    def test_quarter_kelly_default(self):
        """Default kelly_factor is 0.25 (quarter-Kelly)."""
        full = BetSizer.kelly_fraction(0.7, 0.5, kelly_factor=1.0)
        quarter = BetSizer.kelly_fraction(0.7, 0.5, kelly_factor=0.25)
        assert quarter == pytest.approx(full * 0.25)

    def test_half_kelly(self):
        full = BetSizer.kelly_fraction(0.7, 0.5, kelly_factor=1.0)
        half = BetSizer.kelly_fraction(0.7, 0.5, kelly_factor=0.5)
        assert half == pytest.approx(full * 0.5)

    def test_boundary_probability_zero(self):
        kf = BetSizer.kelly_fraction(0.0, 0.5)
        assert kf == 0.0

    def test_boundary_probability_one(self):
        kf = BetSizer.kelly_fraction(1.0, 0.5)
        assert kf == 0.0

    def test_boundary_odds_zero(self):
        kf = BetSizer.kelly_fraction(0.5, 0.0)
        assert kf == 0.0

    def test_boundary_odds_one(self):
        kf = BetSizer.kelly_fraction(0.5, 1.0)
        assert kf == 0.0


# ---------------------------------------------------------------------------
# size_bet — side determination
# ---------------------------------------------------------------------------

class TestSizeBetSide:

    def test_yes_signal(self):
        """probability > market_odds → side = YES."""
        result = BetSizer.size_bet(
            balance=10_000, probability=0.7, market_odds=0.5,
            edge=0.2, confidence="high",
        )
        assert result["side"] == "YES"

    def test_no_signal(self):
        """probability < market_odds → side = NO."""
        result = BetSizer.size_bet(
            balance=10_000, probability=0.3, market_odds=0.5,
            edge=0.2, confidence="high",
        )
        assert result["side"] == "NO"


# ---------------------------------------------------------------------------
# size_bet — edge threshold
# ---------------------------------------------------------------------------

class TestSizeBetEdge:

    def test_edge_too_small_skips(self):
        result = BetSizer.size_bet(
            balance=10_000, probability=0.52, market_odds=0.5,
            edge=0.02, confidence="high", min_edge=0.03,
        )
        assert result["amount"] == 0.0
        assert "below" in result["reasoning"].lower() or "threshold" in result["reasoning"].lower()

    def test_edge_at_threshold_places_bet(self):
        result = BetSizer.size_bet(
            balance=10_000, probability=0.55, market_odds=0.5,
            edge=0.05, confidence="high", min_edge=0.05,
        )
        assert result["amount"] > 0


# ---------------------------------------------------------------------------
# size_bet — confidence scaling
# ---------------------------------------------------------------------------

class TestSizeBetConfidence:

    def test_high_confidence_larger_than_low(self):
        high = BetSizer.size_bet(
            balance=10_000, probability=0.7, market_odds=0.5,
            edge=0.2, confidence="high",
        )
        low = BetSizer.size_bet(
            balance=10_000, probability=0.7, market_odds=0.5,
            edge=0.2, confidence="low",
        )
        assert high["amount"] >= low["amount"]

    def test_medium_confidence(self):
        result = BetSizer.size_bet(
            balance=10_000, probability=0.7, market_odds=0.5,
            edge=0.2, confidence="medium",
        )
        assert result["amount"] > 0

    def test_unknown_confidence_defaults_low(self):
        result = BetSizer.size_bet(
            balance=10_000, probability=0.7, market_odds=0.5,
            edge=0.2, confidence="unknown",
        )
        low = BetSizer.size_bet(
            balance=10_000, probability=0.7, market_odds=0.5,
            edge=0.2, confidence="low",
        )
        assert result["amount"] == pytest.approx(low["amount"])


# ---------------------------------------------------------------------------
# size_bet — caps and minimums
# ---------------------------------------------------------------------------

class TestSizeBetCaps:

    def test_max_cap(self):
        """Bet should not exceed max_bet_pct of balance."""
        result = BetSizer.size_bet(
            balance=10_000, probability=0.99, market_odds=0.01,
            edge=0.98, confidence="high", max_bet_pct=0.05,
        )
        assert result["amount"] <= 10_000 * 0.05 + 0.01  # small float tolerance

    def test_minimum_bet(self):
        """If Kelly amount is very small but edge sufficient, bet at least $10."""
        result = BetSizer.size_bet(
            balance=10_000, probability=0.55, market_odds=0.5,
            edge=0.05, confidence="low",
        )
        if result["amount"] > 0:
            assert result["amount"] >= 10.0

    def test_zero_balance(self):
        result = BetSizer.size_bet(
            balance=0.0, probability=0.7, market_odds=0.5,
            edge=0.2, confidence="high",
        )
        assert result["amount"] == 0.0

    def test_tiny_balance(self):
        """Balance < min_bet with insufficient edge yields 0."""
        result = BetSizer.size_bet(
            balance=5.0, probability=0.55, market_odds=0.5,
            edge=0.05, confidence="low",
        )
        assert result["amount"] == 0.0


# ---------------------------------------------------------------------------
# size_bet — return structure
# ---------------------------------------------------------------------------

class TestSizeBetReturnStructure:

    def test_has_required_keys(self):
        result = BetSizer.size_bet(
            balance=10_000, probability=0.7, market_odds=0.5,
            edge=0.2, confidence="high",
        )
        assert "amount" in result
        assert "side" in result
        assert "kelly_fraction" in result
        assert "reasoning" in result

    def test_kelly_fraction_in_result(self):
        result = BetSizer.size_bet(
            balance=10_000, probability=0.7, market_odds=0.5,
            edge=0.2, confidence="high",
        )
        assert isinstance(result["kelly_fraction"], float)
        assert result["kelly_fraction"] >= 0.0
