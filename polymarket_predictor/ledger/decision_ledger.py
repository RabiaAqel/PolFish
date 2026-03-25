"""Append-only decision ledger for tracking all system decisions.

Every decision that affects the optimizer, portfolio, or predictions is logged
here as a JSONL file — one JSON object per line, grep-friendly.
"""

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from polymarket_predictor.config import DATA_DIR

logger = logging.getLogger(__name__)

# Valid entry types
ENTRY_TYPES = frozenset(
    {
        "BET_PLACED",
        "BET_SKIPPED",
        "BET_RESOLVED",
        "DEEP_CONFIRMED",
        "DEEP_REJECTED",
        "PARAM_CHANGED",
        "CALIBRATION_UPDATE",
        "CYCLE_SUMMARY",
    }
)


@dataclass
class LedgerEntry:
    """A single decision record in the ledger."""

    id: str  # UUID
    timestamp: str  # ISO 8601
    entry_type: str  # One of ENTRY_TYPES
    market_id: str  # Market slug or "" for system events
    question: str  # Market question or "" for system events
    data: dict  # Type-specific structured data
    explanation: str  # Human-readable explanation of WHY this decision was made
    cycle_id: str  # Which autopilot cycle this belongs to, or "manual"

    def to_dict(self) -> dict:
        """Serialize to a plain dict suitable for JSON encoding."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "LedgerEntry":
        """Deserialize from a dict (e.g. parsed from JSON)."""
        return cls(
            id=d["id"],
            timestamp=d["timestamp"],
            entry_type=d["entry_type"],
            market_id=d.get("market_id", ""),
            question=d.get("question", ""),
            data=d.get("data", {}),
            explanation=d.get("explanation", ""),
            cycle_id=d.get("cycle_id", "manual"),
        )


class DecisionLedger:
    """Append-only JSONL log of every decision the system makes.

    The file is stored at ``{data_dir}/decision_ledger.jsonl`` and is designed
    to be both machine-readable (one JSON object per line) and human-readable
    (fields are written in a consistent order for easy grepping).

    Usage::

        ledger = DecisionLedger()
        ledger.log(
            entry_type="BET_PLACED",
            market_id="will-trump-win-2024",
            question="Will Trump win the 2024 election?",
            data={"side": "YES", "amount": 10.0, "odds": 0.55, ...},
            explanation="Edge of 12% exceeds threshold; Kelly suggests 3.2% allocation.",
            cycle_id="cycle-abc123",
        )
    """

    def __init__(self, data_dir: Optional[Union[str, Path]] = None):
        self._data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._filepath = self._data_dir / "decision_ledger.jsonl"

    @property
    def filepath(self) -> Path:
        """Path to the underlying JSONL file."""
        return self._filepath

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def log(
        self,
        entry_type: str,
        market_id: str = "",
        question: str = "",
        data: Optional[dict] = None,
        explanation: str = "",
        cycle_id: str = "manual",
    ) -> LedgerEntry:
        """Create an entry, append it to the JSONL file, and return it.

        Args:
            entry_type: One of the recognised ``ENTRY_TYPES``.
            market_id: Market slug, or ``""`` for system-level events.
            question: Human-readable market question, or ``""``.
            data: Type-specific structured payload.
            explanation: Plain-English reason *why* this decision was made.
            cycle_id: Identifier for the autopilot cycle, or ``"manual"``.

        Returns:
            The newly created ``LedgerEntry``.

        Raises:
            ValueError: If *entry_type* is not recognised.
        """
        if entry_type not in ENTRY_TYPES:
            raise ValueError(
                f"Unknown entry_type {entry_type!r}. "
                f"Must be one of: {', '.join(sorted(ENTRY_TYPES))}"
            )

        entry = LedgerEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            entry_type=entry_type,
            market_id=market_id,
            question=question,
            data=data or {},
            explanation=explanation,
            cycle_id=cycle_id,
        )

        self._append(entry)
        logger.info(
            "Ledger %s | %s | %s",
            entry.entry_type,
            entry.market_id or "(system)",
            entry.explanation[:120],
        )
        return entry

    def _append(self, entry: LedgerEntry) -> None:
        """Append a single entry as one JSON line."""
        line = json.dumps(entry.to_dict(), separators=(", ", ": "), ensure_ascii=False)
        with open(self._filepath, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def _read_all(self) -> List[LedgerEntry]:
        """Read every entry from disk. Returns newest-first order."""
        if not self._filepath.exists():
            return []

        entries: List[LedgerEntry] = []
        with open(self._filepath, "r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(LedgerEntry.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning(
                        "Skipping malformed ledger line %d: %s", line_no, exc
                    )
        entries.reverse()  # most recent first
        return entries

    def get_entries(
        self,
        entry_type: Optional[str] = None,
        market_id: Optional[str] = None,
        cycle_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[LedgerEntry]:
        """Read and filter entries. Most recent first.

        Args:
            entry_type: Filter to this type only.
            market_id: Filter to this market slug only.
            cycle_id: Filter to this cycle only.
            limit: Maximum number of entries to return.
            offset: Number of matching entries to skip before collecting.

        Returns:
            List of matching ``LedgerEntry`` objects, newest first.
        """
        entries = self._read_all()

        if entry_type is not None:
            entries = [e for e in entries if e.entry_type == entry_type]
        if market_id is not None:
            entries = [e for e in entries if e.market_id == market_id]
        if cycle_id is not None:
            entries = [e for e in entries if e.cycle_id == cycle_id]

        return entries[offset : offset + limit]

    def get_cycle_entries(self, cycle_id: str) -> List[LedgerEntry]:
        """Return all entries belonging to a specific autopilot cycle."""
        return [e for e in self._read_all() if e.cycle_id == cycle_id]

    def get_stats(self) -> dict:
        """Return a summary of the ledger contents.

        Returns:
            A dict with keys: ``total_entries``, ``entries_by_type``,
            ``last_cycle_id``, ``last_entry_timestamp``, ``total_cycles``.
        """
        entries = self._read_all()  # newest first

        entries_by_type = {}  # type: dict
        cycle_ids = set()  # type: set

        for entry in entries:
            entries_by_type[entry.entry_type] = (
                entries_by_type.get(entry.entry_type, 0) + 1
            )
            if entry.cycle_id != "manual":
                cycle_ids.add(entry.cycle_id)

        return {
            "total_entries": len(entries),
            "entries_by_type": entries_by_type,
            "last_cycle_id": entries[0].cycle_id if entries else None,
            "last_entry_timestamp": entries[0].timestamp if entries else None,
            "total_cycles": len(cycle_ids),
        }

    def search(self, query: str, limit: int = 50) -> List[LedgerEntry]:
        """Simple case-insensitive text search across question and explanation.

        Args:
            query: Search string (matched case-insensitively).
            limit: Maximum results to return.

        Returns:
            Matching entries, newest first.
        """
        q = query.lower()
        results: List[LedgerEntry] = []
        for entry in self._read_all():
            if q in entry.question.lower() or q in entry.explanation.lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def get_recent(self, limit: int = 20) -> List[LedgerEntry]:
        """Return the most recent *limit* entries across all types."""
        return self._read_all()[:limit]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Delete the JSONL file entirely. Use for hard resets only."""
        if self._filepath.exists():
            self._filepath.unlink()
            logger.info("Decision ledger cleared: %s", self._filepath)
