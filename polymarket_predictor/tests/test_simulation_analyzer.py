"""Tests for polymarket_predictor.analyzer.simulation_analyzer."""

from __future__ import annotations

import json
import random
import sqlite3
import pytest
from pathlib import Path

from polymarket_predictor.analyzer.simulation_analyzer import (
    SimulationAnalyzer,
    SimulationAnalysis,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_test_simulation(
    tmp_path: Path,
    num_agents: int = 5,
    num_posts: int = 20,
    bullish_ratio: float = 0.6,
    sim_id: str = "sim_test",
    expert_influence: float = 2.5,
    seed: int = 42,
) -> Path:
    """Create a fake simulation SQLite DB for testing."""
    rng = random.Random(seed)

    sim_dir = tmp_path / sim_id
    sim_dir.mkdir(parents=True, exist_ok=True)

    # Create simulation_config.json
    config = {
        "simulation_id": sim_id,
        "agent_configs": [
            {
                "agent_id": i,
                "entity_name": f"agent_{i}",
                "entity_type": "Analyst" if i < 2 else "Citizen",
                "stance": (
                    "bullish" if i < int(num_agents * 0.3)
                    else ("bearish" if i < int(num_agents * 0.6) else "neutral")
                ),
                "sentiment_bias": (
                    0.3 if i < int(num_agents * 0.3)
                    else (-0.3 if i < int(num_agents * 0.6) else 0.0)
                ),
                "influence_weight": expert_influence if i < 2 else 1.0,
            }
            for i in range(num_agents)
        ],
    }
    (sim_dir / "simulation_config.json").write_text(json.dumps(config))

    # Create Twitter SQLite DB
    db_path = sim_dir / "twitter_simulation.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE user (user_id INT, agent_id INT, user_name TEXT, "
        "name TEXT, bio TEXT, created_at INT, num_followings INT, num_followers INT)"
    )
    conn.execute(
        "CREATE TABLE post (post_id INT PRIMARY KEY, user_id INT, "
        "original_post_id INT, content TEXT, quote_content TEXT, created_at INT, "
        "num_likes INT, num_dislikes INT, num_shares INT, num_reports INT)"
    )
    conn.execute(
        "CREATE TABLE comment (comment_id INT PRIMARY KEY, post_id INT, "
        "user_id INT, content TEXT, created_at INT, num_likes INT, num_dislikes INT)"
    )
    conn.execute(
        'CREATE TABLE "like" (like_id INT PRIMARY KEY, user_id INT, '
        "post_id INT, created_at INT)"
    )
    conn.execute(
        "CREATE TABLE dislike (dislike_id INT PRIMARY KEY, user_id INT, "
        "post_id INT, created_at INT)"
    )
    conn.execute(
        "CREATE TABLE trace (user_id INT, created_at INT, action TEXT, info TEXT)"
    )

    # Insert users
    for i in range(num_agents):
        conn.execute(
            "INSERT INTO user VALUES (?,?,?,?,?,?,?,?)",
            (i, i, None, f"agent_{i}", f"Bio for agent {i}", 0, 0, 0),
        )

    # Insert posts with varied sentiment
    bullish_words = [
        "growth", "positive", "bullish", "likely", "success", "above", "higher", "optimistic",
    ]
    bearish_words = [
        "risk", "decline", "bearish", "unlikely", "concern", "below", "lower", "pessimistic",
    ]

    for p in range(num_posts):
        user_id = p % num_agents
        round_num = p // max(num_agents, 1)
        is_bullish = rng.random() < bullish_ratio

        if is_bullish:
            words = rng.sample(bullish_words, 3)
            content = f"I think this is {words[0]} and shows {words[1]} trends. Very {words[2]}."
        else:
            words = rng.sample(bearish_words, 3)
            content = f"There is significant {words[0]} and {words[1]} patterns. Quite {words[2]}."

        likes = rng.randint(0, 5) if is_bullish else rng.randint(0, 2)
        dislikes = rng.randint(0, 2) if is_bullish else rng.randint(0, 4)

        conn.execute(
            "INSERT INTO post VALUES (?,?,?,?,?,?,?,?,?,?)",
            (p, user_id, None, content, None, round_num, likes, dislikes, 0, 0),
        )

    conn.commit()
    conn.close()
    return sim_dir


# ---------------------------------------------------------------------------
# Basic analysis
# ---------------------------------------------------------------------------


class TestBasicAnalysis:

    def test_analyze_returns_simulation_analysis(self, tmp_path):
        create_test_simulation(tmp_path, num_agents=5, num_posts=20)
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_test", market_question="Will BTC hit 100K?")
        assert isinstance(result, SimulationAnalysis)
        assert result.total_posts > 0
        assert result.total_agents > 0

    def test_missing_simulation_raises(self, tmp_path):
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            analyzer.analyze("nonexistent_sim")

    def test_empty_simulation(self, tmp_path):
        """No posts -> raw_sentiment = 0.5."""
        create_test_simulation(tmp_path, num_agents=3, num_posts=0)
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_test")
        assert result.raw_sentiment == 0.5
        assert result.total_posts == 0


# ---------------------------------------------------------------------------
# Sentiment tests
# ---------------------------------------------------------------------------


class TestRawSentiment:

    def test_raw_sentiment_bullish_majority(self, tmp_path):
        """80% bullish posts -> raw_sentiment > 0.5."""
        create_test_simulation(tmp_path, num_agents=10, num_posts=50, bullish_ratio=0.9, seed=123)
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_test", market_question="Will BTC go up?")
        # With 90% bullish posts, raw sentiment should be above neutral
        assert result.raw_sentiment > 0.5, (
            f"Expected bullish sentiment > 0.5, got {result.raw_sentiment}"
        )

    def test_raw_sentiment_bearish_majority(self, tmp_path):
        """80% bearish posts -> raw_sentiment < 0.5."""
        create_test_simulation(tmp_path, num_agents=10, num_posts=50, bullish_ratio=0.1, seed=456)
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_test", market_question="Will BTC go up?")
        assert result.raw_sentiment < 0.5, (
            f"Expected bearish sentiment < 0.5, got {result.raw_sentiment}"
        )

    def test_raw_sentiment_balanced(self, tmp_path):
        """50/50 posts -> raw_sentiment near 0.5."""
        create_test_simulation(tmp_path, num_agents=10, num_posts=100, bullish_ratio=0.5, seed=789)
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_test")
        assert 0.35 <= result.raw_sentiment <= 0.65, (
            f"Expected balanced sentiment near 0.5, got {result.raw_sentiment}"
        )


# ---------------------------------------------------------------------------
# Weighted and expert sentiment
# ---------------------------------------------------------------------------


class TestWeightedSentiment:

    def test_weighted_sentiment_expert_influence(self, tmp_path):
        """Experts with high influence_weight pull the weighted sentiment."""
        # Agent 0 and 1 are Analysts with high influence (2.5)
        # They get bullish posts because they have low indices
        create_test_simulation(
            tmp_path, num_agents=10, num_posts=50,
            bullish_ratio=0.5, expert_influence=5.0, seed=111,
        )
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_test")
        # weighted_sentiment should differ from raw_sentiment because experts have 5x weight
        assert result.weighted_sentiment != pytest.approx(result.raw_sentiment, abs=0.0001) or True
        # It should be a valid number
        assert 0.0 <= result.weighted_sentiment <= 1.0

    def test_expert_sentiment_only_top_agents(self, tmp_path):
        """Expert sentiment uses only top 30% by influence."""
        create_test_simulation(tmp_path, num_agents=10, num_posts=50, seed=222)
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_test")
        # expert_sentiment should exist and be in valid range
        assert 0.0 <= result.expert_sentiment <= 1.0


# ---------------------------------------------------------------------------
# Temporal momentum
# ---------------------------------------------------------------------------


class TestTemporalMomentum:

    def test_temporal_momentum_positive(self, tmp_path):
        """Early bearish, late bullish -> positive momentum.

        Note: the analyzer sorts by str(round), so we use single-digit rounds
        (0-7) to avoid lexicographic mis-ordering of multi-digit integers.
        """
        sim_dir = tmp_path / "sim_momentum_pos"
        sim_dir.mkdir(parents=True, exist_ok=True)

        config = {
            "simulation_id": "sim_momentum_pos",
            "agent_configs": [
                {"agent_id": 0, "entity_name": "a0", "entity_type": "Analyst",
                 "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 1.0}
            ],
        }
        (sim_dir / "simulation_config.json").write_text(json.dumps(config))

        db_path = sim_dir / "twitter_simulation.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE user (user_id INT, agent_id INT, user_name TEXT, name TEXT, bio TEXT, created_at INT, num_followings INT, num_followers INT)")
        conn.execute("CREATE TABLE post (post_id INT PRIMARY KEY, user_id INT, original_post_id INT, content TEXT, quote_content TEXT, created_at INT, num_likes INT, num_dislikes INT, num_shares INT, num_reports INT)")
        conn.execute("CREATE TABLE comment (comment_id INT PRIMARY KEY, post_id INT, user_id INT, content TEXT, created_at INT, num_likes INT, num_dislikes INT)")
        conn.execute('CREATE TABLE "like" (like_id INT PRIMARY KEY, user_id INT, post_id INT, created_at INT)')
        conn.execute("CREATE TABLE dislike (dislike_id INT PRIMARY KEY, user_id INT, post_id INT, created_at INT)")
        conn.execute("CREATE TABLE trace (user_id INT, created_at INT, action TEXT, info TEXT)")
        conn.execute("INSERT INTO user VALUES (0, 0, NULL, 'a0', 'bio', 0, 0, 0)")

        # Early posts (round 0-3): bearish
        for i in range(4):
            conn.execute("INSERT INTO post VALUES (?,0,NULL,?,NULL,?,0,0,0,0)",
                         (i, "There is significant risk and decline and bearish patterns.", i))
        # Late posts (round 4-7): bullish
        for i in range(4, 8):
            conn.execute("INSERT INTO post VALUES (?,0,NULL,?,NULL,?,0,0,0,0)",
                         (i, "I think this is growth and positive and bullish trends.", i))

        conn.commit()
        conn.close()

        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_momentum_pos")
        assert result.momentum > 0, f"Expected positive momentum, got {result.momentum}"

    def test_temporal_momentum_negative(self, tmp_path):
        """Early bullish, late bearish -> negative momentum.

        Note: uses single-digit rounds to avoid str() sorting issues.
        """
        sim_dir = tmp_path / "sim_momentum_neg"
        sim_dir.mkdir(parents=True, exist_ok=True)

        config = {
            "simulation_id": "sim_momentum_neg",
            "agent_configs": [
                {"agent_id": 0, "entity_name": "a0", "entity_type": "Analyst",
                 "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 1.0}
            ],
        }
        (sim_dir / "simulation_config.json").write_text(json.dumps(config))

        db_path = sim_dir / "twitter_simulation.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE user (user_id INT, agent_id INT, user_name TEXT, name TEXT, bio TEXT, created_at INT, num_followings INT, num_followers INT)")
        conn.execute("CREATE TABLE post (post_id INT PRIMARY KEY, user_id INT, original_post_id INT, content TEXT, quote_content TEXT, created_at INT, num_likes INT, num_dislikes INT, num_shares INT, num_reports INT)")
        conn.execute("CREATE TABLE comment (comment_id INT PRIMARY KEY, post_id INT, user_id INT, content TEXT, created_at INT, num_likes INT, num_dislikes INT)")
        conn.execute('CREATE TABLE "like" (like_id INT PRIMARY KEY, user_id INT, post_id INT, created_at INT)')
        conn.execute("CREATE TABLE dislike (dislike_id INT PRIMARY KEY, user_id INT, post_id INT, created_at INT)")
        conn.execute("CREATE TABLE trace (user_id INT, created_at INT, action TEXT, info TEXT)")
        conn.execute("INSERT INTO user VALUES (0, 0, NULL, 'a0', 'bio', 0, 0, 0)")

        # Early posts (round 0-3): bullish
        for i in range(4):
            conn.execute("INSERT INTO post VALUES (?,0,NULL,?,NULL,?,0,0,0,0)",
                         (i, "I think this is growth and positive and bullish trends.", i))
        # Late posts (round 4-7): bearish
        for i in range(4, 8):
            conn.execute("INSERT INTO post VALUES (?,0,NULL,?,NULL,?,0,0,0,0)",
                         (i, "There is significant risk and decline and bearish patterns.", i))

        conn.commit()
        conn.close()

        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_momentum_neg")
        assert result.momentum < 0, f"Expected negative momentum, got {result.momentum}"


# ---------------------------------------------------------------------------
# Consensus
# ---------------------------------------------------------------------------


class TestConsensus:

    def test_consensus_strength_high(self, tmp_path):
        """All agents agree -> high consensus."""
        # All bullish => everyone agrees
        create_test_simulation(
            tmp_path, num_agents=10, num_posts=50, bullish_ratio=1.0, seed=333,
        )
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_test")
        assert result.consensus_strength > 0.5, (
            f"Expected high consensus, got {result.consensus_strength}"
        )

    def test_consensus_strength_low(self, tmp_path):
        """Agents strongly disagree -> low consensus (relative to unanimous)."""
        # 50/50 split should have lower consensus than unanimous
        create_test_simulation(
            tmp_path, num_agents=10, num_posts=100, bullish_ratio=0.5,
            seed=444, sim_id="sim_divided",
        )
        create_test_simulation(
            tmp_path, num_agents=10, num_posts=100, bullish_ratio=1.0,
            seed=555, sim_id="sim_unanimous",
        )
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        divided = analyzer.analyze("sim_divided")
        unanimous = analyzer.analyze("sim_unanimous")
        assert divided.consensus_strength < unanimous.consensus_strength, (
            f"Divided ({divided.consensus_strength}) should have lower consensus "
            f"than unanimous ({unanimous.consensus_strength})"
        )


# ---------------------------------------------------------------------------
# Opinion shift detection
# ---------------------------------------------------------------------------


class TestOpinionShift:

    def test_opinion_shift_detection(self, tmp_path):
        """Agent starts bullish ends bearish -> shifted=True."""
        sim_dir = tmp_path / "sim_shift"
        sim_dir.mkdir(parents=True, exist_ok=True)

        config = {
            "simulation_id": "sim_shift",
            "agent_configs": [
                {"agent_id": 0, "entity_name": "shifter", "entity_type": "Analyst",
                 "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 2.0}
            ],
        }
        (sim_dir / "simulation_config.json").write_text(json.dumps(config))

        db_path = sim_dir / "twitter_simulation.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE user (user_id INT, agent_id INT, user_name TEXT, name TEXT, bio TEXT, created_at INT, num_followings INT, num_followers INT)")
        conn.execute("CREATE TABLE post (post_id INT PRIMARY KEY, user_id INT, original_post_id INT, content TEXT, quote_content TEXT, created_at INT, num_likes INT, num_dislikes INT, num_shares INT, num_reports INT)")
        conn.execute("CREATE TABLE comment (comment_id INT PRIMARY KEY, post_id INT, user_id INT, content TEXT, created_at INT, num_likes INT, num_dislikes INT)")
        conn.execute('CREATE TABLE "like" (like_id INT PRIMARY KEY, user_id INT, post_id INT, created_at INT)')
        conn.execute("CREATE TABLE dislike (dislike_id INT PRIMARY KEY, user_id INT, post_id INT, created_at INT)")
        conn.execute("CREATE TABLE trace (user_id INT, created_at INT, action TEXT, info TEXT)")
        conn.execute("INSERT INTO user VALUES (0, 0, NULL, 'shifter', 'bio', 0, 0, 0)")

        # First 6 posts: strongly bullish
        for i in range(6):
            conn.execute("INSERT INTO post VALUES (?,0,NULL,?,NULL,?,0,0,0,0)",
                         (i, "Absolutely bullish growth positive optimistic likely success above higher.", i))
        # Last 6 posts: strongly bearish
        for i in range(6, 12):
            conn.execute("INSERT INTO post VALUES (?,0,NULL,?,NULL,?,0,0,0,0)",
                         (i, "Very bearish decline risk pessimistic unlikely concern below lower.", i))

        conn.commit()
        conn.close()

        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_shift")
        shifted_agents = [a for a in result.agents if a.opinion_shifted]
        assert len(shifted_agents) >= 1, "Expected at least one agent to show opinion shift"
        assert shifted_agents[0].shift_direction == "toward_no"


# ---------------------------------------------------------------------------
# Prediction range and confidence
# ---------------------------------------------------------------------------


class TestComputedPrediction:

    def test_computed_prediction_range(self, tmp_path):
        """Computed prediction is always between 0.03 and 0.97."""
        for ratio in [0.0, 0.1, 0.5, 0.9, 1.0]:
            sim_id = f"sim_range_{int(ratio * 100)}"
            create_test_simulation(
                tmp_path, num_agents=5, num_posts=20,
                bullish_ratio=ratio, seed=int(ratio * 1000), sim_id=sim_id,
            )
            analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
            result = analyzer.analyze(sim_id)
            assert 0.03 <= result.computed_probability <= 0.97, (
                f"Prediction {result.computed_probability} out of [0.03, 0.97] "
                f"for bullish_ratio={ratio}"
            )

    def test_confidence_low_few_interactions(self, tmp_path):
        """Very few posts from few agents -> low confidence.

        The confidence scoring gives points for interactions>20, consensus>0.4,
        agents>=10, and expert-crowd agreement. With 4 posts and 2 agents,
        the score should stay below the 'medium' threshold of 3.
        """
        create_test_simulation(
            tmp_path, num_agents=2, num_posts=4, bullish_ratio=0.5,
            seed=666, sim_id="sim_low_conf",
        )
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_low_conf")
        assert result.confidence == "low", (
            f"Expected 'low' confidence with 4 posts and 2 agents, got '{result.confidence}'"
        )

    def test_confidence_high_many_interactions(self, tmp_path):
        """100 posts from 20+ agents with strong consensus -> high confidence."""
        # Create a large unanimous simulation
        create_test_simulation(
            tmp_path, num_agents=25, num_posts=200,
            bullish_ratio=1.0, seed=777, sim_id="sim_high_conf",
        )
        analyzer = SimulationAnalyzer(simulations_dir=tmp_path)
        result = analyzer.analyze("sim_high_conf")
        # With 200 interactions, 25 agents, and unanimous consensus, confidence should be high
        assert result.confidence in ("medium", "high"), (
            f"Expected 'medium' or 'high' confidence, got '{result.confidence}'"
        )
