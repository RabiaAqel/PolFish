"""Tests for polymarket_predictor.analyzer.method_tracker."""

from __future__ import annotations

import json
import pytest
from dataclasses import asdict

from polymarket_predictor.analyzer.method_tracker import (
    MethodTracker,
    PredictionComparison,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_comparison(
    market_id: str = "m1",
    llm_pred: float = 0.7,
    quant_pred: float = 0.6,
    combined: float = 0.64,
    market_odds: float = 0.5,
) -> PredictionComparison:
    return PredictionComparison(
        market_id=market_id,
        question=f"Test market {market_id}?",
        market_odds=market_odds,
        llm_prediction=llm_pred,
        quant_prediction=quant_pred,
        combined_prediction=combined,
        llm_weight=0.4,
        quant_weight=0.6,
    )


# ---------------------------------------------------------------------------
# Initial weights
# ---------------------------------------------------------------------------


class TestInitialWeights:

    def test_initial_weights(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        assert tracker.llm_weight == pytest.approx(0.40)
        assert tracker.quant_weight == pytest.approx(0.60)

    def test_weights_sum_to_one(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        assert tracker.llm_weight + tracker.quant_weight == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Blend
# ---------------------------------------------------------------------------


class TestBlend:

    def test_blend_with_default_weights(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        result = tracker.blend(llm_pred=0.8, quant_pred=0.6)
        expected = 0.4 * 0.8 + 0.6 * 0.6  # = 0.32 + 0.36 = 0.68
        assert result == pytest.approx(expected)

    def test_blend_extremes(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        result = tracker.blend(llm_pred=1.0, quant_pred=0.0)
        assert result == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# Log prediction
# ---------------------------------------------------------------------------


class TestLogPrediction:

    def test_log_prediction_creates_file(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        comp = _make_comparison()
        tracker.log_prediction(comp)
        assert (tmp_path / "method_comparisons.jsonl").exists()

    def test_log_prediction_persists(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        comp = _make_comparison(market_id="persist_test", llm_pred=0.75)
        tracker.log_prediction(comp)

        # Reload and verify
        tracker2 = MethodTracker(data_dir=tmp_path)
        all_comps = tracker2._load_all()
        assert len(all_comps) == 1
        assert all_comps[0]["market_id"] == "persist_test"
        assert all_comps[0]["llm_prediction"] == pytest.approx(0.75)

    def test_log_prediction_sets_timestamp(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        comp = _make_comparison()
        comp.timestamp = ""
        tracker.log_prediction(comp)
        all_comps = tracker._load_all()
        assert all_comps[0]["timestamp"] != ""


# ---------------------------------------------------------------------------
# Resolve prediction
# ---------------------------------------------------------------------------


class TestResolvePrediction:

    def test_resolve_prediction_scores_correctly_yes(self, tmp_path):
        """YES outcome: LLM=0.7 -> correct, Quant=0.3 -> wrong."""
        tracker = MethodTracker(data_dir=tmp_path)
        comp = _make_comparison(
            market_id="resolve_yes",
            llm_pred=0.7,
            quant_pred=0.3,
            combined=0.46,
        )
        tracker.log_prediction(comp)
        result = tracker.resolve_prediction("resolve_yes", outcome_yes=True)

        assert result is not None
        assert result.llm_correct is True   # 0.7 > 0.5 and outcome is YES
        assert result.quant_correct is False  # 0.3 < 0.5 and outcome is YES
        assert result.resolved is True

    def test_resolve_prediction_no_outcome(self, tmp_path):
        """NO outcome: prediction > 0.5 is wrong, < 0.5 is correct."""
        tracker = MethodTracker(data_dir=tmp_path)
        comp = _make_comparison(
            market_id="resolve_no",
            llm_pred=0.3,   # Correct for NO
            quant_pred=0.7,  # Wrong for NO
            combined=0.54,
        )
        tracker.log_prediction(comp)
        result = tracker.resolve_prediction("resolve_no", outcome_yes=False)

        assert result is not None
        assert result.llm_correct is True   # 0.3 < 0.5 and outcome is NO
        assert result.quant_correct is False  # 0.7 > 0.5 and outcome is NO

    def test_resolve_nonexistent_market(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        result = tracker.resolve_prediction("nonexistent", outcome_yes=True)
        assert result is None


# ---------------------------------------------------------------------------
# Brier score
# ---------------------------------------------------------------------------


class TestBrierScore:

    def test_brier_score_perfect(self, tmp_path):
        """prediction=1.0, outcome=YES -> brier=0.0."""
        tracker = MethodTracker(data_dir=tmp_path)
        comp = _make_comparison(
            market_id="brier_perfect",
            llm_pred=1.0, quant_pred=1.0, combined=1.0,
        )
        tracker.log_prediction(comp)
        result = tracker.resolve_prediction("brier_perfect", outcome_yes=True)
        assert result.llm_brier == pytest.approx(0.0)

    def test_brier_score_worst(self, tmp_path):
        """prediction=0.0, outcome=YES -> brier=1.0."""
        tracker = MethodTracker(data_dir=tmp_path)
        comp = _make_comparison(
            market_id="brier_worst",
            llm_pred=0.0, quant_pred=0.0, combined=0.0,
        )
        tracker.log_prediction(comp)
        result = tracker.resolve_prediction("brier_worst", outcome_yes=True)
        assert result.llm_brier == pytest.approx(1.0)

    def test_brier_score_midpoint(self, tmp_path):
        """prediction=0.5, outcome=YES -> brier=0.25."""
        tracker = MethodTracker(data_dir=tmp_path)
        comp = _make_comparison(
            market_id="brier_mid",
            llm_pred=0.5, quant_pred=0.5, combined=0.5,
        )
        tracker.log_prediction(comp)
        result = tracker.resolve_prediction("brier_mid", outcome_yes=True)
        assert result.llm_brier == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Weight adjustment
# ---------------------------------------------------------------------------


class TestWeightAdjustment:

    def _seed_resolved(self, tracker, count, quant_better=True):
        """Seed tracker with resolved predictions where one method is better."""
        for i in range(count):
            if quant_better:
                # Quant predicts correctly (YES outcome, pred > 0.5)
                # LLM predicts incorrectly
                comp = _make_comparison(
                    market_id=f"adj_{i}",
                    llm_pred=0.3,   # Wrong for YES
                    quant_pred=0.8,  # Correct for YES
                    combined=0.6,
                )
            else:
                comp = _make_comparison(
                    market_id=f"adj_{i}",
                    llm_pred=0.8,
                    quant_pred=0.3,
                    combined=0.5,
                )
            tracker.log_prediction(comp)
            tracker.resolve_prediction(f"adj_{i}", outcome_yes=True)

    def test_weight_adjustment_after_10_resolved(self, tmp_path):
        """Quant consistently better -> quant weight increases."""
        tracker = MethodTracker(data_dir=tmp_path)
        self._seed_resolved(tracker, 12, quant_better=True)

        # Quant has lower Brier score, so quant weight should go up
        assert tracker.quant_weight > MethodTracker.DEFAULT_QUANT_WEIGHT, (
            f"Expected quant_weight > {MethodTracker.DEFAULT_QUANT_WEIGHT}, "
            f"got {tracker.quant_weight}"
        )

    def test_weight_adjustment_minimum_clamp(self, tmp_path):
        """Weight never below 0.15."""
        tracker = MethodTracker(data_dir=tmp_path)
        # Seed many resolved where LLM is always wrong
        self._seed_resolved(tracker, 50, quant_better=True)
        assert tracker.llm_weight >= MethodTracker.MIN_WEIGHT, (
            f"LLM weight {tracker.llm_weight} below minimum {MethodTracker.MIN_WEIGHT}"
        )

    def test_weight_adjustment_maximum_clamp(self, tmp_path):
        """Weight never above 0.85."""
        tracker = MethodTracker(data_dir=tmp_path)
        self._seed_resolved(tracker, 50, quant_better=True)
        assert tracker.quant_weight <= MethodTracker.MAX_WEIGHT, (
            f"Quant weight {tracker.quant_weight} above maximum {MethodTracker.MAX_WEIGHT}"
        )

    def test_no_adjustment_below_10_resolved(self, tmp_path):
        """Only 5 resolved -> weights unchanged from default."""
        tracker = MethodTracker(data_dir=tmp_path)
        self._seed_resolved(tracker, 5, quant_better=True)
        assert tracker.llm_weight == pytest.approx(MethodTracker.DEFAULT_LLM_WEIGHT)
        assert tracker.quant_weight == pytest.approx(MethodTracker.DEFAULT_QUANT_WEIGHT)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


class TestGetPerformance:

    def test_get_performance_empty(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        perf = tracker.get_performance()
        assert perf["total_predictions"] == 0
        assert perf["resolved_predictions"] == 0
        assert perf["best_method"] == "unknown"

    def test_get_performance_with_data(self, tmp_path):
        tracker = MethodTracker(data_dir=tmp_path)
        for i in range(3):
            comp = _make_comparison(
                market_id=f"perf_{i}",
                llm_pred=0.7 + i * 0.05,
                quant_pred=0.6,
                combined=0.64,
            )
            tracker.log_prediction(comp)
            tracker.resolve_prediction(f"perf_{i}", outcome_yes=True)

        perf = tracker.get_performance()
        assert perf["total_predictions"] == 3
        assert perf["resolved_predictions"] == 3
        assert "llm" in perf["methods"]
        assert "quant" in perf["methods"]
        assert "combined" in perf["methods"]
        # All predictions > 0.5 resolved as YES -> all correct
        assert perf["methods"]["llm"]["correct"] == 3
        assert perf["methods"]["llm"]["accuracy"] == pytest.approx(1.0)

    def test_best_method_selection(self, tmp_path):
        """Method with highest accuracy is 'best'."""
        tracker = MethodTracker(data_dir=tmp_path)
        # LLM always right, quant always wrong
        for i in range(5):
            comp = _make_comparison(
                market_id=f"best_{i}",
                llm_pred=0.8,    # correct for YES
                quant_pred=0.3,  # wrong for YES
                combined=0.5,
            )
            tracker.log_prediction(comp)
            tracker.resolve_prediction(f"best_{i}", outcome_yes=True)

        perf = tracker.get_performance()
        # LLM should be best (100% accuracy vs 0%)
        assert perf["best_method"] == "llm"
