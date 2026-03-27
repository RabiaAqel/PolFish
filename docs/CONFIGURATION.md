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
| `OLLAMA_BASE_URL` | string | `http://localhost:11434/v1` | Base URL for local Ollama server. |
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
| `MAX_SIMULATION_ROUNDS` | int | `40` | Maximum simulation rounds per prediction. Takes precedence over `PREDICTOR_MAX_ROUNDS`. |
| `PREDICTOR_MAX_ROUNDS` | int | `40` | Alias for `MAX_SIMULATION_ROUNDS`. Used as fallback if `MAX_SIMULATION_ROUNDS` is not set. |
| `PREDICTOR_VARIANTS` | int | `3` | Number of seed variants for ensemble predictions. |
| `PREDICTOR_MIN_EDGE` | float | `0.10` | Minimum edge (as decimal) to generate a signal. |
| `PREDICTOR_MIN_VOLUME` | float | `10000` | Minimum market volume (USD) for signal generation. |

### Template Agent Injection

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MAX_TEMPLATE_AGENTS` | int | `15` | Maximum number of template agents injected into each simulation. The system includes 200 built-in archetypes (WEEX-validated composition including 3 Devil's Advocate templates). Scale options: `5` (minimal), `15` (default), `50` (enhanced), `170` (WEEX-scale). Set to `0` to disable template injection. |
| `DEFAULT_LLM_WEIGHT` | float | `0.25` | Weight for LLM-based (prose report) predictions in the MethodTracker blend. |
| `DEFAULT_QUANT_WEIGHT` | float | `0.75` | Weight for quantitative (simulation data) predictions in the MethodTracker blend. Quant-dominant weighting reflects empirical finding that data-driven extraction outperforms prose-based extraction. |

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
| `local` | llama3.1:8b | llama3.1:8b | llama3.1:8b | llama3.1:8b | llama3.1:8b | $0.00 |
| `hybrid_local` | llama3.1:8b | llama3.1:8b | llama3.1:8b | llama3.1:8b | gpt-4o | ~$0.12 |
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

### Local Models (Ollama)

Ollama lets you run open-source models locally with zero API costs. It exposes an OpenAI-compatible endpoint that works with the existing pipeline.

**Installation:**

```bash
# macOS
brew install ollama

# Start the server (runs in background)
ollama serve

# Pull models
ollama pull llama3.1:8b      # Fast, good for preprocessing (~4.7 GB)
ollama pull llama3.1:70b     # High quality, needs 40+ GB RAM
ollama pull qwen2.5:14b      # Good balance of speed and quality
ollama pull deepseek-r1:8b   # Reasoning model
```

**Configuration:**

```bash
# All-local (free, no API keys needed):
PIPELINE_PRESET=local

# Hybrid (local preprocessing + cloud report for quality):
PIPELINE_PRESET=hybrid_local
LLM_API_KEY=sk-proj-...   # Still need OpenAI key for the report stage

# Custom Ollama base URL (default: http://localhost:11434/v1):
OLLAMA_BASE_URL=http://192.168.1.100:11434/v1
```

**Performance expectations:**

| Model | Speed | Quality | RAM Required |
|-------|-------|---------|-------------|
| llama3.1:8b | Fast (~20 tok/s) | Good for prep stages | ~5 GB |
| llama3.1:70b | Slow (~3 tok/s) | Near GPT-4o quality | ~40 GB |
| qwen2.5:14b | Medium (~12 tok/s) | Good all-rounder | ~9 GB |
| mistral:7b | Fast (~22 tok/s) | Good for simple tasks | ~4 GB |
| deepseek-r1:8b | Medium (~15 tok/s) | Good reasoning | ~5 GB |

**Recommended per-stage models:**

- **Ontology/Graph:** llama3.1:8b (fast, these stages are simple)
- **Profiles:** llama3.1:8b or qwen2.5:14b
- **Simulation:** qwen2.5:14b or llama3.1:70b (quality matters here)
- **Report:** Use cloud (gpt-4o) for best quality, or llama3.1:70b locally

**Models available:** `llama3.1:8b`, `llama3.1:70b`, `mistral:7b`, `qwen2.5:14b`, `qwen2.5:72b`, `deepseek-r1:8b` (all $0.00)

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

### Free local setup (no API keys, no costs)

```bash
PIPELINE_PRESET=local
ZEP_API_KEY=z_...
```

Cost: $0.00/prediction using Ollama. Requires `ollama serve` running locally with `llama3.1:8b` pulled.

### Hybrid local + cloud setup

```bash
PIPELINE_PRESET=hybrid_local
LLM_API_KEY=sk-proj-...
ZEP_API_KEY=z_...
```

Cost: ~$0.12/prediction. Local models for all prep stages, GPT-4o only for the final report.

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

### WEEX-scale crowd simulation (200 agents)

```bash
PIPELINE_PRESET=cheapest
MAX_TEMPLATE_AGENTS=170
MAX_SIMULATION_ROUNDS=40
DEEPSEEK_API_KEY=sk-...
ZEP_API_KEY=z_...
```

Cost: ~$3-5/prediction with 200 agents on DeepSeek. Uses WEEX-validated agent composition for maximum crowd wisdom diversity. The 170 template agents plus graph-derived organic agents approach the full 200-agent pool.

---

## .env.example Summary

A minimal `.env` file for the balanced preset:

```bash
# Core LLM
LLM_API_KEY=sk-proj-...
LLM_MODEL_NAME=gpt-4o

# Providers
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=AIza...
ZEP_API_KEY=z_...

# Pipeline
PIPELINE_PRESET=balanced
MAX_SIMULATION_ROUNDS=40

# Optional providers
# ANTHROPIC_API_KEY=sk-ant-...
# MISTRAL_API_KEY=...
# GROQ_API_KEY=gsk_...
```
