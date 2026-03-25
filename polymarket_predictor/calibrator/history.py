import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from polymarket_predictor.config import DATA_DIR

logger = logging.getLogger(__name__)

PREDICTIONS_FILE = DATA_DIR / "predictions.jsonl"
RESOLUTIONS_FILE = DATA_DIR / "resolutions.jsonl"

@dataclass
class PredictionRecord:
    market_id: str
    question: str
    predicted_prob: float
    market_prob: float
    ensemble_std: float
    signal: str
    reliability: str
    num_variants: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

@dataclass
class ResolutionRecord:
    market_id: str
    question: str
    outcome: str          # "Yes" or "No"
    outcome_binary: int   # 1 for Yes, 0 for No
    resolved_at: str

class PredictionHistory:
    def log_prediction(self, record: PredictionRecord):
        """Append a prediction to the history file."""
        with open(PREDICTIONS_FILE, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")
        logger.info(f"Logged prediction for {record.market_id}: {record.predicted_prob:.2f}")

    def log_resolution(self, record: ResolutionRecord):
        """Append a resolution to the history file."""
        with open(RESOLUTIONS_FILE, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")
        logger.info(f"Logged resolution for {record.market_id}: {record.outcome}")

    def get_predictions(self) -> list[PredictionRecord]:
        """Load all predictions from history."""
        if not PREDICTIONS_FILE.exists():
            return []
        records = []
        for line in PREDICTIONS_FILE.read_text().strip().split("\n"):
            if line:
                data = json.loads(line)
                records.append(PredictionRecord(**data))
        return records

    def get_resolutions(self) -> list[ResolutionRecord]:
        """Load all resolutions from history."""
        if not RESOLUTIONS_FILE.exists():
            return []
        records = []
        for line in RESOLUTIONS_FILE.read_text().strip().split("\n"):
            if line:
                data = json.loads(line)
                records.append(ResolutionRecord(**data))
        return records

    def get_matched_records(self) -> list[tuple[PredictionRecord, ResolutionRecord]]:
        """Match predictions with their resolutions by market_id."""
        predictions = {r.market_id: r for r in self.get_predictions()}
        resolutions = {r.market_id: r for r in self.get_resolutions()}
        matched = []
        for market_id in predictions:
            if market_id in resolutions:
                matched.append((predictions[market_id], resolutions[market_id]))
        return matched
