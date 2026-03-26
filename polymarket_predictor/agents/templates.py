"""Template agent archetypes for market prediction simulations.

These agents are injected into MiroFish simulations alongside
graph-derived agents to create realistic market dynamics.
"""

MARKET_PARTICIPANT_TEMPLATES = [
    # Retail traders (bullish bias, low influence, high activity)
    {"name": "retail_trader_1", "type": "RetailTrader", "stance": "bullish", "sentiment_bias": 0.3, "influence_weight": 0.5, "activity_level": 0.7, "bio": "Small-cap retail investor, optimistic about market opportunities, follows social media for trading ideas."},
    {"name": "retail_trader_2", "type": "RetailTrader", "stance": "bullish", "sentiment_bias": 0.4, "influence_weight": 0.4, "activity_level": 0.8, "bio": "Part-time trader, tends to follow trends and popular sentiment."},
    {"name": "retail_trader_3", "type": "RetailTrader", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 0.5, "activity_level": 0.6, "bio": "Cautious retail investor, balances risk and reward."},

    # Institutional investors (conservative, high influence, moderate activity)
    {"name": "institutional_1", "type": "InstitutionalInvestor", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 2.5, "activity_level": 0.4, "bio": "Senior portfolio manager at a mid-size fund, data-driven decisions."},
    {"name": "institutional_2", "type": "InstitutionalInvestor", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.8, "activity_level": 0.3, "bio": "Institutional analyst focused on risk assessment and fundamental analysis."},
    {"name": "institutional_3", "type": "InstitutionalInvestor", "stance": "bearish", "sentiment_bias": -0.2, "influence_weight": 2.2, "activity_level": 0.35, "bio": "Conservative fund manager, skeptical of consensus, focuses on downside protection."},

    # Contrarian analysts (always challenge consensus)
    {"name": "contrarian_1", "type": "ContrarianAnalyst", "stance": "bearish", "sentiment_bias": -0.5, "influence_weight": 1.8, "activity_level": 0.6, "bio": "Known contrarian analyst, systematically challenges popular narratives."},
    {"name": "contrarian_2", "type": "ContrarianAnalyst", "stance": "bearish", "sentiment_bias": -0.4, "influence_weight": 1.5, "activity_level": 0.5, "bio": "Skeptical researcher, looks for flaws in consensus thinking."},
    {"name": "contrarian_3", "type": "ContrarianAnalyst", "stance": "bullish", "sentiment_bias": 0.4, "influence_weight": 1.6, "activity_level": 0.55, "bio": "Contrarian who bets against the crowd when markets seem too pessimistic."},

    # Momentum traders (follow trends)
    {"name": "momentum_1", "type": "MomentumTrader", "stance": "neutral", "sentiment_bias": 0.2, "influence_weight": 1.0, "activity_level": 0.7, "bio": "Momentum trader, follows price trends and social sentiment indicators."},
    {"name": "momentum_2", "type": "MomentumTrader", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 0.8, "activity_level": 0.75, "bio": "Short-term trader, reacts quickly to news and price movements."},

    # Risk analysts (focus on downside)
    {"name": "risk_analyst_1", "type": "RiskAnalyst", "stance": "bearish", "sentiment_bias": -0.3, "influence_weight": 2.0, "activity_level": 0.45, "bio": "Professional risk analyst, identifies tail risks and worst-case scenarios."},
    {"name": "risk_analyst_2", "type": "RiskAnalyst", "stance": "neutral", "sentiment_bias": -0.15, "influence_weight": 1.8, "activity_level": 0.4, "bio": "Quantitative risk modeler, focuses on probability distributions and base rates."},

    # News traders (reactive)
    {"name": "news_trader_1", "type": "NewsTrader", "stance": "neutral", "sentiment_bias": 0.1, "influence_weight": 1.2, "activity_level": 0.85, "bio": "Fast-moving news trader, first to react to breaking headlines."},
    {"name": "news_trader_2", "type": "NewsTrader", "stance": "neutral", "sentiment_bias": -0.05, "influence_weight": 1.0, "activity_level": 0.8, "bio": "Information arbitrageur, trades on news before the crowd digests it."},

    # General public (low activity, follows crowd)
    {"name": "public_observer_1", "type": "GeneralPublic", "stance": "neutral", "sentiment_bias": 0.05, "influence_weight": 0.3, "activity_level": 0.2, "bio": "Casual market observer, occasionally shares opinions."},
    {"name": "public_observer_2", "type": "GeneralPublic", "stance": "bullish", "sentiment_bias": 0.15, "influence_weight": 0.3, "activity_level": 0.15, "bio": "Optimistic bystander, follows trending topics."},
    {"name": "public_observer_3", "type": "GeneralPublic", "stance": "bearish", "sentiment_bias": -0.1, "influence_weight": 0.3, "activity_level": 0.25, "bio": "Worried citizen, focuses on negative news."},
    {"name": "public_observer_4", "type": "GeneralPublic", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.2, "activity_level": 0.1, "bio": "Silent observer, rarely posts but reads everything."},
    {"name": "public_observer_5", "type": "GeneralPublic", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 0.3, "activity_level": 0.2, "bio": "Average person following the discussion out of curiosity."},

    # Whale traders (huge influence, low activity)
    {"name": "whale_1", "type": "WhaleTrader", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 3.0, "activity_level": 0.2, "bio": "Large position holder, rare but impactful market participant."},
    {"name": "whale_2", "type": "WhaleTrader", "stance": "bullish", "sentiment_bias": 0.2, "influence_weight": 2.8, "activity_level": 0.15, "bio": "High-net-worth individual with strong convictions when they speak."},

    # Domain expert (added dynamically based on market category)
    {"name": "domain_expert_1", "type": "DomainExpert", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.5, "activity_level": 0.5, "bio": "Subject matter expert providing specialized knowledge."},
    {"name": "domain_expert_2", "type": "DomainExpert", "stance": "neutral", "sentiment_bias": -0.1, "influence_weight": 2.3, "activity_level": 0.45, "bio": "Academic researcher with deep domain knowledge."},

    # Prediction market specialist
    {"name": "prediction_specialist_1", "type": "PredictionSpecialist", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 2.0, "activity_level": 0.5, "bio": "Experienced prediction market trader, calibrated and probabilistic thinker."},
    {"name": "prediction_specialist_2", "type": "PredictionSpecialist", "stance": "neutral", "sentiment_bias": 0.0, "influence_weight": 1.8, "activity_level": 0.45, "bio": "Superforecaster, trained in base rates and debiasing techniques."},
]


def get_templates(max_agents: int = 30) -> list[dict]:
    """Get template agents, capped at max_agents."""
    return MARKET_PARTICIPANT_TEMPLATES[:max_agents]


def get_stance_summary(templates: list[dict]) -> dict:
    """Summarize stance distribution of templates."""
    bullish = sum(1 for t in templates if t["stance"] == "bullish")
    bearish = sum(1 for t in templates if t["stance"] == "bearish")
    neutral = sum(1 for t in templates if t["stance"] == "neutral")
    return {"bullish": bullish, "bearish": bearish, "neutral": neutral, "total": len(templates)}
