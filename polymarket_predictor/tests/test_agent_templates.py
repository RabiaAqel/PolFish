"""Tests for template agent archetypes."""

from polymarket_predictor.agents.templates import (
    MARKET_PARTICIPANT_TEMPLATES,
    get_templates,
    get_stance_summary,
)

REQUIRED_FIELDS = {"name", "type", "stance", "sentiment_bias", "influence_weight", "activity_level", "bio"}


def test_get_templates_returns_list():
    templates = get_templates()
    assert isinstance(templates, list)
    assert len(templates) > 0


def test_get_templates_max_cap():
    for cap in (5, 10, 15, 100):
        result = get_templates(max_agents=cap)
        assert len(result) <= cap
        assert len(result) == min(cap, len(MARKET_PARTICIPANT_TEMPLATES))


def test_all_templates_have_required_fields():
    for tmpl in MARKET_PARTICIPANT_TEMPLATES:
        missing = REQUIRED_FIELDS - set(tmpl.keys())
        assert not missing, f"Template '{tmpl.get('name', '?')}' missing fields: {missing}"


def test_stance_distribution():
    """Ensure a healthy mix of bullish, bearish, and neutral agents."""
    templates = get_templates()
    stances = {t["stance"] for t in templates}
    assert "bullish" in stances, "No bullish agents found"
    assert "bearish" in stances, "No bearish agents found"
    assert "neutral" in stances, "No neutral agents found"

    summary = get_stance_summary(templates)
    assert summary["bullish"] >= 2, "Too few bullish agents"
    assert summary["bearish"] >= 2, "Too few bearish agents"
    assert summary["neutral"] >= 5, "Too few neutral agents"


def test_stance_summary():
    templates = get_templates()
    summary = get_stance_summary(templates)

    assert summary["total"] == len(templates)
    assert summary["bullish"] + summary["bearish"] + summary["neutral"] == summary["total"]

    # Manual recount
    bullish = sum(1 for t in templates if t["stance"] == "bullish")
    bearish = sum(1 for t in templates if t["stance"] == "bearish")
    neutral = sum(1 for t in templates if t["stance"] == "neutral")
    assert summary["bullish"] == bullish
    assert summary["bearish"] == bearish
    assert summary["neutral"] == neutral


def test_unique_names():
    names = [t["name"] for t in MARKET_PARTICIPANT_TEMPLATES]
    assert len(names) == len(set(names)), f"Duplicate names found: {[n for n in names if names.count(n) > 1]}"


def test_influence_range():
    for tmpl in MARKET_PARTICIPANT_TEMPLATES:
        w = tmpl["influence_weight"]
        assert 0.1 <= w <= 3.5, (
            f"Agent '{tmpl['name']}' influence_weight {w} outside [0.1, 3.5]"
        )


def test_activity_range():
    for tmpl in MARKET_PARTICIPANT_TEMPLATES:
        a = tmpl["activity_level"]
        assert 0.05 <= a <= 1.0, (
            f"Agent '{tmpl['name']}' activity_level {a} outside [0.05, 1.0]"
        )


def test_devils_advocate_agents_exist():
    """Should have Devil's Advocate agents in templates."""
    templates = get_templates(max_agents=50)
    devils = [t for t in templates if t["type"] == "DevilsAdvocate"]
    assert len(devils) >= 2, "Need at least 2 Devil's Advocate agents"


def test_devils_advocate_high_influence():
    """Devil's Advocates should have high influence to be heard."""
    templates = get_templates(max_agents=50)
    devils = [t for t in templates if t["type"] == "DevilsAdvocate"]
    for d in devils:
        assert d["influence_weight"] >= 1.5, f"{d['name']} influence too low"


def test_devils_advocate_high_activity():
    """Devil's Advocates should be active participants."""
    templates = get_templates(max_agents=50)
    devils = [t for t in templates if t["type"] == "DevilsAdvocate"]
    for d in devils:
        assert d["activity_level"] >= 0.5, f"{d['name']} activity too low"
