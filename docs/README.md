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

---

## How It Works (Summary)

1. **Scan** -- MarketScanner fetches active markets from Polymarket, filters by expiry, volume, and odds uncertainty, then ranks by "niche score" (markets where the crowd is less likely to be efficient).

2. **Seed** -- SeedGenerator combines market data with scraped news articles into structured text documents that frame the debate.

3. **Simulate** -- The seed is uploaded to MiroFish, which builds a knowledge graph, creates AI agent profiles, and runs a multi-round debate simulation where agents argue different sides.

4. **Extract** -- PredictionParser pulls a probability estimate from the simulation report using regex patterns or an LLM fallback.

5. **Trade** -- BetSizer uses the Kelly criterion to determine position size. PaperPortfolio records the bet and tracks P&L.

6. **Resolve** -- MarketResolver periodically checks Polymarket for settled markets and updates the portfolio.

7. **Optimize** -- StrategyOptimizer and Calibrator analyze historical accuracy to auto-tune edge thresholds, category weights, and bet sizing.

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
    dashboard/api.py           # Flask blueprint (all REST endpoints)
    scrapers/                  # Polymarket + news data fetching
    seeds/                     # Seed document generation
    scanner/                   # Market discovery and ranking
    orchestrator/              # MiroFish pipeline driver
    parser/                    # Prediction extraction from reports
    paper_trader/              # Portfolio + Kelly bet sizing
    resolver/                  # Market resolution + calibration updates
    calibrator/                # Brier score + calibration curves
    optimizer/                 # Strategy parameter tuning
    backtest/                  # Backtesting engine
    autopilot/                 # Fully autonomous prediction cycles
    ledger/                    # Append-only decision audit log
    loop/                      # Continuous trading loop runner
    tests/                     # Test suite
  docs/                        # This documentation
  start.sh                     # One-command launcher
```
