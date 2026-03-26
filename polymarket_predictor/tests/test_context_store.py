"""Tests for the lightweight persistent context store."""

import json
import pytest
from pathlib import Path

from polymarket_predictor.knowledge.context_store import ContextStore, MarketContext


@pytest.fixture
def tmp_store(tmp_path):
    """Create a ContextStore backed by a temporary directory."""
    return ContextStore(data_dir=tmp_path)


def _make_ctx(
    market_id="mkt-1",
    question="Will BTC hit 100k?",
    category="crypto",
    market_odds=0.45,
    prediction=0.55,
    outcome="pending",
    was_correct=None,
    **kwargs,
):
    return MarketContext(
        market_id=market_id,
        question=question,
        category=category,
        market_odds_at_prediction=market_odds,
        our_prediction=prediction,
        outcome=outcome,
        was_correct=was_correct,
        **kwargs,
    )


class TestAddAndRetrieve:
    def test_add_and_retrieve(self, tmp_store):
        ctx = _make_ctx()
        tmp_store.add(ctx)

        records = tmp_store.get_by_category("crypto")
        assert len(records) == 1
        assert records[0]["market_id"] == "mkt-1"
        assert records[0]["question"] == "Will BTC hit 100k?"

    def test_retrieve_filters_by_category(self, tmp_store):
        tmp_store.add(_make_ctx(market_id="c1", category="crypto"))
        tmp_store.add(_make_ctx(market_id="p1", category="politics"))
        tmp_store.add(_make_ctx(market_id="c2", category="crypto"))

        crypto = tmp_store.get_by_category("crypto")
        assert len(crypto) == 2
        assert all(r["category"] == "crypto" for r in crypto)

        politics = tmp_store.get_by_category("politics")
        assert len(politics) == 1

    def test_limit_respected(self, tmp_store):
        for i in range(20):
            tmp_store.add(_make_ctx(market_id=f"mkt-{i}"))

        records = tmp_store.get_by_category("crypto", limit=5)
        assert len(records) == 5


class TestGetRelated:
    def test_get_related(self, tmp_store):
        tmp_store.add(_make_ctx(market_id="a", question="Will BTC hit 100k by December?"))
        tmp_store.add(_make_ctx(market_id="b", question="Will ETH reach 10k?"))
        tmp_store.add(_make_ctx(market_id="c", question="Will BTC hit 50k by June?"))
        tmp_store.add(_make_ctx(market_id="d", question="Will Democrats win Senate?"))

        related = tmp_store.get_related("Will BTC hit 80k?")
        # Should find the BTC-related ones (overlap on "Will", "BTC", "hit")
        assert len(related) >= 2
        ids = [r["market_id"] for r in related]
        assert "a" in ids
        assert "c" in ids

    def test_no_related_for_unrelated_question(self, tmp_store):
        tmp_store.add(_make_ctx(question="Will BTC hit 100k?"))

        related = tmp_store.get_related("Quantum computing breakthrough")
        assert len(related) == 0


class TestAccuracyByCategory:
    def test_accuracy_by_category(self, tmp_store):
        # 3 correct, 1 wrong in crypto
        for i in range(3):
            tmp_store.add(_make_ctx(
                market_id=f"c{i}", category="crypto",
                outcome="yes", was_correct=True,
            ))
        tmp_store.add(_make_ctx(
            market_id="c3", category="crypto",
            outcome="no", was_correct=False,
        ))
        # 1 correct in politics
        tmp_store.add(_make_ctx(
            market_id="p1", category="politics",
            outcome="yes", was_correct=True,
        ))
        # 1 pending in crypto
        tmp_store.add(_make_ctx(
            market_id="c4", category="crypto",
            outcome="pending", was_correct=None,
        ))

        accuracy = tmp_store.get_accuracy_by_category()

        assert accuracy["crypto"]["total"] == 4
        assert accuracy["crypto"]["correct"] == 3
        assert accuracy["crypto"]["accuracy"] == 0.75
        assert accuracy["crypto"]["pending"] == 1

        assert accuracy["politics"]["total"] == 1
        assert accuracy["politics"]["correct"] == 1
        assert accuracy["politics"]["accuracy"] == 1.0


class TestTrackRecord:
    def test_track_record_strong(self, tmp_store):
        # 4/5 correct
        for i in range(4):
            tmp_store.add(_make_ctx(
                market_id=f"c{i}", category="crypto",
                outcome="yes", was_correct=True,
            ))
        tmp_store.add(_make_ctx(
            market_id="c4", category="crypto",
            outcome="no", was_correct=False,
        ))

        summary = tmp_store.get_track_record_summary("crypto")
        assert "Strong track record" in summary
        assert "4/5" in summary

    def test_track_record_weak(self, tmp_store):
        # 1/5 correct
        tmp_store.add(_make_ctx(
            market_id="c0", category="crypto",
            outcome="yes", was_correct=True,
        ))
        for i in range(1, 5):
            tmp_store.add(_make_ctx(
                market_id=f"c{i}", category="crypto",
                outcome="no", was_correct=False,
            ))

        summary = tmp_store.get_track_record_summary("crypto")
        assert "Weak track record" in summary
        assert "1/5" in summary

    def test_track_record_limited(self, tmp_store):
        # Only 2 resolved predictions
        tmp_store.add(_make_ctx(
            market_id="c0", category="crypto",
            outcome="yes", was_correct=True,
        ))
        tmp_store.add(_make_ctx(
            market_id="c1", category="crypto",
            outcome="no", was_correct=False,
        ))

        summary = tmp_store.get_track_record_summary("crypto")
        assert "Limited track record" in summary

    def test_track_record_unknown_category(self, tmp_store):
        summary = tmp_store.get_track_record_summary("sports")
        assert "Limited track record" in summary
        assert "0 resolved" in summary


class TestEmptyStore:
    def test_empty_store(self, tmp_store):
        assert tmp_store.get_by_category("crypto") == []
        assert tmp_store.get_related("anything") == []
        assert tmp_store.get_accuracy_by_category() == {}
        assert "Limited" in tmp_store.get_track_record_summary("crypto")


class TestPersistence:
    def test_persistence(self, tmp_path):
        # Write with one instance
        store1 = ContextStore(data_dir=tmp_path)
        store1.add(_make_ctx(market_id="persist-1"))
        store1.add(_make_ctx(market_id="persist-2"))

        # Read with a fresh instance
        store2 = ContextStore(data_dir=tmp_path)
        records = store2.get_by_category("crypto")
        assert len(records) == 2
        assert records[0]["market_id"] == "persist-1"
        assert records[1]["market_id"] == "persist-2"

    def test_jsonl_format(self, tmp_path):
        store = ContextStore(data_dir=tmp_path)
        store.add(_make_ctx(market_id="fmt-1"))
        store.add(_make_ctx(market_id="fmt-2"))

        # Verify it's valid JSONL
        lines = (tmp_path / "context_store.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            parsed = json.loads(line)
            assert "market_id" in parsed
            assert "timestamp" in parsed
