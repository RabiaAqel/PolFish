# Competitive Research: Prediction Market Systems & Agent Simulations

## Key Takeaways for PolFish

### #1: Organic Discourse > Formal Polling (WEEX 200-Agent Study)

The most important finding: when 200 agents debated on a Twitter-like simulation about Iran/Hormuz crisis:
- **Formal question** ("what's the probability?"): agents said **47.9%**
- **Organic debate analysis** (pessimist cluster): agents revealed **22%**
- **Polymarket price**: **31%**

The informal consensus was **3x closer** to the market than the formal one. This validates MiroFish's social simulation approach AND our quantitative analyzer (which reads organic debate data from SQLite rather than asking the LLM formally).

### #2: Devil's Advocate Agent (Polymarket Intelligence)

Their 6-role debate format explicitly assigns one agent to argue AGAINST consensus. This prevents groupthink — a known failure mode in agent simulations. PolFish should add a mandatory contrarian agent role.

### #3: Agent Leaderboard (Moltguess)

Track which agent personas perform best over time. When "InstitutionalInvestor" agents are consistently more accurate than "RetailTrader" agents, weight their opinions higher automatically.

### #4: Cost Benchmark Validated

200 agents × 100 rounds on GPT-4o-mini costs **$3-5**. Our TISZA run with 41 agents × 40 rounds on GPT-4o cost $8.50. Moving to mini/DeepSeek with more agents is clearly viable.

---

## Systems Analyzed

### 1. Moltguess (moltguess.com)
- Agent-only prediction market (humans are read-only observers)
- Agents compete on a leaderboard with structured reasoning output
- **Learn**: Agent performance tracking + structured reasoning format

### 2. AdSIM (Spotlightmarket/AdSIM)
- A/B testing simulator using 500 synthetic personas
- ThreadPoolExecutor with 10 workers for parallel agent execution
- Rich action taxonomy (8 actions, not just yes/no)
- **Learn**: Parallel execution pattern + PDF document ingestion for grounding

### 3. WEEX 200-Agent Crisis Simulation
- Same stack as PolFish: OASIS + Zep + GPT-4o-mini
- 200 agents (140 civilians, 16 diplomats, 15 media, 10 energy, 7 finance, 2 military)
- 1,888 posts, 70 original viewpoints, 100 rounds, ~49 min, $3-5
- **Critical finding**: Organic discourse more accurate than formal polling
- **Learn**: Diverse persona composition template + organic > formal methodology

### 4. Polymarket Intelligence (luuisotorres/polymarket-intelligence)
- Full-stack React + FastAPI dashboard
- 6-role LangChain/LangGraph debate: Statistics Expert, Time Decay Analyst, Generalist, Crypto/Macro, Devil's Advocate, Moderator
- Whale monitoring + real-time news feeds
- **Learn**: Devil's Advocate role + LangGraph orchestration + whale signals

---

## Implementation Priority

| Insight | Priority | Effort | Impact |
|---------|----------|--------|--------|
| Weight organic analysis over formal verdict | HIGH | Low (already built) | HIGH |
| Add Devil's Advocate agent template | HIGH | Low | MEDIUM |
| Agent performance leaderboard | MEDIUM | Medium | HIGH |
| Structured reasoning in all predictions | MEDIUM | Low | MEDIUM |
| LangGraph orchestration evaluation | LOW | High | MEDIUM |
| Whale tracking integration | LOW | Medium | LOW |
