# Prediction Pipeline Research: The Fish Needs a Bigger Ocean

**PolFish Prediction Engine -- Pipeline Analysis and Improvement Roadmap**

---

## 1. Opening

We built PolFish. It works end-to-end. Markets get scanned, seeds get generated, agents debate, reports get written, probabilities get extracted, bets get sized, and the paper portfolio tracks everything. The plumbing is solid.

But the predictions are mediocre.

We have run 4 real deep predictions so far, producing probabilities of **25%, 5%, 15%, and 62%**. Those are specific numbers, but we have no idea if they are *good* numbers. Are they better than the market price? Are they better than just asking GPT-4o directly? Are they better than flipping a coin and multiplying by 100?

The Monte Carlo research (see [MONTE_CARLO_RESEARCH.md](MONTE_CARLO_RESEARCH.md)) told us what accuracy we *need*. This document dissects the pipeline to figure out what accuracy we actually *have* -- and more importantly, where the bottlenecks are and how to fix them.

**The thesis:** PolFish's prediction pipeline has at least six identifiable weaknesses. The biggest one is not the simulation itself -- it is how we *extract* the prediction from the simulation. Fixing that single step could be worth more than all other improvements combined.

---

## 2. The Current Pipeline (With Actual Data From Our Runs)

Let us walk through each step of the pipeline, using real data from our overnight runs, and be honest about what is working and what is not.

---

### Step 1: Seed Document

**Current state:** 3 DuckDuckGo snippets, roughly 1,000 words total.

**Real example:** For the market "Will the US and Iran reach a ceasefire agreement by July 2025?", we fed three short news articles -- an AP headline, a Reuters brief, and a CNN summary. Total context: about 900 words of surface-level reporting.

**What a Bloomberg analyst would do:** Read 20+ sources -- diplomatic cables, historical ceasefire data, expert interviews, think-tank analyses, satellite imagery reports, UN resolution histories, oil price correlations, and sanctions timeline data. They would spend hours, not seconds, building context.

**The problem:** Our agents are being asked to debate geopolitics after reading three tweets. The seed document is the informational foundation for everything downstream. When the foundation is thin, every subsequent step -- the knowledge graph, the agent reasoning, the debate quality -- inherits that thinness.

Think of it like asking someone to write a PhD thesis after reading the back cover of one textbook. They will produce *something*, but it will be shallow, generic, and probably wrong in the details that matter.

---

### Step 2: Knowledge Graph

**Current state:** 4-5 nodes, 3-4 edges.

**Real example:** The Iran-US ceasefire knowledge graph had nodes `[Iran, US, Diplomats, Sanctions]` with edges `[negotiates_with, imposes]`. That is the entire graph. Four sticky notes connected by three arrows.

**What a real knowledge graph would look like:** A proper graph for Iran-US relations would have 100+ entities -- specific diplomats (names, track records, current positions), military installations, oil price benchmarks, UN resolutions (by number), historical ceasefire attempts (dates, terms, outcomes), proxy conflicts, sanctions packages (specific EOs and their targets), allied nations' positions, and key swing factors.

**The problem:** Like trying to solve a murder mystery with a sticky note that says "someone died." The knowledge graph is supposed to give agents a structured map of the problem space. With 4 nodes, that map covers about as much territory as a postage stamp.

The consequence is that agents cannot reason about relationships they do not know exist. If the graph does not include "oil prices" as a node, no agent will bring up the economic pressure angle -- even though it might be the single most important factor in whether a ceasefire happens.

---

### Step 3: Agent Personas

**Current state:** 3 generic agents -- "Analyst", "Observer", "Expert".

**The problem:** All three are basically the same person wearing different hats. They have different titles but identical incentive structures, similar knowledge bases, and no reason to genuinely disagree. When "Analyst" and "Expert" both read the same thin seed document and both have access to the same tiny knowledge graph, they converge to the same conclusion almost immediately.

**What a real prediction market looks like:**

| Participant Type | Information Source | Bias | Typical Position |
|-----------------|-------------------|------|-----------------|
| Whale trader | Insider networks, private research | Profit-maximizing | High conviction, large size |
| Retail bettor | Twitter, headlines | Recency bias, emotional | Follow trends, small size |
| Quant analyst | Historical data, statistical models | Model-dependent | Data-driven, moderate size |
| Domain expert | Years of field experience | Anchoring to priors | Strong opinions, slow to update |
| Contrarian | Same as everyone else | Systematic disagreement | Opposite of consensus |
| Momentum trader | Price movements only | Trend-following | No opinion on fundamentals |

Our three agents capture none of this diversity. It is like casting a debate show with three copies of the same guest -- polite, informed, moderate, and completely incapable of generating the productive disagreement that makes markets efficient.

---

### Step 4: Simulation

**Current state:** 15 rounds, approximately 40 total posts across 3 agents.

**The problem:** Fifteen rounds is not enough time for opinions to evolve meaningfully. In real markets and real debates, narratives shift. Agent A makes a claim in round 5. Agent B pushes back in round 8. Agent A reconsiders in round 12. A new piece of information surfaces in round 18 that changes everything. Agent B, who was bearish, flips bullish in round 25 after being worn down by accumulating evidence. The final consensus does not form until round 35.

We stop at round 15. We are watching the first 10 minutes of a 2-hour debate and declaring a winner.

In our MiroFish research, opinion convergence typically stabilizes between rounds 25-35. By cutting at 15, we may be capturing initial reactions rather than considered positions. Initial reactions are cheap -- anyone can form an opinion in 5 minutes. Considered positions, the kind that actually predict outcomes, require sustained engagement with counterarguments.

**The math:**

| Configuration | Agents | Rounds | Total Interactions | Information Density |
|--------------|--------|--------|-------------------|-------------------|
| Current | 3 | 15 | ~40 posts | Thin |
| Minimum viable | 15 | 30 | ~300 posts | Moderate |
| Target | 30 | 40 | ~800 posts | Rich |
| Ideal | 50 | 50 | ~1,500 posts | Dense |

We are operating at 2.7% of the ideal interaction density.

---

### Step 5: Report and Prediction (THE BIGGEST PROBLEM)

This is where the pipeline breaks down most severely. Understanding this step is critical.

**Current flow:**

```
Simulation produces: 40 posts across 3 agents over 15 rounds
                ↓
Report agent reads all posts → writes a prose summary
                ↓
Prose summary says: "The simulation revealed mixed sentiment
with some agents expressing optimism about diplomatic progress
while others raised concerns about historical precedent..."
                ↓
SEPARATE LLM call reads this prose → outputs "25%"
```

**What is happening:** The prediction comes from a *separate* LLM call that reads a text summary. It does not analyze the actual simulation dynamics. It reads prose and guesses a number.

**Why this is catastrophic:** The simulation data -- who said what, who changed their mind, where consensus formed, which arguments won and which lost -- is **flattened** into generic prose. Then a fresh LLM reads that prose and essentially performs the same task it could have done without any simulation at all.

Consider what this means: the entire simulation -- the knowledge graph, the agent personas, the 15 rounds of debate -- might be *completely irrelevant* to the final prediction. The number that comes out could be the same quality as simply asking GPT-4o: "What is the probability that the US and Iran reach a ceasefire by July 2025?"

If the simulation adds no signal above a direct LLM query, then PolFish's entire value proposition is an illusion.

---

## 3. The Core Problem: Prediction by Prose vs Prediction by Data

This is the most important section in this document. Everything else is secondary.

### Current Approach: Prediction by Prose

```
3 agents debate for 15 rounds
         ↓
Report agent writes:
  "The simulation revealed mixed sentiment with some agents
   expressing optimism while others raised concerns about
   historical precedent. The consensus appeared to lean
   slightly toward a positive outcome, though significant
   uncertainty remains."
         ↓
Separate LLM reads this prose
         ↓
LLM thinks: "mixed sentiment... lean slightly positive...
             significant uncertainty... I'd say... 62%?"
         ↓
Output: 62%
```

The simulation data is **compressed into vague prose**. The specific dynamics -- vote counts, opinion shifts, argument strength, consensus formation -- are **lost**. The report agent, doing its best, translates rich structured data into the kind of hedged, noncommittal language that LLMs default to. Then a second LLM reads that hedged language and produces a hedged number.

The result is that predictions cluster around 40-65% regardless of the underlying simulation dynamics. Strong signals get dampened. Weak signals get amplified. Everything regresses to the mean.

### Proposed Approach: Prediction by Data

```
50 agents debate for 40 rounds
         ↓
Quantitative analysis of raw simulation data:
  - Agent votes: 28 YES, 22 NO (56% raw sentiment)
  - Weighted by expertise: 52% YES (domain experts lean NO)
  - Opinion shifts: 8 agents moved YES → NO in rounds 20-35
  - Momentum: trending toward NO (-4% per 10 rounds)
  - Consensus strength: weak (high variance in positions)
  - Minority report: 5 "insider" agents unanimously say NO
  - Argument analysis: strongest YES arg cited 12 times,
    strongest NO arg cited 18 times
         ↓
Computed prediction: 47%
  Base:     56% (raw vote)
  Expert:   -4% (domain experts disagree)
  Momentum: -3% (late shift toward NO)
  Minority: -2% (insider signal)
         ↓
Output: 47%
```

The prediction **emerges from** the simulation data. It is not a separate LLM's interpretation of a prose summary. Every component of the prediction is traceable to specific simulation dynamics, and each component can be individually validated and tuned.

### Why This Matters

The difference between these two approaches is the difference between a thermometer and a person who touches the wall and says "seems warm."

With Prediction by Data:
- The prediction is **decomposable** -- you can see exactly which factors contributed what
- The prediction is **tunable** -- if expert weighting is too aggressive, adjust the coefficient
- The prediction is **auditable** -- every number traces back to simulation events
- The prediction is **improvable** -- fix a specific factor, measure the change

With Prediction by Prose:
- The prediction is a black box
- You cannot tell if the simulation helped at all
- You cannot isolate which improvements matter
- You are trusting an LLM to do quantitative reasoning from qualitative text

---

## 4. Weakness-by-Weakness Analysis

| # | Weakness | Status | What Was Implemented | Impact on Accuracy |
|---|----------|--------|---------------------|-------------------|
| 1 | Seed quality | DONE | Improved seed generator: 13,600+ chars per seed, 10 entity types extracted, multi-source aggregation with DuckDuckGo articles | **HIGH** (+3-5%) |
| 2 | Knowledge graph size | DONE | Ontology extraction now produces richer graphs from the expanded seed documents; entity type diversity (10 types) drives more knowledge graph nodes and edges | **HIGH** (+2-4%) |
| 3 | Agent count | DONE | Default increased from 3 to configurable (10+ agents). `MAX_SIMULATION_ROUNDS` env var controls rounds (default 40). More agents = more crowd wisdom | **HIGH** (+3-5%) |
| 4 | Agent diversity | DONE | Agent profiles now derived from diverse entity types (politicians, analysts, traders, activists, institutions, etc.) rather than generic "Analyst/Observer/Expert" titles. Economic archetypes embedded in seed templates | MEDIUM (+2-3%) |
| 5 | Simulation rounds | DONE | Default increased from 15 to 40 rounds via `MAX_SIMULATION_ROUNDS=40`. Allows opinion convergence in rounds 25-35 as MiroFish research suggested | MEDIUM (+1-2%) |
| 6 | Prediction method | DONE | `SimulationAnalyzer` extracts quantitative predictions from raw SQLite data (sentiment counts, engagement weighting, temporal momentum, expert-weighted votes). `MethodTracker` auto-blends LLM and quantitative predictions with self-adjusting weights based on resolved outcomes | **CRITICAL** (+5-10%) |

**Important caveat:** Accuracy impact estimates are hypotheses, not measurements. These are educated guesses based on the Monte Carlo results and general principles of crowd wisdom. Every estimate needs empirical validation.

**Cumulative potential:** If all improvements are additive (they probably are not -- diminishing returns are real), the total accuracy gain could be +16-29%. More realistically, accounting for overlap and diminishing returns, **+8-12%** is a reasonable expectation.

The Monte Carlo research showed that going from 52% to 60% accuracy transforms PolFish from a break-even system to a profitable one. An 8-12% improvement on a 50-53% base would put us squarely in the 58-65% range -- hedge fund territory.

---

## 5. The Agent Diversity Problem

### Why 3 Generic Agents Cannot Simulate a Prediction Market

Prediction markets are not debates. They are *markets*. The price is not determined by the best argument -- it is determined by the interaction of heterogeneous participants with different information, different models, different risk tolerances, and different time horizons.

Real Polymarket participants include:

**Whale traders** -- Bet $100K+, move markets, often have insider-adjacent information or superior analysis. They do not react to headlines; they react to things the headlines have not covered yet. In a simulation, these agents should have access to deeper information and should express high conviction.

**Retail bettors** -- Small bets ($10-100), follow trends, emotionally reactive. They read the top headline and form an instant opinion. They are the noise in the market, but in aggregate they carry signal because they represent mainstream sentiment.

**Quant analysts** -- Use historical base rates, statistical models, and pattern matching. They do not care about narratives. They ask: "What is the base rate for ceasefire agreements in similar geopolitical contexts?" and bet accordingly.

**Domain experts** -- For Iran markets: diplomats, military analysts, regional journalists, sanctions lawyers. They know things that generalists do not. Their signal is high but their sample size is small.

**Contrarians** -- Systematically bet against consensus. They are wrong most of the time, but when they are right, they are spectacularly right. Their role in the simulation is to stress-test the majority opinion.

**Momentum traders** -- Follow price movements, not fundamentals. They do not care *why* the price is moving, only that it *is* moving. In a simulation, they amplify trends.

**News traders** -- React instantly to headlines. First to move, often wrong on the second-order effects. They represent the market's immediate reaction to information.

**Long-term holders** -- Bet early based on deep analysis, do not change position regardless of short-term noise. They represent conviction capital.

Each group has **different information**, **different incentives**, and **different biases**. The interaction between these groups is what makes markets efficient. A whale's large bet draws contrarian interest. A news trader's panic selling creates buying opportunities for quants. A domain expert's quiet accumulation signals to attentive momentum traders.

Our 3 "Analyst/Observer/Expert" agents are three well-meaning generalists having a polite conversation. There is no tension, no information asymmetry, no genuine disagreement rooted in different worldviews. The simulation converges not because truth has been found, but because there was never any real disagreement to resolve.

---

## 6. The Simulation-to-Prediction Gap

### What the Simulation Produces

MiroFish simulation generates rich, structured data:

- **Every agent's post** -- full text, timestamp, platform (Twitter/Reddit/etc.)
- **Reactions** -- likes, replies, reposts (simulated engagement metrics)
- **Agent-to-agent interactions** -- who responded to whom, agreement/disagreement
- **Temporal dynamics** -- how the conversation evolved over rounds

### What the Report Captures

The report agent compresses all of this into:

- A prose summary of "key themes"
- A few direct quotes from agents
- Generic analysis ("mixed sentiment", "cautious optimism", "divergent views")

### What is Lost

| Signal | Available in Simulation | Captured in Report |
|--------|------------------------|-------------------|
| Vote distribution (YES/NO/NEUTRAL) | Yes, from post analysis | No -- flattened to "mixed" |
| Opinion trajectories over time | Yes, from sequential posts | No -- temporal data lost |
| Argument strength (which args convinced others) | Yes, from reply patterns | No -- reduced to "key themes" |
| Consensus dynamics (converge vs diverge?) | Yes, from round-over-round analysis | Partially -- vague qualitative |
| Agent expertise weighting | Yes, from persona metadata | No -- all agents treated equally |
| Minority dissent signals | Yes, from outlier posts | No -- drowned in summary |
| Momentum and trend direction | Yes, from temporal analysis | No -- snapshot, not trajectory |

This is like having a room of 50 experts debate for 2 hours, then asking the secretary "so what happened?" and getting back: "They discussed various perspectives. Some were optimistic, others less so. The mood was cautiously positive." All the nuance, the turning points, the minority insights, the argument dynamics -- gone. Compressed into the informational equivalent of a shrug.

The prediction LLM then reads this shrug and produces a number. It is doing its best, but its best is not very good when the input is this impoverished.

---

## 7. Proposed Improvements (Phased)

### Phase 1: Quick Wins (Config Changes, No Code)

**Change:** Increase simulation rounds from 15 to 40.

**Rationale:** This alone gives agents more time to evolve opinions, challenge each other, and reach considered positions rather than snap judgments. In MiroFish research, convergence typically happens between rounds 25-35. At 15 rounds, we are cutting the debate off before it reaches its most informative phase.

**Cost impact:** ~2x more simulation tokens ($0.30 per prediction becomes ~$0.60)

**Estimated accuracy impact:** +1-2%

**Risk:** Low. Worst case, we spend slightly more per prediction for the same quality. The pipeline already supports arbitrary round counts.

---

### Phase 2: Richer Seeds (Moderate Code Changes)

**Changes:**
- Add multiple news sources (Google News API, NewsAPI, Reddit search)
- Include Wikipedia context for background on key entities
- Add historical data where relevant (base rates, similar past events)
- Target: 5,000-10,000 words per seed document

**Rationale:** Better inputs produce better outputs. An agent that knows the historical base rate for ceasefire agreements (roughly 30% succeed on first attempt) will reason very differently from one that only knows this morning's headline.

**Cost impact:** Minimal. Seed generation is mostly web scraping and API calls, not LLM tokens. Adding $0.02 of search API cost per prediction is noise.

**Estimated accuracy impact:** +3-5%

**Risk:** Medium. More sources means more noise alongside more signal. Need to be selective about source quality. Also introduces dependency on external APIs that may rate-limit or go down.

---

### Phase 3: More and Better Agents (Moderate Code Changes)

**Changes:**
- Increase entity extraction to produce 20-30 entities from the knowledge graph
- Create agent templates for economic archetypes (bull, bear, analyst, retail, whale, quant, contrarian, domain expert)
- Mix domain-specific agents with market-behavior agents
- Assign different information access levels to different agent types

**Rationale:** Crowd wisdom requires a crowd. Three agents is a conversation; thirty agents is a market. The Wisdom of Crowds effect (Galton's ox-weighing experiment, 1906) requires independent, diverse estimators whose errors cancel. Three homogeneous agents do not meet any of these criteria.

**Cost impact:** ~3x more profile generation tokens, ~5x more simulation tokens. Per-prediction cost goes from ~$0.60 (post Phase 1) to ~$2.00.

**Estimated accuracy impact:** +3-5%

**Risk:** Medium. More agents means more LLM calls, which means more latency and more opportunities for individual agent failures to break the pipeline. Need robust error handling.

---

### Phase 4: Quantitative Prediction Extraction (Significant Code Changes)

**Changes:**
- After simulation, analyze raw simulation data instead of prose report
- Count agent positions (YES/NO/NEUTRAL) from post content
- Track opinion shifts over rounds (who changed their mind and when)
- Weight positions by agent persona expertise
- Detect momentum (which direction is sentiment trending in late rounds?)
- Identify minority signals (what do high-expertise dissenting agents say?)
- Compute prediction from data, not from LLM interpretation

**Implementation sketch:**

```python
def extract_prediction(simulation_data, agent_profiles):
    # Step 1: Classify each agent's final position
    positions = classify_positions(simulation_data)  # {agent_id: YES/NO/NEUTRAL}

    # Step 2: Raw vote
    raw_yes = sum(1 for p in positions.values() if p == "YES")
    raw_pct = raw_yes / len(positions)

    # Step 3: Expertise weighting
    weighted_pct = weighted_vote(positions, agent_profiles)

    # Step 4: Momentum (last 10 rounds vs first 10 rounds)
    momentum = calculate_momentum(simulation_data)

    # Step 5: Consensus strength (variance in positions)
    consensus = calculate_consensus_strength(simulation_data)

    # Step 6: Minority signal (high-expertise dissent)
    minority = minority_report(positions, agent_profiles)

    # Step 7: Compose prediction
    prediction = (
        weighted_pct
        + momentum_adjustment(momentum)
        + minority_adjustment(minority)
    )

    return {
        "prediction": clamp(prediction, 0.03, 0.97),
        "raw_vote": raw_pct,
        "expert_weighted": weighted_pct,
        "momentum": momentum,
        "consensus_strength": consensus,
        "minority_signal": minority,
        "decomposition": "fully auditable"
    }
```

**Rationale:** This is the single highest-impact change. Instead of losing 90% of simulation signal through prose compression, we extract structured data directly. Every component of the prediction is traceable, tunable, and auditable.

**Cost impact:** Minimal. Analysis is computation, not LLM calls. Might actually *reduce* cost by eliminating the separate prediction LLM call.

**Estimated accuracy impact:** +5-10% (the single biggest lever)

**Risk:** High implementation complexity. Classifying agent positions from free-text posts is itself an NLP problem (though a much simpler one than the full prediction task). The weighting coefficients need tuning. But the upside is enormous.

---

### Phase 5: Simulated Prediction Market (Ambitious, Future)

**Changes:**
- Instead of simulating Twitter/Reddit discussions, simulate an actual betting market
- Agents place simulated bets (with budgets, position limits, and market impact)
- The equilibrium price IS the prediction
- Agents can see each other's positions and react to price movements
- Market microstructure effects (bid-ask spread, liquidity, momentum) emerge naturally

**Rationale:** This is the ultimate form: a prediction market simulating a prediction market. Instead of extracting a probability from debate dynamics, the probability emerges from market dynamics -- exactly the same mechanism that makes real prediction markets work.

**Cost impact:** Significant engineering investment. Months of development.

**Estimated accuracy impact:** Potentially transformative. This is where PolFish could genuinely achieve 60%+ accuracy, because the simulation would be structurally isomorphic to the thing it is predicting.

**Risk:** Very high. Building a realistic market simulator with heterogeneous agents, realistic microstructure, and emergent price discovery is a research-grade problem. But the payoff is correspondingly large.

---

## 8. How to Validate Each Improvement

Improving the pipeline without measuring the impact is just hope. For each phase, we need a rigorous validation protocol.

### Method: Controlled A/B Testing

1. Select 5 resolved Polymarket markets with known outcomes
2. Run each market through the **old** pipeline and the **new** pipeline
3. Compare on four metrics:

**Metric 1: Prediction Specificity**
Are the numbers more varied? If all 5 predictions cluster between 55-65%, the pipeline is not extracting real signal -- it is defaulting to the LLM's "uncertainty prior." A good pipeline should produce predictions that range from 15% to 85% depending on the market.

**Metric 2: Prediction Consistency**
Run each market 3 times. Do we get similar numbers? If "Iran ceasefire" produces 25% on Monday, 62% on Wednesday, and 41% on Friday, the pipeline is noisy. Consistency is a prerequisite for accuracy.

**Metric 3: Prediction Direction**
Does the pipeline correctly identify overpriced and underpriced markets? If the market price is 70% and the true outcome is NO, does PolFish predict below 50%? Direction matters more than magnitude in early testing.

**Metric 4: Calibration (Long-Term)**
Over 50+ resolved markets, do events predicted at 30% happen about 30% of the time? This is the gold standard (Brier score), but it requires patience and volume.

### Validation Schedule

| Phase | Validation Method | Minimum Sample | Timeline |
|-------|------------------|----------------|----------|
| Phase 1 (more rounds) | A/B on 5 markets, 3 runs each | 15 predictions | 1 week |
| Phase 2 (richer seeds) | A/B on 5 markets, 3 runs each | 15 predictions | 2 weeks |
| Phase 3 (more agents) | A/B on 10 markets, 3 runs each | 30 predictions | 3 weeks |
| Phase 4 (quant extraction) | A/B on 10 markets, 5 runs each | 50 predictions | 4 weeks |
| Phase 5 (market sim) | Full backtest on 95 resolved markets | 95 predictions | Ongoing |

---

## 9. The Bottom Line

### Current State (All 6 Weaknesses Addressed)

All six identified weaknesses have been implemented. The pipeline now operates with:

```
BEFORE (original pipeline):
  3 agents x 15 rounds x thin seeds + prose-only extraction
  = ~52% accuracy (estimated)
  Monte Carlo says: break-even, barely profitable

AFTER (current pipeline):
  10+ agents x 40 rounds x rich seeds (13,600+ chars, 10 entity types)
  + dual extraction (LLM + quantitative from SQLite)
  + self-adjusting method blend via MethodTracker
  = estimated 58-62% accuracy range (empirical validation ongoing)

TARGET STATE (further scaling):
  50 agents x 50 rounds x rich seeds + quantitative extraction
  Monte Carlo target: +$1,244 avg P&L per 50 bets, P(Profit): 87%
```

### What Was Built

| Component | Module | Purpose |
|-----------|--------|---------|
| Quantitative Analyzer | `analyzer/simulation_analyzer.py` | Extracts predictions from raw SQLite simulation data |
| Method Tracker | `analyzer/method_tracker.py` | Compares LLM vs quant accuracy, auto-adjusts blend weights |
| Monte Carlo Simulator | `monte_carlo/simulator.py` | Portfolio viability analysis with parameter sweeps |
| Overnight Runner | `overnight/runner.py` | Crash-safe batch predictions with atomic checkpoints |
| Rolling Loop | `overnight/runner.py` (RollingLoop) | Continuous trading loop with budget caps |
| State Manager | `overnight/state.py` | Atomic state writes for crash recovery |

### Priority Ranking (Original -- All Completed)

The original priority ranking was:

1. **Quantitative prediction extraction (Phase 4)** -- DONE. `SimulationAnalyzer` + `MethodTracker` now extract and blend predictions from both prose reports and raw simulation data.

2. **More agents + more rounds (Phases 1 and 3 combined)** -- DONE. Default rounds increased to 40. Agent diversity improved through entity type extraction (10 types).

3. **Richer seeds (Phase 2)** -- DONE. Seeds now produce 13,600+ characters with structured entity sections, multiple news sources, and explicit contrarian framing.

### Next Steps

- Run controlled A/B validation on 50+ resolved markets to measure actual accuracy improvement
- Scale to 30-50 agents for maximum crowd wisdom effect (currently 10 default)
- Implement Phase 5: simulated prediction market (agents place bets, equilibrium price = prediction)
- Tune MethodTracker blend weights based on accumulated resolved market data

---

## Appendix: Analogies Summary

For quick reference, the analogies used in this document and what they map to:

| Analogy | Pipeline Step | Point |
|---------|-------------|-------|
| "Debating geopolitics after reading three tweets" | Seed document | Thin inputs produce thin reasoning |
| "Solving a murder mystery with a sticky note" | Knowledge graph | Insufficient structure for complex problems |
| "Three copies of the same debate guest" | Agent personas | No diversity means no real disagreement |
| "First 10 minutes of a 2-hour debate" | Simulation rounds | Cutting short before convergence |
| "Asking the secretary what happened" | Report prose | Lossy compression of rich data |
| "A thermometer vs touching the wall" | Prose vs data prediction | Quantitative vs qualitative extraction |
| "Roulette wheel slightly tilted" | Current accuracy | Edge exists but barely |
