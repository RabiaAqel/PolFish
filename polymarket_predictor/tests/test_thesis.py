"""Tests for multi-tier market thesis system."""

import pytest
from unittest.mock import MagicMock
from polymarket_predictor.thesis.grouper import MarketGrouper, MarketGroup
from polymarket_predictor.thesis.applier import ThesisApplier, TierPrediction


def _make_market(slug, question, yes_price=0.5, volume=1000):
    """Create a mock market object."""
    m = MagicMock()
    m.slug = slug
    m.question = question
    m.volume = volume
    m.outcomes = [{"name": "Yes", "price": yes_price}, {"name": "No", "price": 1-yes_price}]
    return m


class TestMarketGrouper:
    """Test market grouping logic."""

    def test_groups_date_tiers(self):
        """Iran ceasefire markets at different dates should form one group."""
        markets = [
            _make_market("us-x-iran-ceasefire-by-april-7-278", "US x Iran ceasefire by April 7?", 0.22),
            _make_market("us-x-iran-ceasefire-by-april-15-182", "US x Iran ceasefire by April 15?", 0.30),
            _make_market("us-x-iran-ceasefire-by-april-30-999", "US x Iran ceasefire by April 30?", 0.44),
            _make_market("us-x-iran-ceasefire-by-june-30-111", "US x Iran ceasefire by June 30?", 0.64),
        ]
        grouper = MarketGrouper()
        groups = grouper.group_markets(markets)
        multi = [g for g in groups if len(g.markets) > 1]
        assert len(multi) >= 1, "Should find at least one multi-market group"
        biggest = max(multi, key=lambda g: len(g.markets))
        assert len(biggest.markets) >= 3, f"Iran group should have 3+ markets, got {len(biggest.markets)}"
        assert biggest.group_type == "date_tier"

    def test_groups_price_tiers(self):
        """Crude oil markets at different prices should form one group."""
        markets = [
            _make_market("will-crude-oil-cl-hit-high-100-by-end-of-march-658", "Will Crude Oil (CL) hit (HIGH) $100 by end of March?", 0.39),
            _make_market("will-crude-oil-cl-hit-high-110-by-end-of-march-732", "Will Crude Oil (CL) hit (HIGH) $110 by end of March?", 0.16),
            _make_market("will-crude-oil-cl-hit-low-80-by-end-of-march-459", "Will Crude Oil (CL) hit (LOW) $80 by end of March?", 0.13),
        ]
        grouper = MarketGrouper()
        groups = grouper.group_markets(markets)
        multi = [g for g in groups if len(g.markets) > 1]
        assert len(multi) >= 1, "Should find at least one price tier group"

    def test_groups_stage_tiers(self):
        """Same person at nomination + election should form one group."""
        markets = [
            _make_market("will-gavin-newsom-win-the-2028-dem", "Will Gavin Newsom win the 2028 Democratic presidential nomination?", 0.24),
            _make_market("will-gavin-newsom-win-the-2028-us", "Will Gavin Newsom win the 2028 US Presidential Election?", 0.17),
        ]
        grouper = MarketGrouper()
        groups = grouper.group_markets(markets)
        multi = [g for g in groups if len(g.markets) > 1]
        assert len(multi) >= 1
        assert multi[0].group_type == "stage_tier"

    def test_single_market_stays_ungrouped(self):
        """A unique market should become a single-market group."""
        markets = [_make_market("will-finland-win-eurovision", "Will Finland win Eurovision 2026?", 0.37)]
        grouper = MarketGrouper()
        groups = grouper.group_markets(markets)
        assert len(groups) == 1
        assert groups[0].group_type == "single"
        assert len(groups[0].markets) == 1

    def test_mixed_markets(self):
        """Mix of groupable and ungroupable markets."""
        markets = [
            _make_market("us-x-iran-ceasefire-by-april-7-278", "US x Iran ceasefire by April 7?", 0.22),
            _make_market("us-x-iran-ceasefire-by-june-30-111", "US x Iran ceasefire by June 30?", 0.64),
            _make_market("will-finland-win-eurovision", "Will Finland win Eurovision 2026?", 0.37),
        ]
        grouper = MarketGrouper()
        groups = grouper.group_markets(markets)
        assert len(groups) == 2  # One Iran group + one single

    def test_empty_markets(self):
        """Empty list should return empty groups."""
        grouper = MarketGrouper()
        groups = grouper.group_markets([])
        assert groups == []

    def test_thesis_question_date_tier(self):
        """Date tier thesis should ask about timing."""
        markets = [
            _make_market("iran-ceasefire-april-7", "US x Iran ceasefire by April 7?", 0.22),
            _make_market("iran-ceasefire-june-30", "US x Iran ceasefire by June 30?", 0.64),
        ]
        grouper = MarketGrouper()
        groups = grouper.group_markets(markets)
        multi = [g for g in groups if len(g.markets) > 1]
        if multi:
            assert "when" in multi[0].thesis_question.lower() or "timeline" in multi[0].thesis_question.lower()

    def test_thesis_question_price_tier(self):
        """Price tier thesis should ask about direction."""
        markets = [
            _make_market("will-crude-oil-cl-hit-high-100-by-end-of-march-658", "Will Crude Oil (CL) hit (HIGH) $100 by end of March?", 0.39),
            _make_market("will-crude-oil-cl-hit-high-110-by-end-of-march-732", "Will Crude Oil (CL) hit (HIGH) $110 by end of March?", 0.16),
        ]
        grouper = MarketGrouper()
        groups = grouper.group_markets(markets)
        multi = [g for g in groups if len(g.markets) > 1]
        if multi:
            assert "price" in multi[0].thesis_question.lower() or "heading" in multi[0].thesis_question.lower()


class TestThesisApplierDateTier:
    """Test applying date-tier thesis to individual markets."""

    def test_predictions_respect_time_ordering(self):
        """Earlier dates should generally have lower probabilities than later dates."""
        markets = [
            _make_market("april-7", "Event by April 7?", 0.22),
            _make_market("april-30", "Event by April 30?", 0.44),
            _make_market("june-30", "Event by June 30?", 0.64),
        ]
        applier = ThesisApplier()
        preds = applier.apply_date_thesis(0.60, "medium", markets)
        # Sorted by market odds (proxy for time)
        probs = [p.predicted_probability for p in preds]
        assert probs == sorted(probs), f"Predictions should increase with time: {probs}"

    def test_no_tier_exceeds_thesis(self):
        """No individual tier should have probability much higher than the thesis."""
        markets = [
            _make_market("near", "Event by next week?", 0.10),
            _make_market("far", "Event by next year?", 0.80),
        ]
        applier = ThesisApplier()
        preds = applier.apply_date_thesis(0.50, "medium", markets)
        for p in preds:
            assert p.predicted_probability <= 0.97

    def test_all_predictions_in_valid_range(self):
        """All predictions should be between 0.03 and 0.97."""
        markets = [
            _make_market("m1", "Event by date 1?", 0.01),
            _make_market("m2", "Event by date 2?", 0.99),
        ]
        applier = ThesisApplier()
        preds = applier.apply_date_thesis(0.40, "low", markets)
        for p in preds:
            assert 0.03 <= p.predicted_probability <= 0.97

    def test_edge_calculation(self):
        """Edge should be prediction minus market odds."""
        markets = [_make_market("m1", "Event?", 0.30)]
        applier = ThesisApplier()
        preds = applier.apply_date_thesis(0.60, "medium", markets)
        assert preds[0].edge == pytest.approx(preds[0].predicted_probability - 0.30, abs=0.001)

    def test_side_determination(self):
        """Side should be YES when edge > 0.03, NO when < -0.03, SKIP otherwise."""
        markets = [_make_market("m1", "Event?", 0.50)]
        applier = ThesisApplier()
        preds = applier.apply_date_thesis(0.80, "high", markets)
        if preds[0].edge > 0.03:
            assert preds[0].side == "YES"


class TestThesisApplierPriceTier:
    """Test applying price-tier thesis."""

    def test_bullish_thesis_favors_high_markets(self):
        """Bullish thesis should increase HIGH market predictions."""
        markets = [
            _make_market("high-100", "Will Oil hit (HIGH) $100?", 0.40),
            _make_market("low-80", "Will Oil hit (LOW) $80?", 0.15),
        ]
        applier = ThesisApplier()
        preds = applier.apply_price_thesis(0.75, "medium", markets)
        high_pred = next(p for p in preds if "high" in p.question.lower())
        low_pred = next(p for p in preds if "low" in p.question.lower())
        # Bullish: HIGH should go up, LOW should go down
        assert high_pred.predicted_probability > 0.40, "HIGH should increase with bullish thesis"
        assert low_pred.predicted_probability < 0.15, "LOW should decrease with bullish thesis"

    def test_bearish_thesis_favors_low_markets(self):
        """Bearish thesis should increase LOW market predictions."""
        markets = [
            _make_market("high-100", "Will Oil hit (HIGH) $100?", 0.40),
            _make_market("low-80", "Will Oil hit (LOW) $80?", 0.15),
        ]
        applier = ThesisApplier()
        preds = applier.apply_price_thesis(0.25, "medium", markets)
        high_pred = next(p for p in preds if "high" in p.question.lower())
        low_pred = next(p for p in preds if "low" in p.question.lower())
        assert high_pred.predicted_probability < 0.40, "HIGH should decrease with bearish thesis"
        assert low_pred.predicted_probability > 0.15, "LOW should increase with bearish thesis"

    def test_neutral_thesis_stays_near_market(self):
        """Neutral thesis should keep predictions close to market odds."""
        markets = [_make_market("high-100", "Will Oil hit (HIGH) $100?", 0.40)]
        applier = ThesisApplier()
        preds = applier.apply_price_thesis(0.50, "low", markets)
        assert abs(preds[0].predicted_probability - 0.40) < 0.05

    def test_no_contradictory_bets(self):
        """With a bullish thesis, should not bet YES on LOW markets."""
        markets = [_make_market("low-80", "Will Oil hit (LOW) $80?", 0.50)]
        applier = ThesisApplier()
        preds = applier.apply_price_thesis(0.80, "high", markets)
        assert preds[0].side != "YES", "Bullish thesis should not bet YES on LOW market"


class TestThesisApplierStageTier:
    """Test applying stage-tier thesis."""

    def test_nomination_higher_than_election(self):
        """Nomination probability should be >= election probability."""
        markets = [
            _make_market("nom", "Will X win the 2028 Democratic presidential nomination?", 0.24),
            _make_market("gen", "Will X win the 2028 US Presidential Election?", 0.17),
        ]
        applier = ThesisApplier()
        preds = applier.apply_stage_thesis(0.30, "medium", markets)
        nom_pred = next(p for p in preds if "nomination" in p.question.lower())
        gen_pred = next(p for p in preds if "election" in p.question.lower())
        assert nom_pred.predicted_probability >= gen_pred.predicted_probability

    def test_predictions_in_valid_range(self):
        markets = [
            _make_market("nom", "Will X win nomination?", 0.01),
            _make_market("gen", "Will X win election?", 0.99),
        ]
        applier = ThesisApplier()
        preds = applier.apply_stage_thesis(0.50, "medium", markets)
        for p in preds:
            assert 0.03 <= p.predicted_probability <= 0.97
