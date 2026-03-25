"""Category-specific simulation prompts for the MiroFish pipeline orchestrator."""

PROMPT_TEMPLATES: dict[str, str] = {
    "politics": (
        "Simulate a diverse group of political actors — voters across demographics, "
        "political analysts, campaign strategists, media commentators, and policy experts "
        "— debating and reacting to: {question}. Agents should form opinions, argue their "
        "positions, and shift views as they encounter new information. After deliberation, "
        "estimate the probability of each outcome."
    ),
    "crypto": (
        "Simulate crypto market participants — traders, DeFi developers, institutional "
        "investors, blockchain analysts, and retail speculators — discussing: {question}. "
        "Agents should consider market trends, on-chain data implications, regulatory "
        "factors, and market sentiment. Estimate the probability of each outcome."
    ),
    "sports": (
        "Simulate sports stakeholders — fans, statisticians, coaches, sports journalists, "
        "and betting analysts — predicting: {question}. Agents should consider team "
        "performance, player stats, historical matchups, injuries, and momentum. Estimate "
        "the probability of each outcome."
    ),
    "business": (
        "Simulate business analysts, industry insiders, investors, journalists, and "
        "consumers debating: {question}. Consider market dynamics, company performance, "
        "competitive landscape, and macroeconomic factors. Estimate the probability of "
        "each outcome."
    ),
    "general": (
        "Simulate a diverse group of informed stakeholders with varying perspectives "
        "debating: {question}. Agents should present evidence-based arguments, challenge "
        "opposing views, and converge toward a probability estimate for each outcome."
    ),
}


def get_simulation_prompt(market_question: str, category: str = "general") -> str:
    """Return a simulation prompt tailored to the market category.

    Args:
        market_question: The prediction market question to simulate.
        category: One of 'politics', 'crypto', 'sports', 'business', or
                  'general'. Falls back to 'general' if unrecognised.

    Returns:
        A fully-formatted prompt string ready for MiroFish agents.
    """
    template = PROMPT_TEMPLATES.get(category.lower(), PROMPT_TEMPLATES["general"])
    return template.format(question=market_question)
