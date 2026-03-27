# Cost Optimization

This guide covers token usage, model pricing, preset comparisons, and strategies for reducing API costs while maintaining prediction quality.

## Token Usage Per Pipeline Stage

The following estimates are based on observed MiroFish runs with default settings (40 rounds, 10 agents). Earlier versions defaulted to 15 rounds; the current default of 40 rounds was chosen to allow agent opinions to converge (see [Prediction Pipeline Research](PREDICTION_PIPELINE_RESEARCH.md)).

| Stage | Input Tokens | Output Tokens | Total Tokens | Purpose |
|-------|-------------|---------------|--------------|---------|
| **Ontology** | 3,000 | 2,000 | 5,000 | Parse seed document, extract entities and relationships |
| **Graph** | 8,000 | 4,000 | 12,000 | Build knowledge graph from ontology |
| **Profiles** | 5,000 | 6,000 | 11,000 | Generate AI agent personality profiles |
| **Simulation** | 40,000 | 20,000 | 60,000 | Run multi-round agent debates (15 rounds x 10 agents) |
| **Report** | 15,000 | 8,000 | 23,000 | Synthesize simulation into analysis report |
| **Total** | **71,000** | **40,000** | **111,000** | |

The simulation stage dominates at ~54% of total tokens. Token usage scales linearly with rounds and agents:

```
simulation_input = 40,000 * (rounds / 15) * (agents / 10)
simulation_output = 20,000 * (rounds / 15) * (agents / 10)
```

---

## Model Pricing Database

All prices are per 1 million tokens (USD):

| Model | Provider | Input | Output | Notes |
|-------|----------|-------|--------|-------|
| `gpt-4o` | OpenAI | $2.50 | $10.00 | Best quality general-purpose |
| `gpt-4o-mini` | OpenAI | $0.15 | $0.60 | Good quality, very cheap |
| `deepseek-chat` | DeepSeek | $0.14 | $0.28 | Cheapest option, good for preprocessing |
| `deepseek-reasoner` | DeepSeek | $0.55 | $2.19 | Chain-of-thought reasoning |
| `gemini-2.0-flash` | Google | $0.075 | $0.30 | Fast, cheap, free tier available |
| `gemini-2.0-flash-lite` | Google | $0.075 | $0.30 | Even faster variant |
| `gemini-2.5-flash` | Google | $0.15 | $0.60 | Latest Gemini flash model |
| `gemini-2.5-pro` | Google | $1.25 | $10.00 | Premium Gemini model |
| `claude-sonnet-4-20250514` | Anthropic | $3.00 | $15.00 | Strong reasoning, most expensive |
| `claude-haiku-3.5` | Anthropic | $0.80 | $4.00 | Fast Claude model |
| `mistral-small-latest` | Mistral | $0.10 | $0.30 | Cheap European alternative |
| `mistral-large-latest` | Mistral | $2.00 | $6.00 | Premium Mistral |
| `llama-3.1-70b-versatile` | Groq | $0.59 | $0.79 | Open-source, very fast inference |
| `llama-3.1-8b-instant` | Groq | $0.05 | $0.08 | Smallest/cheapest option |

---

## Preset Cost Comparison

### Cost Per Single Deep Prediction (40 rounds, 10 agents)

| Preset | Cost | Breakdown |
|--------|------|-----------|
| **local** | $0.00 | All Ollama (llama3.1:8b) -- zero API cost |
| **cheapest** | $0.02 | All DeepSeek -- minimum possible cloud cost |
| **budget** | $0.03 | DeepSeek prep + GPT-4o-mini sim/report |
| **gemini** | $0.03 | All Gemini Flash -- fast and cheap |
| **hybrid_local** | $0.12 | Ollama for all prep stages + GPT-4o for report only |
| **balanced** | $0.42 | DeepSeek prep + Gemini profiles + GPT-4o sim/report |
| **premium** | $0.54 | DeepSeek prep + Gemini profiles + Claude sim + GPT-4o report |
| **best** | $0.58 | All GPT-4o -- maximum quality |

### Batch Cost Projections

| Preset | 1 prediction | 10 predictions | 50 predictions | 100 predictions |
|--------|-------------|---------------|----------------|-----------------|
| **local** | $0.00 | $0.00 | $0.00 | $0.00 |
| **cheapest** | $0.02 | $0.20 | $1.00 | $2.00 |
| **budget** | $0.03 | $0.30 | $1.50 | $3.00 |
| **gemini** | $0.03 | $0.30 | $1.50 | $3.00 |
| **hybrid_local** | $0.12 | $1.20 | $6.00 | $12.00 |
| **balanced** | $0.42 | $4.20 | $21.00 | $42.00 |
| **premium** | $0.54 | $5.40 | $27.00 | $54.00 |
| **best** | $0.58 | $5.80 | $29.00 | $58.00 |

### High Agent Count Cost Table (50 agents x 40 rounds)

Running with more agents increases information density at the cost of more simulation tokens. The `cheapest` and `gemini` presets make high agent counts affordable:

| Preset | 10 agents | 30 agents | 50 agents | Notes |
|--------|-----------|-----------|-----------|-------|
| **cheapest** | $0.02 | $0.06 | $0.10 | All DeepSeek -- scales cheaply |
| **budget** | $0.03 | $0.08 | $0.14 | GPT-4o-mini sim stays cheap |
| **gemini** | $0.03 | $0.08 | $0.14 | Gemini free tier may cap daily |
| **balanced** | $0.42 | $1.10 | $1.80 | GPT-4o sim dominates cost |
| **premium** | $0.54 | $1.40 | $2.30 | Claude sim is most expensive |
| **best** | $0.58 | $1.50 | $2.50 | All GPT-4o |

**DeepSeek for simulation insight:** Running 50 agents on DeepSeek ($0.10/prediction) produces more total information than 10 agents on GPT-4o ($0.42/prediction) at a fraction of the cost. The quality-per-dollar of more agents on a cheap model can exceed fewer agents on a premium model, because crowd wisdom depends more on agent count and diversity than on individual agent intelligence.

### WEEX-Scale Agent Cost Table (40 rounds, up to 200 agents)

With the 200 agent template library (WEEX-validated composition), simulations can scale from lightweight (15 agents) to full crowd (200 agents). Cost scales linearly with agent count:

| Preset | 15 agents | 25 agents | 60 agents | 200 agents | Notes |
|--------|-----------|-----------|-----------|------------|-------|
| **cheapest** | $0.03 | $0.05 | $0.12 | $0.40 | All DeepSeek -- best value at scale |
| **budget** | $0.05 | $0.08 | $0.18 | $0.60 | GPT-4o-mini sim stays affordable |
| **gemini** | $0.05 | $0.08 | $0.18 | $0.60 | Gemini free tier may cap daily at high counts |
| **balanced** | $0.50 | $0.80 | $2.00 | $6.50 | GPT-4o sim dominates at high agent counts |
| **premium** | $0.65 | $1.00 | $2.50 | $8.00 | Claude sim most expensive at scale |

**WEEX benchmark:** Running 200 agents on the `cheapest` preset costs $3-5 per prediction (including all pipeline stages), validated against the WEEX study's composition methodology. Use `MAX_TEMPLATE_AGENTS=170` to fill the agent pool with template archetypes alongside ~30 graph-derived organic agents.

---

### Balanced vs All GPT-4o Savings

The balanced preset achieves ~27% savings over all-GPT-4o by using cheap models for the preprocessing stages (ontology, graph, profiles) where quality difference is minimal.

```
Balanced preset — per-stage cost breakdown (40 rounds, 10 agents):

Stage         Model              Input Tokens  Output Tokens  Cost
------------- ------------------ ------------- -------------- ------
Ontology      deepseek-chat       3,000         2,000         $0.001
Graph         deepseek-chat       8,000         4,000         $0.002
Profiles      gemini-2.0-flash    5,000         6,000         $0.002
Simulation    gpt-4o             107,000        53,000         $0.800  (40 rounds)
Report        gpt-4o              15,000         8,000         $0.118
------------- ------------------ ------------- -------------- ------
TOTAL                            138,000        73,000         $0.923

All GPT-4o:
TOTAL                            138,000        73,000         $1.103

Savings with balanced: $0.18/prediction (16.3%)
At 50 predictions: $9.00 saved
At 100 predictions: $18.00 saved
```

Note: With the original 15-round default, balanced cost was ~$0.42 and all-GPT-4o was ~$0.58. At 40 rounds, the simulation stage cost roughly doubles, but preprocessing savings remain the same.

---

## Choosing the Right Preset

### Decision Matrix

| If you want... | Use this preset | Why |
|----------------|----------------|-----|
| Lowest possible cost | `cheapest` | All DeepSeek at $0.02/prediction |
| Free tier only | `gemini` | Gemini has 1M free tokens/day |
| Good quality, low cost | `budget` | GPT-4o-mini is surprisingly capable at 1/17th the price |
| Best quality/cost ratio | `balanced` | Cheap preprocessing + premium simulation |
| Best reasoning quality | `premium` | Claude Sonnet excels at nuanced debate |
| Maximum accuracy | `best` | All GPT-4o for consistent quality |
| Development/testing | `cheapest` or `gemini` | Iterate fast without burning budget |
| Zero cost (local GPU) | `local` | All Ollama, $0.00/prediction, needs ~5 GB RAM |
| Local + quality reports | `hybrid_local` | Ollama prep + GPT-4o report at $0.12/prediction |
| Production autopilot | `balanced` | Sustainable for 100+ predictions/week |

### When to Use Multiple Variants

Running multiple seed variants (2-5) with ensemble averaging improves prediction quality but multiplies cost linearly:

```
3 variants x $0.42/prediction = $1.26 total
```

Recommendation: Use 1 variant for quick screening, 3 variants for high-conviction deep predictions.

---

## Ollama Local Presets

The `local` and `hybrid_local` presets use Ollama for zero-cost or near-zero-cost predictions by running open-source models on your own hardware.

### local preset ($0.00/prediction)

All five pipeline stages run on `llama3.1:8b` via Ollama. No API keys required (except Zep). Ideal for development, testing, and unlimited iteration. Quality is lower than cloud models, especially for the report stage.

### hybrid_local preset (~$0.12/prediction)

Ontology, graph, profiles, and simulation run locally on `llama3.1:8b`. Only the report stage uses GPT-4o (cloud), since report quality depends heavily on model capability. This gives a 71% cost reduction vs balanced while maintaining report quality.

```
hybrid_local — per-stage cost breakdown:

Stage         Model              Cost
------------- ------------------ ------
Ontology      llama3.1:8b (local) $0.00
Graph         llama3.1:8b (local) $0.00
Profiles      llama3.1:8b (local) $0.00
Simulation    llama3.1:8b (local) $0.00
Report        gpt-4o (cloud)      $0.12
------------- ------------------ ------
TOTAL                              $0.12
```

---

## Dynamic Cost Estimation

Cost estimates are now computed dynamically based on the active preset and model configuration, replacing the earlier hardcoded $0.42 assumption. The `CostCalculator` reads the current `PIPELINE_MODELS` config, looks up per-model token pricing from `MODEL_PRICING`, and computes per-stage costs using observed token usage baselines.

This means:
- `GET /api/polymarket/cost/estimate` reflects your actual config, not a fixed number
- Overnight runner and rolling loop use dynamic cost estimates for budget tracking
- Switching presets immediately updates all cost projections

---

## Actual Run Data

### TISZA overnight run (GPT-4o, 64 agents, 40 rounds)

A production overnight run with the `balanced` preset and 64 template-injected agents:

```
Total predictions: 20
Total cost:        $8.52
Avg cost/prediction: $0.426
Duration:          ~4 hours
Preset:            balanced (GPT-4o for simulation + report)
Agents per sim:    64 (10 organic + 25 template + graph-derived)
Rounds:            40
```

The higher-than-default agent count (64 vs 10) increased simulation token usage but the per-prediction cost remained close to the baseline $0.42 because the extra agents mostly increased simulation input tokens, which are cheaper than output tokens for GPT-4o.

---

## Cost Reduction Strategies

### 1. Reduce Simulation Rounds

The simulation stage consumes ~54% of tokens. Reducing rounds from 15 to 8 cuts simulation cost nearly in half:

```bash
PREDICTOR_MAX_ROUNDS=8
```

| Rounds | Simulation tokens | Total cost (balanced) |
|--------|------------------|-----------------------|
| 5 | 20,000 | ~$0.25 |
| 8 | 32,000 | ~$0.33 |
| 15 | 60,000 | ~$0.42 |
| 20 | 80,000 | ~$0.55 |

### 2. Use Cheap Models for Preprocessing

The ontology, graph, and profiles stages are less sensitive to model quality. DeepSeek and Gemini Flash perform nearly as well as GPT-4o for these structured tasks at 1/20th the cost.

### 3. Limit Seed Variants

Default ensemble uses 3 variants. For routine autopilot scanning, 1 variant is sufficient:

```bash
PREDICTOR_VARIANTS=1
```

### 4. Increase Edge Thresholds

Higher thresholds mean fewer deep predictions triggered, saving on expensive simulation runs:

```bash
PREDICTOR_MIN_EDGE=0.15
```

### 5. Use Quick Predictions for Screening

The quick prediction endpoint (POST `/api/polymarket/predict`) generates a seed document with news articles but does NOT run the MiroFish simulation. It costs $0.00 in API fees (only uses Polymarket's free API and DuckDuckGo search). Use it to screen markets before committing to deep predictions.

### 6. Batch Strategically

The autopilot engine has a budget cap (`max_cost_per_cycle`). Set it based on your daily budget:

```json
{
  "max_cost_per_cycle": 5.0,
  "max_deep_per_cycle": 2,
  "cost_per_deep": 4.0
}
```

### 7. Multi-Tier Thesis Grouping

The thesis system groups related markets (e.g., "Iran ceasefire by April/May/June/December") and runs ONE deep prediction per group instead of one per market. The thesis prediction is then applied to each tier using `ThesisApplier`.

**Cost savings example:**

```
BEFORE thesis grouping:
  14 individual markets x $0.42 = $5.88

AFTER thesis grouping:
  Group 1: Iran ceasefire (7 tiers)     -> 1 prediction = $0.42
  Group 2: Oil prices (6 tiers)          -> 1 prediction = $0.42
  Group 3: Eurovision winner (single)    -> 1 prediction = $0.42
  Total: 3 predictions = $1.26

Savings: $5.88 - $1.26 = $4.62 (78% reduction)
```

This is the highest-impact cost optimization because it applies multiplicatively: every multi-tier group with N markets saves (N-1) deep predictions. In practice, Polymarket frequently lists 5-10+ date tiers for major events (ceasefire deadlines, price targets, election stages), making this saving reliable.

| Scenario | Markets | Groups | Predictions | Cost (balanced) | Savings |
|----------|---------|--------|-------------|-----------------|---------|
| No grouping | 14 | 14 | 14 | $5.88 | -- |
| Light grouping | 14 | 8 | 8 | $3.36 | 43% |
| Heavy grouping | 14 | 3 | 3 | $1.26 | 78% |

### 8. Leverage Free Tiers

- **Gemini**: 15 RPM, 1M tokens/day free (enough for ~9 predictions/day with the gemini preset)
- **Groq**: 30 RPM free tier with llama models
- **DeepSeek**: New accounts get free credits

---

## ROI Analysis

### Break-Even Calculation

If your paper trading edge is E% (net ROI after all wins and losses), and each deep prediction costs C dollars:

```
Break-even predictions per profitable bet = C / (average_bet * E)
```

**Example with balanced preset ($0.42/prediction):**

| Your Edge (ROI) | Avg Bet Size | Predictions to Break Even | Annual Budget (daily) |
|------------------|-------------|---------------------------|----------------------|
| 3% | $100 | 1 bet per 0.14 predictions | $153/year |
| 5% | $100 | 1 bet per 0.084 predictions | $153/year |
| 10% | $50 | 1 bet per 0.084 predictions | $153/year |
| 3% | $50 | 1 bet per 0.28 predictions | $153/year |

The key insight: **API costs are negligible compared to bet sizes.** Even at $0.42/prediction running 1 prediction/day, you spend $153/year. A single winning $100 bet at 3% edge covers 7 predictions.

### Cost Per Signal

Not every prediction generates a tradeable signal. Typical filtering:

```
50 markets scanned (free)
 -> 10 pass quick screening (free)
 -> 3 run deep prediction ($0.42 each = $1.26)
 -> 2 generate actionable signals
 -> 1-2 bets placed

Effective cost per bet: $0.63 - $1.26
```

### Budget Planning

| Usage Level | Predictions/week | Weekly Cost (balanced) | Monthly Cost |
|-------------|------------------|------------------------|--------------|
| Light | 5 | $2.10 | $8.40 |
| Moderate | 20 | $8.40 | $33.60 |
| Heavy | 50 | $21.00 | $84.00 |
| Autopilot (4 cycles/day) | 168 | $70.56 | $282.24 |

---

## Real-Time Cost Tracking

### Check Current Config Costs

```bash
# Estimate cost for current config
curl http://localhost:5001/api/polymarket/cost/estimate

# Compare all presets
curl http://localhost:5001/api/polymarket/cost/compare

# Estimate batch cost
curl "http://localhost:5001/api/polymarket/cost/batch?num=50&rounds=15&agents=10"
```

### View Pipeline Config

```bash
curl http://localhost:5001/api/polymarket/pipeline/config
```

This shows which model is assigned to each stage, whether the API key is configured, and the per-token pricing.

---

## Cost Optimization Checklist

1. Start with the `local` or `cheapest` preset during development ($0.00-$0.02/prediction)
2. Switch to `balanced` for production (best quality/cost ratio)
3. Set `PREDICTOR_MAX_ROUNDS=10` unless you need maximum depth
4. Set `PREDICTOR_VARIANTS=1` for autopilot, `3` for manual high-conviction predictions
5. Configure autopilot budget cap: `max_cost_per_cycle: 5.0`
6. Monitor costs via `GET /api/polymarket/cost/estimate` after config changes
7. Review `GET /api/polymarket/cost/compare` periodically to check if a cheaper preset meets your quality needs
