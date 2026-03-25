"""Tests for polymarket_predictor.cost_tracker."""

import threading
import pytest

from polymarket_predictor.cost_tracker import (
    CostReport,
    CostTracker,
    TokenUsage,
    get_tracker,
    set_tracker,
    MODEL_PRICING,
    DEFAULT_PRICING,
)


# ---------------------------------------------------------------------------
# Basic recording and reporting
# ---------------------------------------------------------------------------

class TestCostTrackerBasic:

    def test_record_and_report(self):
        ct = CostTracker(model="gpt-4o")
        ct.record(prompt_tokens=100, completion_tokens=50, step="test")
        report = ct.get_report()
        assert report.total_prompt_tokens == 100
        assert report.total_completion_tokens == 50
        assert report.total_tokens == 150

    def test_multiple_records_summed(self):
        ct = CostTracker()
        ct.record(prompt_tokens=100, completion_tokens=50, step="a")
        ct.record(prompt_tokens=200, completion_tokens=100, step="b")
        report = ct.get_report()
        assert report.total_prompt_tokens == 300
        assert report.total_completion_tokens == 150
        assert report.total_tokens == 450


# ---------------------------------------------------------------------------
# Per-step breakdown
# ---------------------------------------------------------------------------

class TestStepBreakdown:

    def test_multiple_steps(self):
        ct = CostTracker()
        ct.record(prompt_tokens=100, completion_tokens=50, step="ontology")
        ct.record(prompt_tokens=200, completion_tokens=100, step="graph")
        ct.record(prompt_tokens=50, completion_tokens=25, step="simulation")
        report = ct.get_report()
        assert len(report.steps) == 3
        step_names = {s["step"] for s in report.steps}
        assert step_names == {"ontology", "graph", "simulation"}

    def test_same_step_aggregated(self):
        ct = CostTracker()
        ct.record(prompt_tokens=100, completion_tokens=50, step="ontology")
        ct.record(prompt_tokens=200, completion_tokens=100, step="ontology")
        report = ct.get_report()
        assert len(report.steps) == 1
        assert report.steps[0]["prompt_tokens"] == 300
        assert report.steps[0]["completion_tokens"] == 150

    def test_missing_step_labeled_unknown(self):
        ct = CostTracker()
        ct.record(prompt_tokens=100, completion_tokens=50)
        report = ct.get_report()
        assert report.steps[0]["step"] == "unknown"


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

class TestCostCalculation:

    def test_gpt4o_pricing(self):
        ct = CostTracker(model="gpt-4o")
        ct.record(prompt_tokens=1000, completion_tokens=500, step="test")
        report = ct.get_report()
        # input: 2.50/1M * 1000 = 0.0025
        # output: 10.00/1M * 500 = 0.005
        expected = (1000 * 2.50 + 500 * 10.00) / 1_000_000
        assert report.total_cost_usd == pytest.approx(expected)

    def test_gpt4o_mini_pricing(self):
        ct = CostTracker(model="gpt-4o-mini")
        ct.record(prompt_tokens=1000, completion_tokens=500, step="test")
        report = ct.get_report()
        expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
        assert report.total_cost_usd == pytest.approx(expected)

    def test_unknown_model_falls_back_to_default(self):
        ct = CostTracker(model="gpt-5-turbo-imaginary")
        ct.record(prompt_tokens=1000, completion_tokens=500, step="test")
        report = ct.get_report()
        expected = (1000 * DEFAULT_PRICING["input"] + 500 * DEFAULT_PRICING["output"]) / 1_000_000
        assert report.total_cost_usd == pytest.approx(expected)

    def test_step_level_cost(self):
        ct = CostTracker(model="gpt-4o")
        ct.record(prompt_tokens=1000, completion_tokens=500, step="ontology")
        report = ct.get_report()
        expected = (1000 * 2.50 + 500 * 10.00) / 1_000_000
        assert report.steps[0]["cost_usd"] == pytest.approx(expected, abs=1e-4)


# ---------------------------------------------------------------------------
# Empty tracker
# ---------------------------------------------------------------------------

class TestEmptyTracker:

    def test_empty_report(self):
        ct = CostTracker()
        report = ct.get_report()
        assert report.total_prompt_tokens == 0
        assert report.total_completion_tokens == 0
        assert report.total_tokens == 0
        assert report.total_cost_usd == 0.0
        assert report.steps == []


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:

    def test_reset_clears_all(self):
        ct = CostTracker()
        ct.record(prompt_tokens=100, completion_tokens=50, step="a")
        ct.reset()
        report = ct.get_report()
        assert report.total_tokens == 0
        assert report.steps == []


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_records(self):
        ct = CostTracker()
        num_threads = 20
        records_per_thread = 100

        def worker():
            for _ in range(records_per_thread):
                ct.record(prompt_tokens=10, completion_tokens=5, step="concurrent")

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        report = ct.get_report()
        expected_prompt = num_threads * records_per_thread * 10
        expected_completion = num_threads * records_per_thread * 5
        assert report.total_prompt_tokens == expected_prompt
        assert report.total_completion_tokens == expected_completion


# ---------------------------------------------------------------------------
# Global tracker
# ---------------------------------------------------------------------------

class TestGlobalTracker:

    def test_set_and_get_tracker(self):
        original = get_tracker()
        try:
            ct = CostTracker(model="gpt-4o-mini")
            set_tracker(ct)
            assert get_tracker() is ct
        finally:
            set_tracker(original)

    def test_set_tracker_none(self):
        original = get_tracker()
        try:
            set_tracker(None)
            assert get_tracker() is None
        finally:
            set_tracker(original)


# ---------------------------------------------------------------------------
# CostReport.to_dict
# ---------------------------------------------------------------------------

class TestCostReportToDict:

    def test_serialization(self):
        ct = CostTracker(model="gpt-4o")
        ct.record(prompt_tokens=1000, completion_tokens=500, step="test")
        report = ct.get_report()
        d = report.to_dict()
        assert d["total_prompt_tokens"] == 1000
        assert d["total_completion_tokens"] == 500
        assert d["total_tokens"] == 1500
        assert d["model"] == "gpt-4o"
        assert isinstance(d["total_cost_usd"], float)
        assert isinstance(d["steps"], list)
        assert len(d["steps"]) == 1

    def test_to_dict_cost_rounded(self):
        ct = CostTracker(model="gpt-4o")
        ct.record(prompt_tokens=1, completion_tokens=1, step="tiny")
        report = ct.get_report()
        d = report.to_dict()
        # Should be rounded to 4 decimal places
        cost_str = str(d["total_cost_usd"])
        # At most 4 decimal places
        if "." in cost_str:
            assert len(cost_str.split(".")[1]) <= 4


# ---------------------------------------------------------------------------
# TokenUsage auto total
# ---------------------------------------------------------------------------

class TestTokenUsage:

    def test_total_tokens_auto_calculated(self):
        ct = CostTracker()
        ct.record(prompt_tokens=100, completion_tokens=50, total_tokens=0, step="x")
        report = ct.get_report()
        assert report.total_tokens == 150

    def test_total_tokens_explicit(self):
        ct = CostTracker()
        ct.record(prompt_tokens=100, completion_tokens=50, total_tokens=200, step="x")
        # The report sums prompt+completion for total_tokens, not the stored total_tokens
        report = ct.get_report()
        assert report.total_tokens == 150  # 100 + 50 from aggregation
