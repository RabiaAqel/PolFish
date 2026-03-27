# PolFish Documentation

PolFish is an AI-powered prediction market analysis platform. It uses MiroFish's multi-agent simulation engine to generate probability estimates for Polymarket events, then paper-trades against those predictions to measure real-world accuracy.

## Quick Start (5 minutes to first prediction)

### 1. Install dependencies

```bash
cd MiroFish/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd ../../
pip install -e .  # installs polymarket_predictor package
```

### 2. Configure API keys

```bash
cp MiroFish/.env.example MiroFish/.env
```

Edit `MiroFish/.env` and add at minimum:

```
LLM_API_KEY=your-openai-key
DEEPSEEK_API_KEY=your-deepseek-key
ZEP_API_KEY=your-zep-key
```

See [Configuration Guide](CONFIGURATION.md) for all options and free-tier providers.

### 3. Start the platform

```bash
./start.sh
```

This launches:
- **Backend** at `http://localhost:5001` (Flask API + Polymarket predictor)
- **Frontend** at `http://localhost:3000` (Vue 3 dashboard)

### 4. Make your first prediction

Open the dashboard at `http://localhost:3000` and navigate to the Polymarket page. Enter a market slug (e.g., `will-bitcoin-reach-100k-in-2025`) and click **Predict**.

Or use the API directly:

```bash
curl -X POST http://localhost:5001/api/polymarket/predict \
  -H "Content-Type: application/json" \
  -d '{"slug": "will-bitcoin-reach-100k-in-2025"}'
```

For a full deep prediction (runs the complete MiroFish simulation pipeline):

```bash
curl -X POST http://localhost:5001/api/polymarket/predict/deep \
  -H "Content-Type: application/json" \
  -d '{"slug": "will-bitcoin-reach-100k-in-2025", "variants": 3}'
```

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [Architecture](ARCHITECTURE.md) | System design, module dependencies, data flow diagrams |
| [Configuration](CONFIGURATION.md) | All environment variables, pipeline presets, provider setup |
| [API Reference](API_REFERENCE.md) | Every HTTP endpoint with request/response examples |
| [Cost Optimization](COST_OPTIMIZATION.md) | Token usage, model pricing, preset comparisons, ROI analysis |
| [Troubleshooting](TROUBLESHOOTING.md) | Common errors and their fixes |
| [Monte Carlo Research](MONTE_CARLO_RESEARCH.md) | 54K-portfolio simulation study: accuracy thresholds, Kelly tuning, and break-even analysis |
| [Prediction Pipeline Research](PREDICTION_PIPELINE_RESEARCH.md) | Pipeline weakness analysis: seed quality, agent diversity, simulation depth, and the prose-to-prediction gap |
| [Strategic Research](STRATEGIC_RESEARCH.md) | Competitive landscape, multi-agent debate evidence, local model benchmarks, testing best practices, and strategic recommendations |

---

## Key Features

- **Multi-agent simulation** -- MiroFish knowledge graph + agent debates produce diverse viewpoints
- **Dual prediction extraction** -- LLM-based (prose report) and quantitative (raw simulation data) predictions, auto-blended by the MethodTracker
- **Monte Carlo viability analysis** -- Parameter sweeps across accuracy, edge thresholds, and Kelly fractions to find break-even and optimal configurations
- **Overnight runner** -- Crash-safe batch predictions with atomic checkpoints and auto-resume
- **Rolling trading loop** -- Continuous prediction rounds at configurable intervals with budget caps
- **Multi-tier thesis grouping** -- Related markets (date tiers, price tiers, stage tiers) are grouped by shared thesis; ONE deep prediction covers all tiers, reducing costs by up to 78%
- **Self-improving method weights** -- MethodTracker auto-adjusts LLM vs quantitative blend based on resolved market outcomes
- **Paper trading** -- Full portfolio simulation with Kelly-optimal sizing, P&L tracking, and auto-resolution
- **Autopilot** -- End-to-end autonomous cycles: scan, predict, bet, resolve, optimize
- **Ollama local model support** -- Run the entire pipeline locally at $0.00/prediction using the `local` preset, or use `hybrid_local` for local prep + cloud reports at ~$0.12/prediction
- **Knowledge Base (context store)** -- Persistent market intelligence that accumulates over time; tracks accuracy by category, avoids re-researching the same topics, and provides cross-market context
- **200 agent templates (WEEX composition)** -- 200 built-in market-participant archetypes using WEEX-validated composition, including 3 Devil's Advocate templates that systematically challenge consensus. Configurable via `MAX_TEMPLATE_AGENTS` (default 15, WEEX-scale 170) for simulations ranging from lightweight to full-scale crowd wisdom
- **UI/UX overhaul** -- Streamlined navigation with Predict | Trade | Research (dropdown) | Settings (gear icon) for faster workflow access
- **Superforecaster prompt methodology** -- Report generation uses a structured 6-step Superforecaster process (decompose, base rates, evidence, factors, calibrate, predict) to reduce LLM default-probability bias
- **Dynamic cost estimation** -- Costs computed from actual model config and token pricing, replacing the earlier hardcoded $0.42 assumption
- **Enhanced Gamma API** -- Market search, event sub-market fetching, order book summaries, and tradable market filtering
- **Niche scoring** -- Scanner ranks markets by "nicheness" (category, keywords, volume) to find inefficient markets with more alpha potential
- **8 pipeline presets** -- From free local Ollama ($0.00/prediction) to premium Claude ($0.54/prediction)
- **Decision ledger** -- Append-only JSONL audit log of every system decision

## How It Works (Summary)

1. **Scan** -- MarketScanner fetches active markets from Polymarket, filters by expiry, volume, and odds uncertainty, then ranks by PolFish suitability score (category edge, volume sweet spot, odds uncertainty).

2. **Group** -- MarketGrouper clusters related markets by shared thesis (date tiers, price tiers, stage tiers). One deep prediction per group covers all tier markets.

3. **Seed** -- SeedGenerator combines market data with scraped news articles into structured text documents that frame the debate.

3. **Simulate** -- The seed is uploaded to MiroFish, which builds a knowledge graph, creates AI agent profiles, and runs a multi-round debate simulation where agents argue different sides.

4. **Extract** -- Two prediction methods run in parallel:
   - **LLM extraction:** PredictionParser reads the prose report and extracts a probability using regex or LLM fallback.
   - **Quantitative extraction:** SimulationAnalyzer reads the raw SQLite simulation data -- agent sentiment counts, engagement-weighted consensus, temporal momentum, and expert-weighted votes -- to compute a data-driven probability.

5. **Blend** -- MethodTracker combines both predictions using auto-adjusting weights. As markets resolve, the method with better Brier scores gets more weight.

6. **Trade** -- BetSizer uses the Kelly criterion to determine position size. PaperPortfolio records the bet and tracks P&L.

7. **Resolve** -- MarketResolver periodically checks Polymarket for settled markets and updates the portfolio.

8. **Optimize** -- StrategyOptimizer and Calibrator analyze historical accuracy to auto-tune edge thresholds, category weights, and bet sizing.

---

## Project Layout

```
mirofish/
  MiroFish/                    # Core simulation engine
    backend/                   # Flask API server
    frontend/                  # Vue 3 dashboard
    .env.example               # Configuration template
  polymarket_predictor/        # Prediction pipeline package
    config.py                  # Central configuration
    cost_calculator.py         # Cost estimation engine
    cost_tracker.py            # Runtime token usage tracking
    cli.py                     # CLI entry point
    dashboard/api.py           # Flask blueprint (all 54 REST endpoints)
    scrapers/                  # Polymarket + news data fetching
    seeds/                     # Seed document generation
    knowledge/                 # Persistent market intelligence (context store)
      context_store.py         # MarketContext records, accuracy tracking
    agents/                    # Template agent archetypes
      templates.py             # 200 market-participant templates (WEEX composition)
    scanner/                   # Market discovery and ranking
    orchestrator/              # MiroFish pipeline driver
    parser/                    # Prediction extraction from reports
    analyzer/                  # Quantitative analysis + method tracking
      simulation_analyzer.py   # Prediction from raw SQLite simulation data
      method_tracker.py        # LLM vs quant comparison, auto-blend weights
    monte_carlo/               # Portfolio viability simulation
      simulator.py             # Parameter sweeps, break-even analysis
    thesis/                    # Multi-tier thesis grouping
      grouper.py               # MarketGrouper — group related markets
      applier.py               # ThesisApplier — apply thesis to tiers
    overnight/                 # Resilient long-running operations
      runner.py                # OvernightRunner + RollingLoop
      state.py                 # Crash-safe atomic state checkpoints
    paper_trader/              # Portfolio + Kelly bet sizing
    resolver/                  # Market resolution + calibration updates
    calibrator/                # Brier score + calibration curves
    optimizer/                 # Strategy parameter tuning
    backtest/                  # Backtesting engine
    autopilot/                 # Fully autonomous prediction cycles
    ledger/                    # Append-only decision audit log
    loop/                      # Continuous trading loop runner
    tests/                     # Test suite (531 tests)
  docs/                        # This documentation
  start.sh                     # One-command launcher
```
