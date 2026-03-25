import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

from polymarket_predictor.calibrator.history import PredictionHistory
from polymarket_predictor.config import DATA_DIR

logger = logging.getLogger(__name__)

CALIBRATION_FILE = DATA_DIR / "calibration.json"

@dataclass
class CalibrationBin:
    bin_start: float
    bin_end: float
    predicted_mean: float
    actual_rate: float
    count: int

@dataclass
class CalibrationReport:
    bins: list[CalibrationBin]
    brier_score: float
    total_predictions: int
    calibration_error: float   # Mean absolute calibration error

class Calibrator:
    def __init__(self):
        self.history = PredictionHistory()
        self._curve: dict | None = None
        self._load_curve()

    def _load_curve(self):
        """Load saved calibration curve if it exists."""
        if CALIBRATION_FILE.exists():
            self._curve = json.loads(CALIBRATION_FILE.read_text())
            logger.info(f"Loaded calibration curve with {len(self._curve.get('bins', []))} bins")

    def build_calibration(self) -> CalibrationReport:
        """Build calibration curve from matched prediction/resolution history."""
        matched = self.history.get_matched_records()
        if len(matched) < 10:
            logger.warning(f"Only {len(matched)} matched records - need at least 10 for calibration")
            return CalibrationReport(bins=[], brier_score=0, total_predictions=len(matched), calibration_error=0)

        # Bin predictions into deciles
        num_bins = 10
        bins = []
        for i in range(num_bins):
            bin_start = i / num_bins
            bin_end = (i + 1) / num_bins
            in_bin = [(p, r) for p, r in matched if bin_start <= p.predicted_prob < bin_end]
            if in_bin:
                predicted_mean = sum(p.predicted_prob for p, r in in_bin) / len(in_bin)
                actual_rate = sum(r.outcome_binary for p, r in in_bin) / len(in_bin)
                bins.append(CalibrationBin(bin_start, bin_end, predicted_mean, actual_rate, len(in_bin)))

        # Brier score
        brier = sum((p.predicted_prob - r.outcome_binary) ** 2 for p, r in matched) / len(matched)

        # Mean absolute calibration error
        cal_error = sum(abs(b.predicted_mean - b.actual_rate) * b.count for b in bins) / len(matched) if bins else 0

        report = CalibrationReport(bins=bins, brier_score=brier, total_predictions=len(matched), calibration_error=cal_error)

        # Save curve
        curve_data = {
            "bins": [{"start": b.bin_start, "end": b.bin_end, "predicted": b.predicted_mean, "actual": b.actual_rate, "count": b.count} for b in bins],
            "brier_score": brier,
            "total_predictions": len(matched),
        }
        CALIBRATION_FILE.write_text(json.dumps(curve_data, indent=2))
        self._curve = curve_data
        logger.info(f"Calibration built: Brier={brier:.4f}, CalError={cal_error:.4f}, N={len(matched)}")

        return report

    def calibrate(self, raw_probability: float) -> float:
        """Apply calibration curve to a raw prediction. Returns adjusted probability."""
        if not self._curve or not self._curve.get("bins"):
            return raw_probability  # No calibration data yet, return raw

        bins = self._curve["bins"]

        # Find matching bin
        for b in bins:
            if b["start"] <= raw_probability < b["end"]:
                if b["count"] < 3:
                    return raw_probability  # Not enough data in this bin
                # Linear interpolation between predicted and actual
                adjustment = b["actual"] - b["predicted"]
                calibrated = raw_probability + adjustment
                return max(0.01, min(0.99, calibrated))

        return raw_probability  # Outside any bin
