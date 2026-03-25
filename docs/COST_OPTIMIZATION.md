# Cost Optimization

This guide covers token usage, model pricing, preset comparisons, and strategies for reducing API costs while maintaining prediction quality.

## Token Usage Per Pipeline Stage

The following estimates are based on observed MiroFish runs with default settings (15 rounds, 10 agents):

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

### Cost Per Single Deep Prediction (15 rounds, 10 agents)

| Preset | Cost | Breakdown |
|--------|------|-----------|
| **cheapest** | $0.02 | All DeepSeek -- minimum possible cost |
| **budget** | $0.03 | DeepSeek prep + GPT-4o-mini sim/report |
| **gemini** | $0.03 | All Gemini Flash -- fast and cheap |
| **balanced** | $0.42 | DeepSeek prep + Gemini profiles + GPT-4o sim/report |
| **premium** | $0.54 | DeepSeek prep + Gemini profiles + Claude sim + GPT-4o report |
| **best** | $0.58 | All GPT-4o -- maximum quality |

### Batch Cost Projections

| Preset | 1 prediction | 10 predictions | 50 predictions | 100 predictions |
|--------|-------------|---------------|----------------|-----------------|
| **cheapest** | $0.02 | $0.20 | $1.00 | $2.00 |
| **budget** | $0.03 | $0.30 | $1.50 | $3.00 |
| **gemini** | $0.03 | $0.30 | $1.50 | $3.00 |
| **balanced** | $0.42 | $4.20 | $21.00 | $42.00 |
| **premium** | $0.54 | $5.40 | $27.00 | $54.00 |
| **best** | $0.58 | $5.80 | $29.00 | $58.00 |

### Balanced vs All GPT-4o Savings

The balanced preset achieves ~27% savings over all-GPT-4o by using cheap models for the preprocessing stages (ontology, graph, profiles) where quality difference is minimal.

```
Balanced:  ontology($0.001) + graph($0.002) + profiles($0.002) + sim($0.300) + report($0.118) = $0.42
All GPT4o: ontology($0.028) + graph($0.060) + profiles($0.073) + sim($0.300) + report($0.118) = $0.58

Savings: $0.16/prediction (27.3%)
At 50 predictions: $8.00 saved
At 100 predictions: $16.00 saved
```

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
| Production autopilot | `balanced` | Sustainable for 100+ predictions/week |

### When to Use Multiple Variants

Running multiple seed variants (2-5) with ensemble averaging improves prediction quality but multiplies cost linearly:

```
3 variants x $0.42/prediction = $1.26 total
```

Recommendation: Use 1 variant for quick screening, 3 variants for high-conviction deep predictions.

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

### 7. Leverage Free Tiers

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

1. Start with the `cheapest` or `gemini` preset during development
2. Switch to `balanced` for production (best quality/cost ratio)
3. Set `PREDICTOR_MAX_ROUNDS=10` unless you need maximum depth
4. Set `PREDICTOR_VARIANTS=1` for autopilot, `3` for manual high-conviction predictions
5. Configure autopilot budget cap: `max_cost_per_cycle: 5.0`
6. Monitor costs via `GET /api/polymarket/cost/estimate` after config changes
7. Review `GET /api/polymarket/cost/compare` periodically to check if a cheaper preset meets your quality needs
