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

@dataclass
class DeepSeedTemplate:
    """Extended template for deep seed documents with category-specific prompts."""

    category: str
    agent_focus: str
    context_emphasis: str
    seed_header: str
    # Additional deep-research sections
    background_prompt: str
    stakeholder_prompt: str
    contrarian_prompt: str
    historical_prompt: str


DEEP_TEMPLATES: dict[str, DeepSeedTemplate] = {
    "politics": DeepSeedTemplate(
        category="politics",
        agent_focus="voters, pundits, political analysts, pollsters, campaign strategists",
        context_emphasis="polling data, historical election results, campaign dynamics, endorsements",
        seed_header=(
            "This market concerns a political event. Agents should weigh polling "
            "trends, partisan dynamics, incumbent advantages, and historical precedent "
            "when forming predictions."
        ),
        background_prompt=(
            "Provide background on the political landscape: electoral history of the "
            "region/office, recent polling data and trends, key endorsements from major "
            "figures, party dynamics and internal divisions, and demographic shifts "
            "that may influence the outcome."
        ),
        stakeholder_prompt=(
            "Identify the key political actors: candidates, party leaders, major donors, "
            "influential media figures, and voter blocs whose behavior will determine "
            "the outcome."
        ),
        contrarian_prompt=(
            "Consider why polls might be wrong: historical polling errors, shy voter "
            "effects, differential turnout, late-breaking events, and October surprises. "
            "What would a major upset look like and what would cause it?"
        ),
        historical_prompt=(
            "What historical elections or political events are most analogous? What were "
            "the base rates for incumbents, underdogs, or similar political dynamics? "
            "How often do late swings change outcomes?"
        ),
    ),
    "crypto": DeepSeedTemplate(
        category="crypto",
        agent_focus="traders, blockchain analysts, DeFi researchers, quant strategists",
        context_emphasis="on-chain metrics, trading volume, regulatory developments, macro context",
        seed_header=(
            "This market concerns a cryptocurrency or blockchain event. Agents "
            "should consider on-chain data, exchange flows, regulatory signals, and "
            "broader macro conditions when forming predictions."
        ),
        background_prompt=(
            "Provide technical analysis context: key support/resistance levels, recent "
            "price action, on-chain metrics (active addresses, exchange inflows/outflows, "
            "whale movements), and relevant macro indicators (DXY, interest rates, "
            "risk-on/risk-off sentiment)."
        ),
        stakeholder_prompt=(
            "Identify key actors: major holders (whales), exchanges, protocol developers, "
            "regulators (SEC, CFTC, international bodies), and institutional players "
            "whose actions may move the market."
        ),
        contrarian_prompt=(
            "Consider: Is the market pricing in a black swan? Could a regulatory crackdown, "
            "protocol exploit, or macro shock invalidate current assumptions? What does "
            "extreme bearish/bullish scenario look like?"
        ),
        historical_prompt=(
            "What historical crypto cycles, halvings, or regulatory events are analogous? "
            "How did similar setups resolve in past bull/bear markets? What are the base "
            "rates for the type of price move being predicted?"
        ),
    ),
    "sports": DeepSeedTemplate(
        category="sports",
        agent_focus="sports analysts, statisticians, bettors, coaches",
        context_emphasis="team/player statistics, injury reports, historical matchups, venue factors",
        seed_header=(
            "This market concerns a sporting event. Agents should evaluate recent "
            "performance, head-to-head records, injury status, and situational "
            "factors when forming predictions."
        ),
        background_prompt=(
            "Provide context on recent form: last 5-10 game results, key player "
            "statistics and trends, injury reports, rest days, and travel schedules. "
            "Include any relevant venue or weather factors."
        ),
        stakeholder_prompt=(
            "Identify the key players, coaches, and external factors: star performers, "
            "players returning from injury, coaching changes, referee assignments, "
            "and any off-field distractions."
        ),
        contrarian_prompt=(
            "Consider upsets: What is the historical upset rate in this context? Are "
            "there motivation asymmetries (must-win vs. nothing to play for)? Could "
            "fatigue, travel, or complacency affect the favourite?"
        ),
        historical_prompt=(
            "What do head-to-head records show? How does the home/away split look? "
            "What is the base rate for the underdog in similar matchups? Are there "
            "any playoff/tournament-specific dynamics?"
        ),
    ),
    "culture": DeepSeedTemplate(
        category="culture",
        agent_focus="cultural commentators, entertainment analysts, social media observers",
        context_emphasis="public sentiment, media coverage, social media trends, historical analogies",
        seed_header=(
            "This market concerns a cultural or entertainment event. Agents should "
            "consider media buzz, public sentiment, historical patterns in similar "
            "events, and social media momentum when forming predictions."
        ),
        background_prompt=(
            "Provide context on the cultural landscape: media coverage intensity, "
            "social media sentiment and volume, critical reception, and any "
            "controversies or viral moments driving attention."
        ),
        stakeholder_prompt=(
            "Identify key figures: celebrities, media outlets, influencers, fan "
            "communities, and industry insiders whose opinions or actions may "
            "influence the outcome."
        ),
        contrarian_prompt=(
            "Consider: Is the media narrative overblown? Could public fatigue, "
            "backlash, or a sudden shift in attention change the outcome? What "
            "are voters/audiences actually thinking vs. what the media says?"
        ),
        historical_prompt=(
            "What historical cultural events, award races, or viral moments are "
            "analogous? How often does the frontrunner actually win? What is the "
            "base rate for upsets or surprises in this domain?"
        ),
    ),
    "science": DeepSeedTemplate(
        category="science",
        agent_focus="researchers, domain experts, science journalists, regulators",
        context_emphasis="peer-reviewed evidence, experimental data, expert consensus, regulatory timeline",
        seed_header=(
            "This market concerns a scientific or technological development. Agents "
            "should prioritise peer-reviewed evidence, expert consensus, and "
            "technical feasibility when forming predictions."
        ),
        background_prompt=(
            "Provide context on the current research status: latest published results, "
            "phase of development (research/trial/deployment), regulatory timeline and "
            "hurdles, funding status, and expert consensus on feasibility."
        ),
        stakeholder_prompt=(
            "Identify key actors: lead researchers, funding agencies, regulatory bodies "
            "(FDA, EMA, etc.), competing teams or technologies, and industry partners "
            "whose decisions affect the timeline."
        ),
        contrarian_prompt=(
            "Consider: Could replication failures, regulatory rejection, funding cuts, "
            "or technical setbacks delay or prevent the outcome? What is the historical "
            "failure rate for similar scientific milestones?"
        ),
        historical_prompt=(
            "What historical scientific breakthroughs or regulatory approvals are "
            "analogous? How long did similar developments take from announcement to "
            "completion? What is the base rate for success at this stage?"
        ),
    ),
    "business": DeepSeedTemplate(
        category="business",
        agent_focus="financial analysts, industry insiders, economists, corporate strategists",
        context_emphasis="earnings data, market trends, regulatory filings, macroeconomic indicators",
        seed_header=(
            "This market concerns a business or economic event. Agents should "
            "examine financial data, regulatory environment, competitive landscape, "
            "and macro trends when forming predictions."
        ),
        background_prompt=(
            "Provide context on the business landscape: recent earnings and guidance, "
            "market share trends, competitive dynamics, regulatory environment, and "
            "macroeconomic indicators (GDP, employment, inflation) relevant to the "
            "outcome."
        ),
        stakeholder_prompt=(
            "Identify key actors: company executives, board members, major shareholders, "
            "regulators, competitors, and customers whose decisions may influence "
            "the outcome."
        ),
        contrarian_prompt=(
            "Consider: Could an earnings miss, regulatory surprise, market downturn, "
            "or competitive disruption change the outcome? What would a worst-case "
            "scenario look like for the consensus view?"
        ),
        historical_prompt=(
            "What historical business events, mergers, IPOs, or regulatory decisions "
            "are analogous? How often do consensus forecasts prove correct in this "
            "domain? What are the base rates for similar outcomes?"
        ),
    ),
    "general": DeepSeedTemplate(
        category="general",
        agent_focus="generalist analysts, forecasters, informed citizens, domain experts",
        context_emphasis="news coverage, base rates, expert opinions, historical analogies",
        seed_header=(
            "This market covers a general prediction topic. Agents should gather "
            "broad evidence, consider base rates for similar events, and weigh "
            "expert opinions when forming predictions."
        ),
        background_prompt=(
            "Provide broad context: What is the current situation? What are the key "
            "factors that will determine the outcome? What do experts and commentators "
            "think is most likely?"
        ),
        stakeholder_prompt=(
            "Identify the key decision-makers, influencers, and affected parties "
            "whose actions or reactions will determine the outcome."
        ),
        contrarian_prompt=(
            "Consider: Why might the consensus be wrong? What overlooked factors, "
            "black swans, or tail risks could change the outcome? What would need "
            "to be true for the opposite of the expected outcome to occur?"
        ),
        historical_prompt=(
            "What historical events or analogies are most relevant? What are the "
            "base rates for similar predictions resolving YES vs NO? How often do "
            "prediction markets get events like this right?"
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
