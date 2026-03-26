"""Quantitative prediction extraction from MiroFish simulation data.

Instead of asking an LLM to read a prose report and guess a probability,
this module reads the raw simulation SQLite databases and COMPUTES a
prediction from the actual agent behavior data.

The prediction emerges from:
1. What agents said (sentiment analysis of posts/comments)
2. How agents interacted (likes, dislikes, engagement patterns)
3. How opinions shifted over time (temporal analysis)
4. Who said what (expertise-weighted analysis)
5. Where consensus formed or didn't (agreement metrics)
"""

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentAnalysis:
    """Analysis of a single agent's behavior during simulation."""
    agent_id: int
    name: str
    entity_type: str
    configured_stance: str  # bullish/neutral/bearish from config
    influence_weight: float

    # Computed from posts/comments
    total_posts: int = 0
    total_comments: int = 0
    bullish_posts: int = 0
    bearish_posts: int = 0
    neutral_posts: int = 0
    observed_sentiment: float = 0.5  # 0=bearish, 0.5=neutral, 1=bullish

    # Engagement received
    total_likes_received: int = 0
    total_dislikes_received: int = 0

    # Temporal
    early_sentiment: float = 0.5  # First third of rounds
    late_sentiment: float = 0.5   # Last third of rounds
    opinion_shifted: bool = False
    shift_direction: str = ""  # "toward_yes", "toward_no", "none"


@dataclass
class SimulationAnalysis:
    """Complete quantitative analysis of a simulation run."""
    simulation_id: str
    market_question: str

    # Agent-level analysis
    agents: list[AgentAnalysis] = field(default_factory=list)
    total_agents: int = 0

    # Content stats
    total_posts: int = 0
    total_comments: int = 0
    total_interactions: int = 0

    # Sentiment metrics (0 = bearish, 0.5 = neutral, 1 = bullish)
    raw_sentiment: float = 0.5
    weighted_sentiment: float = 0.5  # Weighted by influence
    expert_sentiment: float = 0.5    # Only high-influence agents

    # Temporal metrics
    early_round_sentiment: float = 0.5
    late_round_sentiment: float = 0.5
    momentum: float = 0.0  # Positive = shifting bullish, negative = shifting bearish

    # Consensus metrics
    consensus_strength: float = 0.0  # 0 = divided, 1 = unanimous
    agents_shifted: int = 0
    shift_direction: str = ""  # net direction of shifts

    # Engagement metrics
    bullish_engagement: float = 0.0  # Likes on bullish content
    bearish_engagement: float = 0.0  # Likes on bearish content

    # Final computed prediction
    computed_probability: float = 0.5
    confidence: str = "low"
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "simulation_id": self.simulation_id,
            "market_question": self.market_question,
            "total_agents": self.total_agents,
            "total_posts": self.total_posts,
            "total_comments": self.total_comments,
            "raw_sentiment": round(self.raw_sentiment, 4),
            "weighted_sentiment": round(self.weighted_sentiment, 4),
            "expert_sentiment": round(self.expert_sentiment, 4),
            "momentum": round(self.momentum, 4),
            "consensus_strength": round(self.consensus_strength, 4),
            "agents_shifted": self.agents_shifted,
            "computed_probability": round(self.computed_probability, 4),
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "agents": [
                {
                    "name": a.name,
                    "type": a.entity_type,
                    "stance": a.configured_stance,
                    "influence": a.influence_weight,
                    "sentiment": round(a.observed_sentiment, 3),
                    "posts": a.total_posts,
                    "shifted": a.opinion_shifted,
                    "shift_dir": a.shift_direction,
                }
                for a in self.agents
            ],
        }


class SimulationAnalyzer:
    """Extract quantitative predictions from MiroFish simulation databases."""

    # Keywords for sentiment classification (simple but effective)
    BULLISH_KEYWORDS = [
        "will", "likely", "expect", "positive", "growth", "increase", "rise",
        "bullish", "optimistic", "strong", "momentum", "upward", "gain",
        "success", "achieve", "reach", "surpass", "above", "higher",
        "confident", "probable", "favorable", "support", "advance",
        "yes", "agree", "certainly", "definitely", "clearly",
    ]

    BEARISH_KEYWORDS = [
        "unlikely", "doubt", "risk", "decline", "decrease", "fall", "drop",
        "bearish", "pessimistic", "weak", "concern", "downward", "loss",
        "fail", "miss", "below", "lower", "uncertain", "challenge",
        "no", "disagree", "improbable", "difficult", "obstacle",
        "volatile", "unstable", "threat", "worry", "caution",
    ]

    def __init__(self, simulations_dir: Path = None):
        if simulations_dir is None:
            simulations_dir = Path(__file__).parent.parent.parent / "MiroFish" / "backend" / "uploads" / "simulations"
        self._sim_dir = simulations_dir

    def analyze(self, simulation_id: str, market_question: str = "", market_odds: float = 0.5) -> SimulationAnalysis:
        """Run full quantitative analysis on a completed simulation.

        Returns a SimulationAnalysis with a computed probability.
        """
        sim_path = self._sim_dir / simulation_id
        if not sim_path.exists():
            raise FileNotFoundError(f"Simulation directory not found: {sim_path}")

        analysis = SimulationAnalysis(
            simulation_id=simulation_id,
            market_question=market_question,
        )

        # Load agent configs
        config_file = sim_path / "simulation_config.json"
        agent_configs = {}
        if config_file.exists():
            config = json.loads(config_file.read_text())
            for ac in config.get("agent_configs", []):
                agent_configs[ac["agent_id"]] = ac

        # Analyze both platforms
        all_posts = []
        all_comments = []

        for db_name in ["twitter_simulation.db", "reddit_simulation.db"]:
            db_path = sim_path / db_name
            if not db_path.exists():
                continue

            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row

                posts = self._get_posts(conn)
                comments = self._get_comments(conn)
                users = self._get_users(conn)
                likes = self._get_likes(conn)
                dislikes = self._get_dislikes(conn)

                all_posts.extend(posts)
                all_comments.extend(comments)

                conn.close()
            except Exception as e:
                logger.warning("Failed to read %s: %s", db_path, e)

        if not all_posts and not all_comments:
            logger.warning("No posts or comments found for %s", simulation_id)
            analysis.reasoning = "No simulation content to analyze"
            return analysis

        analysis.total_posts = len(all_posts)
        analysis.total_comments = len(all_comments)
        analysis.total_interactions = len(all_posts) + len(all_comments)

        # Build agent analysis objects
        agent_map = {}
        for ac_id, ac in agent_configs.items():
            agent = AgentAnalysis(
                agent_id=ac_id,
                name=ac.get("entity_name", f"agent_{ac_id}"),
                entity_type=ac.get("entity_type", "unknown"),
                configured_stance=ac.get("stance", "neutral"),
                influence_weight=ac.get("influence_weight", 1.0),
            )
            agent_map[ac_id] = agent

        # Classify sentiment of each post
        post_sentiments = []
        for post in all_posts:
            # Combine content and quote_content for full sentiment picture
            text = post["content"] or ""
            quote = post.get("quote_content") or ""
            if quote:
                text = f"{text} {quote}"
            sentiment = self._classify_sentiment(text, market_question)
            user_id = post["user_id"]
            round_num = post["created_at"]

            post_sentiments.append({
                "user_id": user_id,
                "sentiment": sentiment,
                "round": round_num,
                "likes": post.get("num_likes", 0),
                "dislikes": post.get("num_dislikes", 0),
            })

            if user_id in agent_map:
                agent_map[user_id].total_posts += 1
                if sentiment > 0.6:
                    agent_map[user_id].bullish_posts += 1
                elif sentiment < 0.4:
                    agent_map[user_id].bearish_posts += 1
                else:
                    agent_map[user_id].neutral_posts += 1

        # Also classify comments
        for comment in all_comments:
            sentiment = self._classify_sentiment(comment["content"], market_question)
            user_id = comment["user_id"]
            round_num = comment.get("created_at", 0)

            post_sentiments.append({
                "user_id": user_id,
                "sentiment": sentiment,
                "round": round_num,
                "likes": comment.get("num_likes", 0),
                "dislikes": comment.get("num_dislikes", 0),
            })

            if user_id in agent_map:
                agent_map[user_id].total_comments += 1

        # Calculate per-agent observed sentiment
        for agent_id, agent in agent_map.items():
            agent_posts = [p for p in post_sentiments if p["user_id"] == agent_id]
            if agent_posts:
                agent.observed_sentiment = sum(p["sentiment"] for p in agent_posts) / len(agent_posts)

                # Temporal analysis for this agent
                sorted_posts = sorted(agent_posts, key=lambda p: (float(p["round"]) if isinstance(p["round"], (int, float)) else 0))
                third = max(1, len(sorted_posts) // 3)
                early = sorted_posts[:third]
                late = sorted_posts[-third:]

                agent.early_sentiment = sum(p["sentiment"] for p in early) / len(early) if early else 0.5
                agent.late_sentiment = sum(p["sentiment"] for p in late) / len(late) if late else 0.5

                shift = agent.late_sentiment - agent.early_sentiment
                if abs(shift) > 0.1:
                    agent.opinion_shifted = True
                    agent.shift_direction = "toward_yes" if shift > 0 else "toward_no"

        analysis.agents = list(agent_map.values())
        analysis.total_agents = len(analysis.agents)

        # === METRIC 1: Raw Sentiment ===
        if post_sentiments:
            analysis.raw_sentiment = sum(p["sentiment"] for p in post_sentiments) / len(post_sentiments)

        # === METRIC 2: Influence-Weighted Sentiment ===
        weighted_sum = 0.0
        weight_total = 0.0
        for agent in analysis.agents:
            if agent.total_posts + agent.total_comments > 0:
                weighted_sum += agent.observed_sentiment * agent.influence_weight
                weight_total += agent.influence_weight
        analysis.weighted_sentiment = weighted_sum / weight_total if weight_total > 0 else 0.5

        # === METRIC 3: Expert Sentiment (top 30% by influence) ===
        sorted_agents = sorted(analysis.agents, key=lambda a: a.influence_weight, reverse=True)
        top_count = max(1, len(sorted_agents) // 3)
        top_agents = sorted_agents[:top_count]
        expert_sentiments = [a.observed_sentiment for a in top_agents if a.total_posts + a.total_comments > 0]
        analysis.expert_sentiment = sum(expert_sentiments) / len(expert_sentiments) if expert_sentiments else 0.5

        # === METRIC 4: Temporal Momentum ===
        sorted_all = sorted(post_sentiments, key=lambda p: (float(p["round"]) if isinstance(p["round"], (int, float)) else 0))
        if len(sorted_all) >= 4:
            half = len(sorted_all) // 2
            early_half = sorted_all[:half]
            late_half = sorted_all[half:]
            analysis.early_round_sentiment = sum(p["sentiment"] for p in early_half) / len(early_half)
            analysis.late_round_sentiment = sum(p["sentiment"] for p in late_half) / len(late_half)
            analysis.momentum = analysis.late_round_sentiment - analysis.early_round_sentiment

        # === METRIC 5: Consensus Strength ===
        if analysis.agents:
            sentiments = [a.observed_sentiment for a in analysis.agents if a.total_posts + a.total_comments > 0]
            if sentiments:
                mean_s = sum(sentiments) / len(sentiments)
                variance = sum((s - mean_s) ** 2 for s in sentiments) / len(sentiments)
                # Low variance = high consensus, high variance = divided
                analysis.consensus_strength = max(0, 1.0 - (variance * 4))  # Scale: var=0.25 -> 0 consensus

        # === METRIC 6: Opinion Shifts ===
        analysis.agents_shifted = sum(1 for a in analysis.agents if a.opinion_shifted)
        yes_shifts = sum(1 for a in analysis.agents if a.shift_direction == "toward_yes")
        no_shifts = sum(1 for a in analysis.agents if a.shift_direction == "toward_no")
        if yes_shifts + no_shifts > 0:
            analysis.shift_direction = "toward_yes" if yes_shifts > no_shifts else "toward_no"

        # === METRIC 7: Engagement-Weighted Sentiment ===
        bullish_engagement = sum(p["likes"] for p in post_sentiments if p["sentiment"] > 0.6)
        bearish_engagement = sum(p["likes"] for p in post_sentiments if p["sentiment"] < 0.4)
        analysis.bullish_engagement = bullish_engagement
        analysis.bearish_engagement = bearish_engagement

        # === COMPUTE FINAL PREDICTION ===
        analysis.computed_probability = self._compute_prediction(analysis, market_odds)
        analysis.confidence = self._compute_confidence(analysis)
        analysis.reasoning = self._generate_reasoning(analysis, market_odds)

        logger.info(
            "Simulation analysis for %s: raw=%.2f weighted=%.2f expert=%.2f momentum=%+.2f -> prediction=%.1f%%",
            simulation_id, analysis.raw_sentiment, analysis.weighted_sentiment,
            analysis.expert_sentiment, analysis.momentum, analysis.computed_probability * 100,
        )

        return analysis

    def _get_posts(self, conn: sqlite3.Connection) -> list[dict]:
        cursor = conn.execute(
            "SELECT post_id, user_id, content, quote_content, created_at, "
            "num_likes, num_dislikes, num_shares FROM post "
            "WHERE (content IS NOT NULL AND content != '') "
            "OR (quote_content IS NOT NULL AND quote_content != '')"
        )
        return [dict(row) for row in cursor.fetchall()]

    def _get_comments(self, conn: sqlite3.Connection) -> list[dict]:
        cursor = conn.execute("SELECT comment_id, user_id, content, created_at, num_likes, num_dislikes FROM comment WHERE content IS NOT NULL AND content != ''")
        return [dict(row) for row in cursor.fetchall()]

    def _get_users(self, conn: sqlite3.Connection) -> list[dict]:
        cursor = conn.execute("SELECT user_id, agent_id, name, bio FROM user")
        return [dict(row) for row in cursor.fetchall()]

    def _get_likes(self, conn: sqlite3.Connection) -> list[dict]:
        cursor = conn.execute("SELECT like_id, user_id, post_id, created_at FROM \"like\"")
        return [dict(row) for row in cursor.fetchall()]

    def _get_dislikes(self, conn: sqlite3.Connection) -> list[dict]:
        cursor = conn.execute("SELECT dislike_id, user_id, post_id, created_at FROM dislike")
        return [dict(row) for row in cursor.fetchall()]

    def _classify_sentiment(self, text: str, market_question: str) -> float:
        """Classify text sentiment relative to the market question.

        Returns 0.0 (strongly bearish/NO) to 1.0 (strongly bullish/YES).
        0.5 = neutral.
        """
        if not text or not text.strip():
            return 0.5

        text_lower = text.lower()

        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text_lower)

        total = bullish_count + bearish_count
        if total == 0:
            return 0.5

        # Scale to 0-1
        raw = bullish_count / total  # 0 = all bearish keywords, 1 = all bullish

        # Dampen toward 0.5 (don't be too extreme from keyword matching alone)
        dampened = 0.5 + (raw - 0.5) * 0.6

        return max(0.05, min(0.95, dampened))

    def _compute_prediction(self, analysis: SimulationAnalysis, market_odds: float) -> float:
        """Combine all metrics into a final prediction probability."""

        # Weights for each signal
        prediction = (
            analysis.raw_sentiment * 0.15
            + analysis.weighted_sentiment * 0.25
            + analysis.expert_sentiment * 0.25
            + (0.5 + analysis.momentum) * 0.15  # Center momentum around 0.5
            + analysis.raw_sentiment * analysis.consensus_strength * 0.10  # Consensus amplifies sentiment
            + (analysis.bullish_engagement / max(1, analysis.bullish_engagement + analysis.bearish_engagement)) * 0.10
        )

        # Clamp
        prediction = max(0.03, min(0.97, prediction))

        # If consensus is very weak (agents very divided), pull toward market odds
        if analysis.consensus_strength < 0.3:
            prediction = prediction * 0.6 + market_odds * 0.4

        return prediction

    def _compute_confidence(self, analysis: SimulationAnalysis) -> str:
        """Determine confidence level from analysis quality."""
        score = 0

        # More data = higher confidence
        if analysis.total_interactions > 50:
            score += 2
        elif analysis.total_interactions > 20:
            score += 1

        # Strong consensus = higher confidence
        if analysis.consensus_strength > 0.7:
            score += 2
        elif analysis.consensus_strength > 0.4:
            score += 1

        # More agents = higher confidence
        if analysis.total_agents >= 20:
            score += 2
        elif analysis.total_agents >= 10:
            score += 1

        # Expert agreement with crowd = higher confidence
        if abs(analysis.expert_sentiment - analysis.raw_sentiment) < 0.1:
            score += 1

        if score >= 5:
            return "high"
        elif score >= 3:
            return "medium"
        return "low"

    def _generate_reasoning(self, analysis: SimulationAnalysis, market_odds: float) -> str:
        """Generate human-readable reasoning for the prediction."""
        parts = []

        pred = analysis.computed_probability
        direction = "above" if pred > market_odds else "below"
        diff = abs(pred - market_odds)

        parts.append(f"Computed probability: {pred:.1%} ({direction} market odds of {market_odds:.1%} by {diff:.1%})")

        # Sentiment
        if analysis.raw_sentiment > 0.6:
            parts.append(f"Overall sentiment is bullish ({analysis.raw_sentiment:.0%})")
        elif analysis.raw_sentiment < 0.4:
            parts.append(f"Overall sentiment is bearish ({analysis.raw_sentiment:.0%})")
        else:
            parts.append(f"Overall sentiment is mixed ({analysis.raw_sentiment:.0%})")

        # Expert view
        if abs(analysis.expert_sentiment - analysis.raw_sentiment) > 0.1:
            expert_dir = "more bullish" if analysis.expert_sentiment > analysis.raw_sentiment else "more bearish"
            parts.append(f"Experts are {expert_dir} than the crowd ({analysis.expert_sentiment:.0%} vs {analysis.raw_sentiment:.0%})")

        # Momentum
        if abs(analysis.momentum) > 0.05:
            mom_dir = "bullish" if analysis.momentum > 0 else "bearish"
            parts.append(f"Momentum is {mom_dir} ({analysis.momentum:+.0%} shift over simulation)")

        # Consensus
        if analysis.consensus_strength > 0.7:
            parts.append(f"Strong consensus among agents ({analysis.consensus_strength:.0%})")
        elif analysis.consensus_strength < 0.3:
            parts.append(f"Agents are deeply divided ({analysis.consensus_strength:.0%} consensus)")

        # Shifts
        if analysis.agents_shifted > 0:
            parts.append(f"{analysis.agents_shifted} agents changed their position during the simulation ({analysis.shift_direction})")

        parts.append(f"Based on {analysis.total_interactions} posts/comments from {analysis.total_agents} agents")

        return ". ".join(parts) + "."
