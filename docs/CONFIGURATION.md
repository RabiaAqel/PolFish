# Configuration Guide

All configuration is done through environment variables, typically set in `MiroFish/.env`. Copy the example file to get started:

```bash
cp MiroFish/.env.example MiroFish/.env
```

## Environment Variables Reference

### Core LLM Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LLM_API_KEY` | string | `""` | Primary OpenAI API key. Used as fallback for all stages. |
| `LLM_BASE_URL` | string | `https://api.openai.com/v1` | Base URL for the primary LLM provider. |
| `LLM_MODEL_NAME` | string | `gpt-4o` | Default model name when no preset or stage override is set. |

### Provider API Keys

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DEEPSEEK_API_KEY` | string | `""` | DeepSeek API key for preprocessing stages. |
| `GEMINI_API_KEY` | string | `""` | Google Gemini API key for agent profiles. |
| `ANTHROPIC_API_KEY` | string | `""` | Anthropic Claude API key for simulation. |
| `MISTRAL_API_KEY` | string | `""` | Mistral API key. |
| `GROQ_API_KEY` | string | `""` | Groq API key for fast open-source model inference. |
| `ZEP_API_KEY` | string | `""` | Zep API key for knowledge graph memory. |

### Pipeline Preset

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PIPELINE_PRESET` | string | `balanced` | Which model preset to use. See [Presets](#pipeline-presets) below. |

### Per-Stage Model Overrides

These override the preset for individual pipeline stages. Only needed when using the `custom` preset or fine-tuning a preset.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ONTOLOGY_MODEL` | string | (from preset) | Model for ontology generation. |
| `ONTOLOGY_API_KEY` | string | (auto-resolved) | API key override for ontology stage. |
| `ONTOLOGY_BASE_URL` | string | (auto-resolved) | Base URL override for ontology stage. |
| `GRAPH_MODEL` | string | (from preset) | Model for knowledge graph building. |
| `GRAPH_API_KEY` | string | (auto-resolved) | API key override for graph stage. |
| `GRAPH_BASE_URL` | string | (auto-resolved) | Base URL override for graph stage. |
| `PROFILES_MODEL` | string | (from preset) | Model for agent profile generation. |
| `PROFILES_API_KEY` | string | (auto-resolved) | API key override for profiles stage. |
| `PROFILES_BASE_URL` | string | (auto-resolved) | Base URL override for profiles stage. |
| `SIMULATION_MODEL` | string | (from preset) | Model for running the multi-agent debate. |
| `SIMULATION_API_KEY` | string | (auto-resolved) | API key override for simulation stage. |
| `SIMULATION_BASE_URL` | string | (auto-resolved) | Base URL override for simulation stage. |
| `REPORT_MODEL` | string | (from preset) | Model for report generation. |
| `REPORT_API_KEY` | string | (auto-resolved) | API key override for report stage. |
| `REPORT_BASE_URL` | string | (auto-resolved) | Base URL override for report stage. |

**How auto-resolution works:** When you set `SIMULATION_MODEL=gemini-2.5-flash`, the system looks up `gemini-2.5-flash` in the `MODEL_PRICING` database, finds `provider: "gemini"`, and auto-resolves the API key from `GEMINI_API_KEY` and the base URL from the provider defaults. You only need `*_API_KEY` and `*_BASE_URL` overrides if you want to point at a custom endpoint.

### Predictor Parameters

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PREDICTOR_MAX_ROUNDS` | int | `15` | Maximum simulation rounds per prediction. |
| `PREDICTOR_VARIANTS` | int | `3` | Number of seed variants for ensemble predictions. |
| `PREDICTOR_MIN_EDGE` | float | `0.10` | Minimum edge (as decimal) to generate a signal. |
| `PREDICTOR_MIN_VOLUME` | float | `10000` | Minimum market volume (USD) for signal generation. |

### Infrastructure

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MIROFISH_API_URL` | string | `http://localhost:5001/api` | URL of the MiroFish backend API. |

---

## Pipeline Presets

Set `PIPELINE_PRESET` in your `.env` file to switch between pre-configured model combinations.

### Preset Comparison

| Preset | Ontology | Graph | Profiles | Simulation | Report | Cost/prediction |
|--------|----------|-------|----------|------------|--------|-----------------|
| `balanced` | deepseek-chat | deepseek-chat | gemini-2.0-flash | gpt-4o | gpt-4o | ~$0.42 |
| `budget` | deepseek-chat | deepseek-chat | deepseek-chat | gpt-4o-mini | gpt-4o-mini | ~$0.03 |
| `premium` | deepseek-chat | deepseek-chat | gemini-2.0-flash | claude-sonnet-4 | gpt-4o | ~$0.54 |
| `cheapest` | deepseek-chat | deepseek-chat | deepseek-chat | deepseek-chat | deepseek-chat | ~$0.02 |
| `best` | gpt-4o | gpt-4o | gpt-4o | gpt-4o | gpt-4o | ~$0.58 |
| `gemini` | gemini-2.5-flash | gemini-2.5-flash | gemini-2.0-flash | gemini-2.5-flash | gemini-2.5-flash | ~$0.03 |
| `custom` | (env vars) | (env vars) | (env vars) | (env vars) | (env vars) | varies |

### Switching Presets

In your `.env` file:

```bash
# Use the budget preset for development
PIPELINE_PRESET=budget

# Or the premium preset for production
PIPELINE_PRESET=premium
```

Restart the backend after changing presets.

### Custom Preset

Set `PIPELINE_PRESET=custom` and define each stage individually:

```bash
PIPELINE_PRESET=custom
ONTOLOGY_MODEL=deepseek-chat
GRAPH_MODEL=deepseek-chat
PROFILES_MODEL=gemini-2.0-flash
SIMULATION_MODEL=claude-sonnet-4-20250514
REPORT_MODEL=gemini-2.5-flash
```

---

## Provider Setup Guides

### OpenAI (Required for balanced/best/budget presets)

1. Sign up at [platform.openai.com](https://platform.openai.com)
2. Navigate to API Keys and create a new key
3. Add billing payment method (pay-as-you-go)
4. Set in `.env`:
   ```
   LLM_API_KEY=sk-proj-...
   ```

**Models available:** `gpt-4o` ($2.50/$10.00 per 1M tokens), `gpt-4o-mini` ($0.15/$0.60 per 1M tokens)

### DeepSeek (Recommended -- cheap preprocessing)

1. Sign up at [platform.deepseek.com](https://platform.deepseek.com)
2. Create an API key in the dashboard
3. New accounts get free credits
4. Set in `.env`:
   ```
   DEEPSEEK_API_KEY=sk-...
   ```

**Models available:** `deepseek-chat` ($0.14/$0.28 per 1M tokens), `deepseek-reasoner` ($0.55/$2.19 per 1M tokens)

### Gemini (Free tier available)

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Create an API key (free tier: 15 RPM, 1M tokens/day)
3. Set in `.env`:
   ```
   GEMINI_API_KEY=AIza...
   ```

**Models available:** `gemini-2.0-flash` ($0.075/$0.30), `gemini-2.0-flash-lite` ($0.075/$0.30), `gemini-2.5-flash` ($0.15/$0.60), `gemini-2.5-pro` ($1.25/$10.00)

### Anthropic (Optional -- Claude for simulation reasoning)

1. Sign up at [console.anthropic.com](https://console.anthropic.com)
2. Create an API key
3. Add billing payment method
4. Set in `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

**Models available:** `claude-sonnet-4-20250514` ($3.00/$15.00), `claude-haiku-3.5` ($0.80/$4.00)

### Mistral (Optional)

1. Sign up at [console.mistral.ai](https://console.mistral.ai)
2. Create an API key
3. Set in `.env`:
   ```
   MISTRAL_API_KEY=...
   ```

**Models available:** `mistral-small-latest` ($0.10/$0.30), `mistral-large-latest` ($2.00/$6.00)

### Groq (Free tier available -- fast inference)

1. Sign up at [console.groq.com](https://console.groq.com)
2. Create an API key (free tier: 30 RPM)
3. Set in `.env`:
   ```
   GROQ_API_KEY=gsk_...
   ```

**Models available:** `llama-3.1-70b-versatile` ($0.59/$0.79), `llama-3.1-8b-instant` ($0.05/$0.08)

### Zep (Required for knowledge graph)

1. Sign up at [app.getzep.com](https://app.getzep.com)
2. Create a project and get the API key
3. Set in `.env`:
   ```
   ZEP_API_KEY=z_...
   ```

---

## Autopilot Configuration

The autopilot engine has its own config stored in `polymarket_predictor/data/autopilot_config.json`. You can modify it through the API or the dashboard.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_deep_per_cycle` | int | `3` | Maximum deep predictions per autopilot cycle. |
| `max_cost_per_cycle` | float | `15.0` | Budget cap in USD per cycle. |
| `min_edge_for_deep` | float | `0.05` | Minimum quick-predict edge to trigger deep prediction. |
| `min_edge_for_bet` | float | `0.03` | Minimum deep-predict edge to place a paper bet. |
| `cycle_interval_hours` | int | `6` | Hours between autopilot cycles (when running on loop). |
| `niche_focus` | bool | `true` | Prefer obscure/niche markets (less efficient = more alpha). |
| `quick_research` | bool | `false` | Fetch news articles during quick predict phase. |
| `max_markets_to_scan` | int | `50` | Maximum markets to scan per cycle. |
| `days_ahead` | float | `7.0` | Look for markets expiring within N days. Supports decimals (e.g., `0.25` = 6 hours). |
| `min_volume` | int | `500` | Minimum market trading volume (USD). |
| `cost_per_deep` | float | `4.0` | Estimated cost per deep prediction (for budget calculations). |

### Updating Autopilot Config

Via API:

```bash
curl -X PUT http://localhost:5001/api/polymarket/autopilot/config \
  -H "Content-Type: application/json" \
  -d '{"max_deep_per_cycle": 5, "min_edge_for_deep": 0.08}'
```

---

## Strategy Optimizer Configuration

The strategy optimizer stores its config in `polymarket_predictor/data/strategy.json`. It auto-tunes based on paper trading performance.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_edge_threshold` | float | `0.03` | Minimum edge to place any bet. |
| `max_bet_pct` | float | `0.05` | Maximum fraction of balance for a single bet. |
| `kelly_factor` | float | `0.25` | Fraction of full Kelly criterion to use (quarter-Kelly). |
| `min_volume` | float | `100` | Minimum market volume. |
| `odds_range` | [float, float] | `[0.10, 0.90]` | Only bet on markets with YES odds in this range. |
| `category_weights` | dict | See below | Multipliers per market category. |
| `confidence_multipliers` | dict | `{"high": 1.0, "medium": 0.6, "low": 0.3}` | Bet size scaling by confidence level. |
| `prefer_niche` | bool | `true` | Prefer less-efficient market categories. |
| `prefer_deep` | bool | `false` | Use deep predictions for trading loop. |

**Default category weights:**

```json
{
  "science": 1.5,
  "world": 1.4,
  "entertainment": 1.3,
  "politics": 1.1,
  "crypto": 0.7,
  "finance": 0.6,
  "sports": 0.5
}
```

Higher weights mean the system bets more aggressively in that category. Science, world events, and entertainment tend to have less-efficient markets (fewer informed traders), making them better targets for MiroFish edge.

---

## Example Configurations

### Cheapest possible setup (free tiers only)

```bash
PIPELINE_PRESET=gemini
GEMINI_API_KEY=AIza...
ZEP_API_KEY=z_...
```

Cost: ~$0.03/prediction using Gemini free tier (up to 1M tokens/day free).

### Balanced production setup

```bash
PIPELINE_PRESET=balanced
LLM_API_KEY=sk-proj-...
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=AIza...
ZEP_API_KEY=z_...
```

Cost: ~$0.42/prediction. Uses cheap models for preprocessing, GPT-4o for the expensive reasoning stages.

### Maximum quality

```bash
PIPELINE_PRESET=premium
LLM_API_KEY=sk-proj-...
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
ZEP_API_KEY=z_...
```

Cost: ~$0.54/prediction. Claude Sonnet for simulation reasoning, GPT-4o for reports.
