"""Tests for polymarket_predictor.ledger.decision_ledger."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polymarket_predictor.ledger.decision_ledger import (
    ENTRY_TYPES,
    DecisionLedger,
    LedgerEntry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ledger(tmp_path: Path) -> DecisionLedger:
    """Return a DecisionLedger backed by a temporary directory."""
    return DecisionLedger(data_dir=tmp_path)


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------


class TestLogValidEntry:
    """log writes to JSONL and the entry is readable back."""

    def test_log_and_read(self, ledger: DecisionLedger):
        entry = ledger.log(
            entry_type="BET_PLACED",
            market_id="btc-above-70k",
            question="Will BTC be above 70k?",
            data={"side": "YES", "amount": 10.0},
            explanation="Edge of 12% exceeds threshold.",
            cycle_id="cycle-001",
        )

        assert entry.entry_type == "BET_PLACED"
        assert entry.market_id == "btc-above-70k"

        # Readable back
        entries = ledger.get_entries()
        assert len(entries) == 1
        assert entries[0].id == entry.id


class TestLogInvalidEntryType:
    """log raises ValueError for unrecognised entry types."""

    def test_raises(self, ledger: DecisionLedger):
        with pytest.raises(ValueError, match="Unknown entry_type"):
            ledger.log(entry_type="INVALID_TYPE")


class TestLogAllValidTypes:
    """All 8 recognised entry types can be logged without error."""

    @pytest.mark.parametrize("entry_type", sorted(ENTRY_TYPES))
    def test_log_valid_type(self, ledger: DecisionLedger, entry_type: str):
        entry = ledger.log(entry_type=entry_type)
        assert entry.entry_type == entry_type


# ---------------------------------------------------------------------------
# get_entries
# ---------------------------------------------------------------------------


class TestGetEntriesNoFilter:
    """get_entries with no filter returns all entries newest-first."""

    def test_all_returned_newest_first(self, ledger: DecisionLedger):
        e1 = ledger.log(entry_type="BET_PLACED", market_id="m1")
        e2 = ledger.log(entry_type="BET_SKIPPED", market_id="m2")
        e3 = ledger.log(entry_type="BET_RESOLVED", market_id="m3")

        entries = ledger.get_entries()
        assert len(entries) == 3
        # newest first
        assert entries[0].id == e3.id
        assert entries[2].id == e1.id


class TestGetEntriesByType:
    """get_entries filters by entry_type."""

    def test_filter_by_type(self, ledger: DecisionLedger):
        ledger.log(entry_type="BET_PLACED", market_id="m1")
        ledger.log(entry_type="BET_SKIPPED", market_id="m2")
        ledger.log(entry_type="BET_PLACED", market_id="m3")

        entries = ledger.get_entries(entry_type="BET_PLACED")
        assert len(entries) == 2
        assert all(e.entry_type == "BET_PLACED" for e in entries)


class TestGetEntriesByMarketId:
    """get_entries filters by market_id."""

    def test_filter_by_market(self, ledger: DecisionLedger):
        ledger.log(entry_type="BET_PLACED", market_id="m1")
        ledger.log(entry_type="BET_PLACED", market_id="m2")
        ledger.log(entry_type="BET_SKIPPED", market_id="m1")

        entries = ledger.get_entries(market_id="m1")
        assert len(entries) == 2
        assert all(e.market_id == "m1" for e in entries)


class TestGetEntriesByCycleId:
    """get_entries filters by cycle_id."""

    def test_filter_by_cycle(self, ledger: DecisionLedger):
        ledger.log(entry_type="BET_PLACED", cycle_id="c1")
        ledger.log(entry_type="BET_PLACED", cycle_id="c2")
        ledger.log(entry_type="BET_SKIPPED", cycle_id="c1")

        entries = ledger.get_entries(cycle_id="c1")
        assert len(entries) == 2
        assert all(e.cycle_id == "c1" for e in entries)


class TestGetEntriesLimitOffset:
    """get_entries pagination with limit and offset."""

    def test_pagination(self, ledger: DecisionLedger):
        for i in range(10):
            ledger.log(entry_type="BET_PLACED", market_id=f"m{i}")

        page1 = ledger.get_entries(limit=3, offset=0)
        page2 = ledger.get_entries(limit=3, offset=3)

        assert len(page1) == 3
        assert len(page2) == 3
        # Pages should not overlap
        ids1 = {e.id for e in page1}
        ids2 = {e.id for e in page2}
        assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# get_cycle_entries
# ---------------------------------------------------------------------------


class TestGetCycleEntries:
    """get_cycle_entries returns all entries for a specific cycle."""

    def test_returns_cycle_entries(self, ledger: DecisionLedger):
        ledger.log(entry_type="BET_PLACED", cycle_id="c1")
        ledger.log(entry_type="BET_PLACED", cycle_id="c2")
        ledger.log(entry_type="BET_RESOLVED", cycle_id="c1")

        entries = ledger.get_cycle_entries("c1")
        assert len(entries) == 2
        assert all(e.cycle_id == "c1" for e in entries)


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    """get_stats returns correct counts by type and total cycles."""

    def test_correct_stats(self, ledger: DecisionLedger):
        ledger.log(entry_type="BET_PLACED", cycle_id="c1")
        ledger.log(entry_type="BET_PLACED", cycle_id="c1")
        ledger.log(entry_type="BET_SKIPPED", cycle_id="c2")
        ledger.log(entry_type="CYCLE_SUMMARY", cycle_id="c2")

        stats = ledger.get_stats()
        assert stats["total_entries"] == 4
        assert stats["entries_by_type"]["BET_PLACED"] == 2
        assert stats["entries_by_type"]["BET_SKIPPED"] == 1
        assert stats["entries_by_type"]["CYCLE_SUMMARY"] == 1
        assert stats["total_cycles"] == 2


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    """search performs case-insensitive text match in question + explanation."""

    def test_case_insensitive_match(self, ledger: DecisionLedger):
        ledger.log(
            entry_type="BET_PLACED",
            question="Will Bitcoin rise?",
            explanation="Market looks bullish.",
        )
        ledger.log(
            entry_type="BET_PLACED",
            question="Will ETH fall?",
            explanation="Bearish signal detected.",
        )

        results = ledger.search("bitcoin")
        assert len(results) == 1
        assert "Bitcoin" in results[0].question

    def test_search_in_explanation(self, ledger: DecisionLedger):
        ledger.log(
            entry_type="BET_PLACED",
            question="Generic question",
            explanation="Strong BULLISH momentum detected.",
        )

        results = ledger.search("bullish")
        assert len(results) == 1


class TestSearchNoResults:
    """search returns empty list when no matches."""

    def test_no_results(self, ledger: DecisionLedger):
        ledger.log(entry_type="BET_PLACED", question="Will it rain?")
        results = ledger.search("bitcoin")
        assert results == []


# ---------------------------------------------------------------------------
# get_recent
# ---------------------------------------------------------------------------


class TestGetRecent:
    """get_recent returns last N entries."""

    def test_returns_recent(self, ledger: DecisionLedger):
        for i in range(10):
            ledger.log(entry_type="BET_PLACED", market_id=f"m{i}")

        recent = ledger.get_recent(limit=3)
        assert len(recent) == 3
        # newest first
        assert recent[0].market_id == "m9"


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestClear:
    """clear deletes the file; subsequent reads return empty results."""

    def test_clear_and_read(self, ledger: DecisionLedger):
        ledger.log(entry_type="BET_PLACED")
        assert len(ledger.get_entries()) == 1

        ledger.clear()

        assert len(ledger.get_entries()) == 0
        assert not ledger.filepath.exists()


# ---------------------------------------------------------------------------
# Malformed JSONL
# ---------------------------------------------------------------------------


class TestMalformedJSONL:
    """Malformed lines are skipped with warning; others still readable."""

    def test_skips_bad_lines(self, ledger: DecisionLedger):
        # Write a valid entry then a corrupt line
        ledger.log(entry_type="BET_PLACED", market_id="good")

        with open(ledger.filepath, "a", encoding="utf-8") as f:
            f.write("THIS IS NOT JSON\n")

        ledger.log(entry_type="BET_SKIPPED", market_id="also-good")

        entries = ledger.get_entries()
        assert len(entries) == 2
        market_ids = {e.market_id for e in entries}
        assert "good" in market_ids
        assert "also-good" in market_ids


# ---------------------------------------------------------------------------
# Empty file
# ---------------------------------------------------------------------------


class TestEmptyFile:
    """All methods return empty results when file does not exist."""

    def test_empty_entries(self, ledger: DecisionLedger):
        assert ledger.get_entries() == []

    def test_empty_stats(self, ledger: DecisionLedger):
        stats = ledger.get_stats()
        assert stats["total_entries"] == 0

    def test_empty_search(self, ledger: DecisionLedger):
        assert ledger.search("anything") == []

    def test_empty_recent(self, ledger: DecisionLedger):
        assert ledger.get_recent() == []

    def test_empty_cycle(self, ledger: DecisionLedger):
        assert ledger.get_cycle_entries("c1") == []


# ---------------------------------------------------------------------------
# LedgerEntry serialisation roundtrip
# ---------------------------------------------------------------------------


class TestLedgerEntrySerialization:
    """to_dict / from_dict roundtrip preserves all fields."""

    def test_roundtrip(self):
        entry = LedgerEntry(
            id="abc-123",
            timestamp="2024-01-01T00:00:00+00:00",
            entry_type="BET_PLACED",
            market_id="btc-slug",
            question="Will BTC moon?",
            data={"side": "YES", "amount": 42.0},
            explanation="Because reasons.",
            cycle_id="cycle-xyz",
        )

        d = entry.to_dict()
        restored = LedgerEntry.from_dict(d)

        assert restored.id == entry.id
        assert restored.timestamp == entry.timestamp
        assert restored.entry_type == entry.entry_type
        assert restored.market_id == entry.market_id
        assert restored.question == entry.question
        assert restored.data == entry.data
        assert restored.explanation == entry.explanation
        assert restored.cycle_id == entry.cycle_id
