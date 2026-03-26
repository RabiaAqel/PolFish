"""Tests for _assign_agent_diversity in simulation_config_generator."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pytest


# We need to create lightweight stand-in AgentActivityConfig since importing
# the real one would pull in heavy Flask/backend dependencies. Instead, we
# import the real class and method directly.

# Add backend to path so we can import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "MiroFish" / "backend"))

from app.services.simulation_config_generator import (
    AgentActivityConfig,
    SimulationConfigGenerator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agents(n: int) -> List[AgentActivityConfig]:
    """Create n default AgentActivityConfig objects."""
    return [
        AgentActivityConfig(
            agent_id=i,
            entity_uuid=f"uuid-{i}",
            entity_name=f"agent_{i}",
            entity_type="Citizen",
        )
        for i in range(n)
    ]


def _apply_diversity(agents: List[AgentActivityConfig]) -> List[AgentActivityConfig]:
    """Apply diversity using the real method."""
    gen = SimulationConfigGenerator.__new__(SimulationConfigGenerator)
    return gen._assign_agent_diversity(agents)


# ---------------------------------------------------------------------------
# Stance distribution
# ---------------------------------------------------------------------------


class TestStanceDistribution:

    def test_diversity_stance_distribution_10_agents(self):
        """10 agents -> 3 bullish, 3 bearish, 4 neutral."""
        agents = _apply_diversity(_make_agents(10))
        stances = [a.stance for a in agents]
        assert stances.count("bullish") == 3, f"Expected 3 bullish, got {stances.count('bullish')}"
        assert stances.count("bearish") == 3, f"Expected 3 bearish, got {stances.count('bearish')}"
        assert stances.count("neutral") == 4, f"Expected 4 neutral, got {stances.count('neutral')}"

    def test_diversity_stance_distribution_20_agents(self):
        """20 agents -> 6 bullish, 6 bearish, 8 neutral."""
        agents = _apply_diversity(_make_agents(20))
        stances = [a.stance for a in agents]
        assert stances.count("bullish") == 6, f"Expected 6 bullish, got {stances.count('bullish')}"
        assert stances.count("bearish") == 6, f"Expected 6 bearish, got {stances.count('bearish')}"
        assert stances.count("neutral") == 8, f"Expected 8 neutral, got {stances.count('neutral')}"

    def test_diversity_stance_distribution_1_agent(self):
        """1 agent doesn't crash."""
        agents = _apply_diversity(_make_agents(1))
        assert len(agents) == 1
        assert agents[0].stance in ("bullish", "bearish", "neutral")

    def test_diversity_stance_distribution_0_agents(self):
        """0 agents doesn't crash."""
        agents = _apply_diversity(_make_agents(0))
        assert len(agents) == 0


# ---------------------------------------------------------------------------
# Influence weight
# ---------------------------------------------------------------------------


class TestInfluenceWeight:

    def test_diversity_influence_range(self):
        """All weights between 0.5 and 3.0."""
        agents = _apply_diversity(_make_agents(20))
        for a in agents:
            assert 0.5 <= a.influence_weight <= 3.0, (
                f"Agent {a.agent_id} influence_weight={a.influence_weight} "
                f"out of [0.5, 3.0]"
            )

    def test_diversity_influence_varies(self):
        """Not all agents have the same influence weight."""
        agents = _apply_diversity(_make_agents(10))
        weights = set(a.influence_weight for a in agents)
        assert len(weights) > 1, "All agents have identical influence weights"


# ---------------------------------------------------------------------------
# Sentiment bias
# ---------------------------------------------------------------------------


class TestSentimentBias:

    def test_diversity_sentiment_bias_matches_stance(self):
        """Bullish=positive bias, bearish=negative."""
        agents = _apply_diversity(_make_agents(20))
        for a in agents:
            if a.stance == "bullish":
                assert a.sentiment_bias > 0, (
                    f"Bullish agent {a.agent_id} has non-positive sentiment_bias={a.sentiment_bias}"
                )
            elif a.stance == "bearish":
                assert a.sentiment_bias < 0, (
                    f"Bearish agent {a.agent_id} has non-negative sentiment_bias={a.sentiment_bias}"
                )


# ---------------------------------------------------------------------------
# Activity variation
# ---------------------------------------------------------------------------


class TestActivityVariation:

    def test_diversity_activity_variation(self):
        """Not all agents have the same activity level."""
        agents = _apply_diversity(_make_agents(15))
        levels = set(a.activity_level for a in agents)
        assert len(levels) > 1, "All agents have identical activity levels"

    def test_diversity_posting_rates_vary(self):
        """Posts per hour should vary across agents."""
        agents = _apply_diversity(_make_agents(15))
        rates = set(a.posts_per_hour for a in agents)
        assert len(rates) > 1, "All agents have identical posts_per_hour"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:

    def test_diversity_deterministic(self):
        """Same input -> same output twice."""
        agents1 = _apply_diversity(_make_agents(10))
        agents2 = _apply_diversity(_make_agents(10))

        for a1, a2 in zip(agents1, agents2):
            assert a1.stance == a2.stance
            assert a1.influence_weight == a2.influence_weight
            assert a1.sentiment_bias == a2.sentiment_bias
            assert a1.activity_level == a2.activity_level
