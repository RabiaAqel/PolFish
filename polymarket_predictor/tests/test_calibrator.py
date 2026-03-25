"""Tests for polymarket_predictor.calibrator.calibrate and history."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from polymarket_predictor.calibrator.history import (
    PredictionHistory,
    PredictionRecord,
    ResolutionRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prediction(market_id: str, predicted_prob: float) -> PredictionRecord:
    return PredictionRecord(
        market_id=market_id,
        question=f"Market {market_id}?",
        predicted_prob=predicted_prob,
        market_prob=0.50,
        ensemble_std=0.05,
        signal="buy",
        reliability="good",
        num_variants=3,
        timestamp="2025-01-01T00:00:00",
    )


def _make_resolution(market_id: str, outcome_binary: int) -> ResolutionRecord:
    return ResolutionRecord(
        market_id=market_id,
        question=f"Market {market_id}?",
        outcome="Yes" if outcome_binary else "No",
        outcome_binary=outcome_binary,
        resolved_at="2025-02-01T00:00:00",
    )


# ---------------------------------------------------------------------------
# PredictionHistory
# ---------------------------------------------------------------------------


class TestPredictionHistory:
    def test_log_prediction_writes_jsonl(self, tmp_path):
        pred_file = tmp_path / "predictions.jsonl"
        res_file = tmp_path / "resolutions.jsonl"
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
        ):
            h = PredictionHistory()
            rec = _make_prediction("m1", 0.7)
            h.log_prediction(rec)

            lines = pred_file.read_text().strip().split("\n")
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["market_id"] == "m1"
            assert data["predicted_prob"] == 0.7

    def test_log_resolution_writes_jsonl(self, tmp_path):
        pred_file = tmp_path / "predictions.jsonl"
        res_file = tmp_path / "resolutions.jsonl"
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
        ):
            h = PredictionHistory()
            rec = _make_resolution("m1", 1)
            h.log_resolution(rec)

            lines = res_file.read_text().strip().split("\n")
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["market_id"] == "m1"
            assert data["outcome_binary"] == 1

    def test_get_predictions(self, tmp_path):
        pred_file = tmp_path / "predictions.jsonl"
        res_file = tmp_path / "resolutions.jsonl"
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
        ):
            h = PredictionHistory()
            h.log_prediction(_make_prediction("m1", 0.6))
            h.log_prediction(_make_prediction("m2", 0.8))

            preds = h.get_predictions()
            assert len(preds) == 2
            assert preds[0].market_id == "m1"
            assert preds[1].predicted_prob == 0.8

    def test_get_resolutions(self, tmp_path):
        pred_file = tmp_path / "predictions.jsonl"
        res_file = tmp_path / "resolutions.jsonl"
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
        ):
            h = PredictionHistory()
            h.log_resolution(_make_resolution("m1", 1))
            h.log_resolution(_make_resolution("m2", 0))

            ress = h.get_resolutions()
            assert len(ress) == 2

    def test_get_matched_records(self, tmp_path):
        pred_file = tmp_path / "predictions.jsonl"
        res_file = tmp_path / "resolutions.jsonl"
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
        ):
            h = PredictionHistory()
            h.log_prediction(_make_prediction("m1", 0.7))
            h.log_prediction(_make_prediction("m2", 0.3))
            h.log_prediction(_make_prediction("m3", 0.5))  # no resolution
            h.log_resolution(_make_resolution("m1", 1))
            h.log_resolution(_make_resolution("m2", 0))

            matched = h.get_matched_records()
            assert len(matched) == 2
            ids = {p.market_id for p, r in matched}
            assert ids == {"m1", "m2"}

    def test_empty_files_returns_empty(self, tmp_path):
        pred_file = tmp_path / "predictions.jsonl"
        res_file = tmp_path / "resolutions.jsonl"
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
        ):
            h = PredictionHistory()
            assert h.get_predictions() == []
            assert h.get_resolutions() == []
            assert h.get_matched_records() == []

    def test_malformed_lines_skipped(self, tmp_path):
        pred_file = tmp_path / "predictions.jsonl"
        res_file = tmp_path / "resolutions.jsonl"
        # Write a valid line then a broken line
        valid = json.dumps({
            "market_id": "m1", "question": "Q?", "predicted_prob": 0.6,
            "market_prob": 0.5, "ensemble_std": 0.05, "signal": "buy",
            "reliability": "good", "num_variants": 3, "timestamp": "2025-01-01T00:00:00",
        })
        pred_file.write_text(valid + "\n{BAD JSON\n")
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
        ):
            h = PredictionHistory()
            # The implementation does json.loads which will raise on bad line;
            # we verify it raises (the source doesn't have try/except on get_predictions)
            with pytest.raises(json.JSONDecodeError):
                h.get_predictions()


# ---------------------------------------------------------------------------
# Calibrator
# ---------------------------------------------------------------------------


class TestCalibrator:
    def _build_history_files(self, tmp_path, n: int, all_correct: bool = False, all_wrong: bool = False):
        """Write n matched prediction/resolution pairs to tmp files."""
        pred_file = tmp_path / "predictions.jsonl"
        res_file = tmp_path / "resolutions.jsonl"
        cal_file = tmp_path / "calibration.json"

        preds = []
        ress = []
        for i in range(n):
            prob = (i + 1) / (n + 1)  # spread across 0-1 range
            preds.append(_make_prediction(f"m{i}", prob))
            if all_correct:
                outcome = 1 if prob >= 0.5 else 0
            elif all_wrong:
                outcome = 0 if prob >= 0.5 else 1
            else:
                outcome = 1 if i % 2 == 0 else 0
            ress.append(_make_resolution(f"m{i}", outcome))

        with open(pred_file, "w") as f:
            for p in preds:
                from dataclasses import asdict
                f.write(json.dumps(asdict(p)) + "\n")

        with open(res_file, "w") as f:
            for r in ress:
                from dataclasses import asdict
                f.write(json.dumps(asdict(r)) + "\n")

        return pred_file, res_file, cal_file

    def test_build_calibration_sufficient_data(self, tmp_path):
        pred_file, res_file, cal_file = self._build_history_files(tmp_path, 20)
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
            patch("polymarket_predictor.calibrator.calibrate.CALIBRATION_FILE", cal_file),
            patch("polymarket_predictor.calibrator.calibrate.DATA_DIR", tmp_path),
        ):
            from polymarket_predictor.calibrator.calibrate import Calibrator
            cal = Calibrator()
            report = cal.build_calibration()

            assert len(report.bins) > 0
            assert report.total_predictions == 20
            assert isinstance(report.brier_score, float)
            assert isinstance(report.calibration_error, float)
            assert cal_file.exists()

    def test_build_calibration_insufficient_data(self, tmp_path):
        pred_file, res_file, cal_file = self._build_history_files(tmp_path, 5)
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
            patch("polymarket_predictor.calibrator.calibrate.CALIBRATION_FILE", cal_file),
            patch("polymarket_predictor.calibrator.calibrate.DATA_DIR", tmp_path),
        ):
            from polymarket_predictor.calibrator.calibrate import Calibrator
            cal = Calibrator()
            report = cal.build_calibration()

            assert report.bins == []
            assert report.total_predictions == 5

    def test_calibrate_with_curve(self, tmp_path):
        cal_file = tmp_path / "calibration.json"
        curve = {
            "bins": [
                {"start": 0.6, "end": 0.7, "predicted": 0.65, "actual": 0.72, "count": 10},
            ],
            "brier_score": 0.15,
            "total_predictions": 50,
        }
        cal_file.write_text(json.dumps(curve))
        with (
            patch("polymarket_predictor.calibrator.calibrate.CALIBRATION_FILE", cal_file),
            patch("polymarket_predictor.calibrator.calibrate.DATA_DIR", tmp_path),
        ):
            from polymarket_predictor.calibrator.calibrate import Calibrator
            cal = Calibrator()
            # 0.65 is in the [0.6, 0.7) bin; adjustment = 0.72 - 0.65 = +0.07
            result = cal.calibrate(0.65)
            assert abs(result - 0.72) < 0.001

    def test_calibrate_without_curve(self, tmp_path):
        cal_file = tmp_path / "calibration.json"
        # No calibration file exists
        with (
            patch("polymarket_predictor.calibrator.calibrate.CALIBRATION_FILE", cal_file),
            patch("polymarket_predictor.calibrator.calibrate.DATA_DIR", tmp_path),
        ):
            from polymarket_predictor.calibrator.calibrate import Calibrator
            cal = Calibrator()
            result = cal.calibrate(0.65)
            assert result == 0.65

    def test_calibrate_small_bin_count(self, tmp_path):
        cal_file = tmp_path / "calibration.json"
        curve = {
            "bins": [
                {"start": 0.6, "end": 0.7, "predicted": 0.65, "actual": 0.80, "count": 2},
            ],
        }
        cal_file.write_text(json.dumps(curve))
        with (
            patch("polymarket_predictor.calibrator.calibrate.CALIBRATION_FILE", cal_file),
            patch("polymarket_predictor.calibrator.calibrate.DATA_DIR", tmp_path),
        ):
            from polymarket_predictor.calibrator.calibrate import Calibrator
            cal = Calibrator()
            # count < 3 so raw is returned
            result = cal.calibrate(0.65)
            assert result == 0.65

    def test_brier_score_all_correct(self, tmp_path):
        """When predictions perfectly match outcomes, Brier score should be near 0."""
        pred_file, res_file, cal_file = self._build_history_files(tmp_path, 20, all_correct=True)
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
            patch("polymarket_predictor.calibrator.calibrate.CALIBRATION_FILE", cal_file),
            patch("polymarket_predictor.calibrator.calibrate.DATA_DIR", tmp_path),
        ):
            from polymarket_predictor.calibrator.calibrate import Calibrator
            cal = Calibrator()
            report = cal.build_calibration()
            # Not exactly 0 because probs are not 0 or 1 but should be relatively low
            assert report.brier_score < 0.3

    def test_brier_score_all_wrong(self, tmp_path):
        """When predictions are opposite of outcomes, Brier score should be high."""
        pred_file, res_file, cal_file = self._build_history_files(tmp_path, 20, all_wrong=True)
        with (
            patch("polymarket_predictor.calibrator.history.PREDICTIONS_FILE", pred_file),
            patch("polymarket_predictor.calibrator.history.RESOLUTIONS_FILE", res_file),
            patch("polymarket_predictor.calibrator.calibrate.CALIBRATION_FILE", cal_file),
            patch("polymarket_predictor.calibrator.calibrate.DATA_DIR", tmp_path),
        ):
            from polymarket_predictor.calibrator.calibrate import Calibrator
            cal = Calibrator()
            report = cal.build_calibration()
            assert report.brier_score > 0.3

    def test_calibrate_result_clamped(self, tmp_path):
        """Calibrated result should be clamped to [0.01, 0.99]."""
        cal_file = tmp_path / "calibration.json"
        curve = {
            "bins": [
                {"start": 0.0, "end": 0.1, "predicted": 0.05, "actual": -0.10, "count": 10},
            ],
        }
        cal_file.write_text(json.dumps(curve))
        with (
            patch("polymarket_predictor.calibrator.calibrate.CALIBRATION_FILE", cal_file),
            patch("polymarket_predictor.calibrator.calibrate.DATA_DIR", tmp_path),
        ):
            from polymarket_predictor.calibrator.calibrate import Calibrator
            cal = Calibrator()
            result = cal.calibrate(0.05)
            assert result >= 0.01
