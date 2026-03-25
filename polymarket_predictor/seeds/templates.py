"""Category-specific templates for building seed documents."""

from dataclasses import dataclass


@dataclass
class SeedTemplate:
    """Template that shapes seed document content based on market category."""

    category: str
    agent_focus: str
    context_emphasis: str
    seed_header: str


TEMPLATES: dict[str, SeedTemplate] = {
    "politics": SeedTemplate(
        category="politics",
        agent_focus="voters, pundits, political analysts",
        context_emphasis="polling data, historical election results, campaign dynamics",
        seed_header=(
            "This market concerns a political event. Agents should weigh polling "
            "trends, partisan dynamics, incumbent advantages, and historical precedent "
            "when forming predictions."
        ),
    ),
    "crypto": SeedTemplate(
        category="crypto",
        agent_focus="traders, blockchain analysts, DeFi researchers",
        context_emphasis="on-chain metrics, trading volume, regulatory developments, market sentiment",
        seed_header=(
            "This market concerns a cryptocurrency or blockchain event. Agents "
            "should consider on-chain data, exchange flows, regulatory signals, and "
            "broader macro conditions when forming predictions."
        ),
    ),
    "sports": SeedTemplate(
        category="sports",
        agent_focus="sports analysts, statisticians, bettors",
        context_emphasis="team/player statistics, injury reports, historical matchups, venue factors",
        seed_header=(
            "This market concerns a sporting event. Agents should evaluate recent "
            "performance, head-to-head records, injury status, and situational "
            "factors when forming predictions."
        ),
    ),
    "culture": SeedTemplate(
        category="culture",
        agent_focus="cultural commentators, entertainment analysts, social media observers",
        context_emphasis="public sentiment, media coverage, social media trends, historical analogies",
        seed_header=(
            "This market concerns a cultural or entertainment event. Agents should "
            "consider media buzz, public sentiment, historical patterns in similar "
            "events, and social media momentum when forming predictions."
        ),
    ),
    "science": SeedTemplate(
        category="science",
        agent_focus="researchers, domain experts, science journalists",
        context_emphasis="peer-reviewed evidence, experimental data, expert consensus, replication status",
        seed_header=(
            "This market concerns a scientific or technological development. Agents "
            "should prioritise peer-reviewed evidence, expert consensus, and "
            "technical feasibility when forming predictions."
        ),
    ),
    "business": SeedTemplate(
        category="business",
        agent_focus="financial analysts, industry insiders, economists",
        context_emphasis="earnings data, market trends, regulatory filings, macroeconomic indicators",
        seed_header=(
            "This market concerns a business or economic event. Agents should "
            "examine financial data, regulatory environment, competitive landscape, "
            "and macro trends when forming predictions."
        ),
    ),
    "general": SeedTemplate(
        category="general",
        agent_focus="generalist analysts, forecasters, informed citizens",
        context_emphasis="news coverage, base rates, expert opinions, historical analogies",
        seed_header=(
            "This market covers a general prediction topic. Agents should gather "
            "broad evidence, consider base rates for similar events, and weigh "
            "expert opinions when forming predictions."
        ),
    ),
}

# Maps Polymarket category strings to template keys.
CATEGORY_MAP: dict[str, str] = {
    # Politics
    "Politics": "politics",
    "US Politics": "politics",
    "Elections": "politics",
    "World Politics": "politics",
    # Crypto / blockchain
    "Crypto": "crypto",
    "Cryptocurrency": "crypto",
    "Bitcoin": "crypto",
    "Ethereum": "crypto",
    "DeFi": "crypto",
    # Sports
    "Sports": "sports",
    "NBA": "sports",
    "NFL": "sports",
    "MLB": "sports",
    "Soccer": "sports",
    "MMA": "sports",
    "Tennis": "sports",
    # Culture / entertainment
    "Culture": "culture",
    "Entertainment": "culture",
    "Music": "culture",
    "Awards": "culture",
    "Pop Culture": "culture",
    # Science / tech
    "Science": "science",
    "Technology": "science",
    "AI": "science",
    "Space": "science",
    "Climate": "science",
    # Business / finance
    "Business": "business",
    "Finance": "business",
    "Economics": "business",
    "Stocks": "business",
    "Companies": "business",
}
