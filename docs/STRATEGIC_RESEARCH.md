# Prediction Market Trading Systems: Strategic Research Report for PolFish

## Executive Summary

This report analyzes the competitive landscape, technical approaches, and best practices for AI-powered prediction market trading systems. Based on extensive research across existing systems, academic papers, and practitioner experience.

**Key findings:**
1. Most profitable Polymarket bots make money from **arbitrage and market-making**, not superior predictions
2. Multi-agent debate provides **ensemble benefits equivalent to simple voting** — the debate mechanism itself may not add value
3. Local 14B models are sufficient for agent simulation; frontier models only needed for final prediction extraction
4. You need **200+ resolved predictions minimum** to distinguish skill from luck
5. Realistic sustainable edge on well-covered markets is **1-3%**; niche markets offer **5-15%** but with limited capital deployment

## 1. Existing Prediction Market Trading Systems

### 1.1 Polymarket Official Agents Framework
- **URL**: github.com/Polymarket/agents
- **Method**: RAG-augmented single LLM call. ChromaDB for context, LLM for probability.
- **Limitation**: No ensemble, no backtesting, no calibration. Framework, not strategy.

### 1.2 Polystrat / Olas (Valory AG)
- **Performance**: 4,200+ trades in first month, up to 376% returns on individual trades
- **Reality**: Returns driven largely by arbitrage (buying YES+NO when combined < $1), not superior forecasting
- **Key stat**: 37% of AI agents show positive P&L vs less than half that for humans

### 1.3 OpenClaw Trading Bot
- **Performance**: $115,000 in a single week on Polymarket
- **Method**: Autonomous agent with modular "skills" plugins
- **Reality**: Primarily exploits structural inefficiencies, not prediction quality

### 1.4 Fully Autonomous Polymarket AI Trading Bot
- **URL**: github.com/dylanpersonguy/Fully-Autonomous-Polymarket-AI-Trading-Bot
- **Method**: Multi-model ensemble (GPT-4o, Claude, Gemini) with 15+ risk checks
- **Open source**: Yes. No published track record.

### 1.5 TradingAgents (UCLA/MIT) — Most Similar to PolFish
- **URL**: github.com/TauricResearch/TradingAgents
- **Method**: 7 specialized agent roles: Fundamentals Analyst, Sentiment Analyst, News Analyst, Technical Analyst, Bull Researcher, Bear Researcher, Risk Manager, Fund Manager
- **Key insight**: Structured debate between bull and bear researchers
- **Limitation**: Stock trading, not prediction markets. Backtest only.

### 1.6 Market Statistics
- 30%+ of Polymarket wallets use AI agents
- 14 of 20 most profitable wallets are bots
- Arbitrage extracted ~$40M from Polymarket in 2024-2025
- Single-market mispricings resolve in median 3.6 seconds
- Dynamic taker fees now ~1.56%

## 2. Agent Swarm Systems: Does Debate Actually Help?

### The Evidence FOR Multi-Agent Debate:
- Du et al. (2023): Multi-agent debate significantly improves mathematical reasoning
- Knowledge-enhanced debate: State-of-the-art on 6 datasets vs single-agent methods

### The Evidence AGAINST:
- **Critical 2025 finding**: Simple majority voting accounts for most gains attributed to debate. Debate induces a martingale — expected belief remains unchanged over rounds.
- MedAgentBoard: Multi-agent systems do NOT consistently outperform advanced single LLMs
- Completeness vs correctness trade-off: better task completion but not better accuracy

### What This Means for PolFish:
**The ensemble is valuable, the debate mechanism may not be.** Running 3 independent predictions and averaging may be roughly equivalent to having 40 agents "debate." This needs to be empirically tested.

## 3. Local Tools and Cost Efficiency

### Local Model Quality vs Cloud
| Model | Quality vs GPT-4o | Hardware | Cost |
|-------|-------------------|----------|------|
| Llama 3.1 8B | 60-70% | 8GB VRAM | $0 |
| Qwen 2.5 14B | 80-90% | 16GB VRAM | $0 |
| Qwen3.5 27B | Matches GPT-5 Mini | 24GB VRAM | $0 |
| GPT-4.5 (cloud) | Brier 0.101 | Cloud | ~$2.50/1M |
| Superforecasters | Brier 0.081 | Human | N/A |

### Zep Alternatives
| Alternative | Self-Hosted | Best For |
|------------|-------------|----------|
| **Hindsight** | Yes, no external DB | Clearest Zep replacement |
| **LanceDB** | Yes, embedded | Simplest vector DB |
| **Mem0** | Yes + cloud option | Good balance |
| **SuperLocalMemory** | Fully local | Zero-cloud option |

### Token Optimization (60-80% cost reduction possible):
- Prompt caching: ~73% reduction on repeated system prompts
- Output control: max_tokens limits + "Answer in 50 words"
- Model routing: cheap model for data, expensive for reasoning
- Semantic caching: cache responses for similar queries

## 4. Testing Best Practices

### Minimum Sample Sizes
- At 5-10% edge: **minimum 200 resolved predictions**
- At 2-3% edge: **500-1000+ predictions needed**
- With only 30-50 resolved bets: **genuinely cannot distinguish skill from luck**

### Backtesting Methods
- **Walk-Forward Optimization**: Gold standard. Train on window, test on next, roll forward.
- **Purged K-Fold**: Eliminates data leakage between train/test.
- Guard against: look-ahead bias, data snooping, survivorship bias

### Measuring Edge vs Luck
- **Brier Skill Score** = 1 - (your Brier / reference Brier). Reference = always predicting market price.
- **Calibration plots**: bin predictions into deciles, compare predicted vs observed.
- **Bootstrap**: Resample 10,000 times, compute 95% CI on Brier score.
- **Paired Diebold-Mariano test**: Compare two forecasting models properly.

### Historical Data Sources
- Polymarket Gamma API (free, 1,000 calls/hour)
- PolymarketData (bulk S3 exports, Python SDK)
- PolyBackTest (full order book at sub-second resolution)
- Telonex (tick-level, 500K+ markets, 20B+ data points)

## 5. Strategic Recommendations for PolFish

### Architecture
| Decision | Recommendation | Confidence |
|----------|---------------|------------|
| Keep multi-agent simulation? | Keep but A/B test against single LLM | Medium |
| Agent debate vs simple ensemble? | Simple ensemble likely equivalent | High |
| Local vs cloud models? | Local 14B for simulation, cloud for final prediction | High |
| Replace Zep? | Yes — LanceDB + SQLite or Hindsight | High |
| Minimum bets for validation? | 200+ resolved predictions | High |
| Primary edge source? | Niche/low-liquidity markets | High |
| Real-time vs batch? | Batch predictions, real-time execution only | High |

### The Critical A/B Test
Before investing more in the simulation pipeline, run:
- **(A)** Full MiroFish simulation (40 agents, 40 rounds, graph, report)
- **(B)** Single GPT-4o call with same context (market data + news + seed)
- Measure: Brier score on 100+ resolved markets
- If A doesn't beat B significantly → simplify

### Cost Efficiency Path
Current: ~$8.50/prediction (balanced preset, 64 agents)
Target: ~$0.05-0.15/prediction
How: Local 14B for simulation + DeepSeek for report + eliminate Zep

### Honest Limitations
- Only 5% of professional fund managers generate positive alpha over 6 years
- Prediction markets are arguably MORE efficient than equity markets for covered events
- Realistic sustainable edge: 1-3% on mainstream, 5-15% on niche
- LLM-superforecaster parity projected for late 2026
- No published evidence that multi-agent simulation beats a well-prompted single LLM for probability estimation

---

Sources: Polymarket docs, CoinDesk, TradingView, arXiv papers (Du et al. 2023, TradingAgents 2024, IMDEA 2025), ForecastBench, QuantPedia, QuantInsti, various GitHub repos.
