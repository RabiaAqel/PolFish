# Architecture

## High-Level Pipeline

```
                                    PolFish System Architecture
                                    ==========================

  +-------------------+     +-------------------+     +-------------------+
  |   Polymarket API  |     |   News Sources    |     |   User / Cron     |
  |  (Gamma + CLOB)   |     |  (DuckDuckGo etc) |     |  (Dashboard/CLI)  |
  +--------+----------+     +--------+----------+     +--------+----------+
           |                         |                         |
           v                         v                         v
  +--------+-------------------------+-------------------------+----------+
  |                        polymarket_predictor                            |
  |                                                                        |
  |  +----------------+   +----------------+   +-------------------------+ |
  |  | MarketScanner  |-->| SeedGenerator  |-->| MiroFishPipeline        | |
  |  | (scanner/)     |   | (seeds/)       |   | (orchestrator/)         | |
  |  |                |   |                |   |                         | |
  |  | - scan_expiring|   | - generate_seed|   | - upload_and_generate   | |
  |  | - scan_interest|   | - variants:    |   |   _ontology             | |
  |  | - categorize   |   |   balanced,    |   | - build_graph           | |
  |  | - niche scoring|   |   contrarian,  |   | - create_simulation     | |
  |  +----------------+   |   data_heavy,  |   | - run_simulation        | |
  |                        |   news_heavy   |   | - generate_report       | |
  |                        +----------------+   +------------+------------+ |
  |                                                          |              |
  |                                                          v              |
  |  +----------------+   +----------------+   +-------------------------+ |
  |  | PaperPortfolio |<--| BetSizer       |<--| PredictionParser       | |
  |  | (paper_trader/)|   | (Kelly sizing) |   | (parser/)              | |
  |  |                |   |                |   |                         | |
  |  | - place_bet    |   | - kelly_frac   |   | - regex extraction     | |
  |  | - resolve_bet  |   | - size_bet     |   | - LLM fallback         | |
  |  | - get_perf     |   +----------------+   +-------------------------+ |
  |  +-------+--------+                                                    |
  |          |                                                             |
  |          v                                                             |
  |  +----------------+   +----------------+   +-------------------------+ |
  |  | MarketResolver |-->| Calibrator     |-->| StrategyOptimizer      | |
  |  | (resolver/)    |   | (calibrator/)  |   | (optimizer/)           | |
  |  |                |   |                |   |                         | |
  |  | - check_resol  |   | - brier_score  |   | - optimize params      | |
  |  | - settle P&L   |   | - calibration  |   | - category weights     | |
  |  |                |   |   curve/bins   |   | - edge thresholds      | |
  |  +----------------+   +----------------+   +-------------------------+ |
  |                                                                        |
  |  +---------------------------+   +----------------------------------+  |
  |  | AutopilotEngine           |   | BacktestEngine                   |  |
  |  | (autopilot/)              |   | (backtest/)                      |  |
  |  |                           |   |                                  |  |
  |  | Fully autonomous cycles:  |   | Test against resolved markets:  |  |
  |  | scan -> quick predict ->  |   | fetch resolved -> predict ->    |  |
  |  | rank -> deep predict ->   |   | bet -> resolve -> calibrate ->  |  |
  |  | confirm/reject -> bet ->  |   | optimize (incremental batches)  |  |
  |  | resolve -> optimize       |   |                                  |  |
  |  +---------------------------+   +----------------------------------+  |
  |                                                                        |
  |  +---------------------------+   +----------------------------------+  |
  |  | DecisionLedger            |   | CostCalculator                   |  |
  |  | (ledger/)                 |   | (cost_calculator.py)             |  |
  |  |                           |   |                                  |  |
  |  | Append-only JSONL audit   |   | Estimate costs per preset,      |  |
  |  | log of every decision:    |   | per model, per batch. Compare   |  |
  |  | BET_PLACED, BET_SKIPPED,  |   | configurations and track ROI.   |  |
  |  | DEEP_CONFIRMED, etc.      |   |                                  |  |
  |  +---------------------------+   +----------------------------------+  |
  |                                                                        |
  |  +---------------------------+   +----------------------------------+  |
  |  | SimulationAnalyzer        |   | MethodTracker                    |  |
  |  | (analyzer/simulation_     |   | (analyzer/method_tracker.py)     |  |
  |  |  analyzer.py)             |   |                                  |  |
  |  |                           |   | Self-improving prediction        |  |
  |  | Quantitative prediction   |   | method comparison:               |  |
  |  | from raw SQLite data:     |   | - Track LLM vs quant accuracy   |  |
  |  | - Agent sentiment counts  |   | - Auto-adjust blend weights     |  |
  |  | - Engagement weighting    |   | - Brier score per method        |  |
  |  | - Temporal momentum       |   | - Store every comparison        |  |
  |  | - Expert-weighted votes   |   |                                  |  |
  |  +---------------------------+   +----------------------------------+  |
  |                                                                        |
  |  +---------------------------+   +----------------------------------+  |
  |  | MonteCarloSimulator       |   | OvernightRunner + RollingLoop    |  |
  |  | (monte_carlo/simulator.py)|   | (overnight/runner.py)            |  |
  |  |                           |   |                                  |  |
  |  | Portfolio viability study: |   | Resilient long-running ops:     |  |
  |  | - Parameter sweeps over   |   | - Crash recovery via checkpoints|  |
  |  |   accuracy, edge, kelly   |   | - Atomic state writes           |  |
  |  | - Break-even detection    |   | - Budget tracking per round     |  |
  |  | - 1000+ simulation paths  |   | - Graceful stop support         |  |
  |  | - Uses real market data   |   | - Auto-resume on restart        |  |
  |  +---------------------------+   +----------------------------------+  |
  |                                                                        |
  |  +---------------------------+   +----------------------------------+  |
  |  | ContextStore              |   | TemplateAgents                   |  |
  |  | (knowledge/context_store  |   | (agents/templates.py)            |  |
  |  |  .py)                     |   |                                  |  |
  |  | Persistent market intel:  |   | 200 agent templates (WEEX        |  |
  |  | - Cross-market context    |   | composition validated):           |  |
  |  | - Accuracy by category    |   | - Retail/institutional traders   |  |
  |  | - Avoid re-researching    |   | - Contrarians, momentum, whales  |  |
  |  |   same topics             |   | - Domain experts, superforecasters|  |
  |  | - Historical patterns     |   | - 3 Devil's Advocate templates   |  |
  |  |                           |   | - Includes OASIS-required fields |  |
  |  |                           |   | - MAX_TEMPLATE_AGENTS: 5-170     |  |
  |  +---------------------------+   +----------------------------------+  |
  |                                                                        |
  |  +---------------------------+   +----------------------------------+  |
  |  | MarketGrouper             |   | ThesisApplier                    |  |
  |  | (thesis/grouper.py)       |   | (thesis/applier.py)              |  |
  |  |                           |   |                                  |  |
  |  | Multi-tier thesis system: |   | Apply thesis to individual tiers:|  |
  |  | - Date tiers (same event, |   | - Date: cumulative probability  |  |
  |  |   different deadlines)    |   | - Price: directional adjustment |  |
  |  | - Price tiers (same asset,|   | - Stage: conditional probability|  |
  |  |   different targets)      |   | - Returns TierPrediction per    |  |
  |  | - Stage tiers (nomination |   |   market with edge + signal     |  |
  |  |   -> election)            |   |                                  |  |
  |  +---------------------------+   +----------------------------------+  |
  +------------------------------------------------------------------------+
           |
           v
  +------------------------------------------------------------------------+
  |                    MiroFish Backend (Flask API)                         |
  |                                                                        |
  |  app/services/                                                         |
  |    ontology_generator.py    - Generate ontology from seed documents     |
  |    graph_builder.py         - Build knowledge graph from ontology       |
  |    simulation_config_gen.py - Generate agent profiles and config        |
  |    simulation_runner.py     - Run multi-round agent debates             |
  |    simulation_manager.py    - Manage simulation lifecycle               |
  |    text_processor.py        - Document parsing and chunking             |
  |    zep_graph_memory.py      - Zep knowledge graph integration          |
  |                                                                        |
  |  app/api/                   - REST endpoints for graph/sim/report       |
  |  app/models/                - Project and Task data models              |
  |  app/utils/                 - Logging, retry, file parsing, Zep paging  |
  +------------------------------------------------------------------------+
           |
           v
  +------------------------------------------------------------------------+
  |                    MiroFish Frontend (Vue 3 + Vite)                     |
  |                                                                        |
  |  views/                                                                |
  |    PolymarketView.vue       - Market prediction interface               |
  |    PaperTradingView.vue     - Portfolio and bet tracking                |
  |    BacktestView.vue         - Backtesting interface                     |
  |    DecisionLogView.vue      - Decision ledger browser                   |
  |    HowItWorksView.vue       - Pipeline explainer                        |
  |    SimulationView.vue       - MiroFish simulation runner                |
  |    SimulationRunView.vue    - Live simulation monitoring                |
  |    ReportView.vue           - Report viewer                             |
  |    InteractionView.vue      - Agent interaction explorer                |
  |                                                                        |
  |  components/                                                           |
  |    Step1GraphBuild.vue      - Graph building step                       |
  |    Step2EnvSetup.vue        - Environment/agent setup                   |
  |    Step3Simulation.vue      - Simulation control                        |
  |    Step4Report.vue          - Report generation                         |
  |    Step5Interaction.vue     - Post-sim interaction                      |
  |    GraphPanel.vue           - Knowledge graph visualization             |
  |    HistoryDatabase.vue      - Historical data browser                   |
  +------------------------------------------------------------------------+
```

## Data Flow

### Quick Prediction Flow

```
User enters slug
       |
       v
PolymarketScraper.get_market_by_slug(slug)
       |
       v
NewsAggregator.search_articles(question)
       |
       v
SeedGenerator.generate_seed(market, articles, variant="balanced")
       |
       v
Return seed file path + market data (no simulation)
```

### Deep Prediction Flow

```
User enters slug + variant count
       |
       v
For each variant (balanced, contrarian, data_heavy, ...):
  |
  +-> SeedGenerator.generate_seed(market, articles, variant)
  |        |
  |        v
  +-> MiroFishPipeline.run(seed_path, question, max_rounds=15)
  |     |
  |     +-> upload_and_generate_ontology()   [ONTOLOGY stage]
  |     +-> build_graph()                     [GRAPH stage]
  |     +-> create_simulation()
  |     +-> prepare_simulation()              [PROFILES stage]
  |     +-> run_simulation(max_rounds=15)     [SIMULATION stage]
  |     +-> generate_report()                 [REPORT stage]
  |        |
  |        v
  +-> PredictionParser.parse(report_text, question)
         |
         v
      Prediction { probability, confidence, key_factors }

Ensemble average across variants
       |
       v
Signal: BUY_YES / BUY_NO / SKIP (based on edge vs market odds)
```

### Prediction Verdict Flow (LLM + Quantitative Blend)

```
Simulation completes
       |
       +---> LLM Prediction (report-based)
       |       PredictionParser reads prose report → probability
       |
       +---> Quantitative Prediction (data-based)
       |       SimulationAnalyzer reads raw SQLite data:
       |         - Agent sentiment counts (YES/NO/NEUTRAL)
       |         - Engagement-weighted consensus
       |         - Temporal momentum (early vs late rounds)
       |         - Expert-weighted votes
       |
       v
MethodTracker blends both predictions:
  combined = (llm_weight * llm_prob) + (quant_weight * quant_prob)
       |
       v
Weights auto-adjust as markets resolve:
  Method with better Brier score gets more weight over time
       |
       v
Final prediction → edge calculation → bet decision
```

### Multi-Tier Thesis Flow (Overnight Runner)

```
MarketScanner.scan_interesting()
       |
       v
MarketGrouper.group_markets(candidates)
       |
       v
Groups: [Iran ceasefire (7 tiers), Oil prices (6 tiers), Eurovision (single)]
       |
       v
For each GROUP:
  |
  +-> If multi-tier (2+ markets):
  |     |
  |     +-> Run ONE deep prediction on group.thesis_question
  |     |     (e.g., "When will Iran ceasefire happen?")
  |     |
  |     +-> ThesisApplier.apply_{date|price|stage}_thesis()
  |     |     Maps thesis prediction to each tier market
  |     |
  |     +-> For each tier: check edge, size bet, place if warranted
  |
  +-> If single market:
        |
        +-> Run deep prediction as normal (same as before)
        +-> Check edge, size bet, place if warranted

Cost savings: 3 groups x $0.42 = $1.26 vs 14 markets x $0.42 = $5.88 (78%)
```

### Autopilot Cycle Flow

```
AutopilotEngine.run_cycle()
       |
       v
Phase 1: SCAN
  MarketScanner.scan_interesting(days_ahead, min_volume, odds_range)
       |
       v
Phase 2: QUICK PREDICT
  For each market: call /api/polymarket/predict (seed-only, no simulation)
       |
       v
Phase 3: SELECT CANDIDATES
  Rank by edge, filter by min_edge_for_deep, cap at max_deep_per_cycle
       |
       v
Phase 4: DEEP PREDICT
  For top candidates: run full MiroFish pipeline
  Confirm if deep edge >= min_edge_for_bet, reject otherwise
       |
       v
Phase 5: BET
  BetSizer.size_bet() using Kelly criterion
  PaperPortfolio.place_bet()
  DecisionLedger.log(BET_PLACED / BET_SKIPPED)
       |
       v
Phase 6: RESOLVE
  MarketResolver.check_resolutions() for all open positions
       |
       v
Phase 7: OPTIMIZE
  StrategyOptimizer.optimize() adjusts parameters based on performance
       |
       v
Phase 8: SUMMARY
  DecisionLedger.log(CYCLE_SUMMARY)
```

## Module Dependency Graph

```
config.py  <------------ (every module imports this)
    |
    v
scrapers/
  polymarket.py  -----> Market dataclass
  news.py        -----> Article dataclass
    |
    v
seeds/
  generator.py   -----> SeedGenerator (uses Market + Article)
  templates.py   -----> SeedTemplate, CATEGORY_MAP
    |
    v
orchestrator/
  pipeline.py    -----> MiroFishPipeline (calls MiroFish backend API)
  ensemble.py    -----> EnsemblePrediction
  prompts.py     -----> Prompt templates
    |
    v
parser/
  prediction.py  -----> PredictionParser, Prediction
    |
    v
paper_trader/
  portfolio.py   -----> PaperPortfolio, BetSizer, BetRecord
    |
    v
calibrator/
  history.py     -----> PredictionHistory, PredictionRecord, ResolutionRecord
  calibrate.py   -----> Calibrator, CalibrationReport
  backtest.py    -----> (legacy calibration backtest)
    |
    v
resolver/
  resolver.py    -----> MarketResolver, CalibrationUpdater
    |
    v
optimizer/
  strategy.py    -----> StrategyOptimizer, DEFAULT_STRATEGY_CONFIG
    |
    v
scanner/
  market_scanner.py --> MarketScanner (uses PolymarketScraper)
    |
    v
ledger/
  decision_ledger.py -> DecisionLedger, LedgerEntry
    |
    v
autopilot/
  engine.py      -----> AutopilotEngine, AutopilotConfig
    |
    v
backtest/
  engine.py      -----> BacktestEngine
    |
    v
loop/
  runner.py      -----> TradingLoop
    |
    v
analyzer/
  simulation_analyzer.py -> SimulationAnalyzer (quantitative prediction from SQLite)
  method_tracker.py ------> MethodTracker (LLM vs quant comparison, auto-blend)
    |
    v
monte_carlo/
  simulator.py   -----> MonteCarloSimulator, ParameterSweepResult
    |
    v
knowledge/
  context_store.py --> ContextStore, MarketContext (persistent market intelligence)
    |
    v
agents/
  templates.py   -----> MARKET_PARTICIPANT_TEMPLATES, get_templates (200 archetypes, WEEX composition)
    |
    v
thesis/
  grouper.py     -----> MarketGrouper, MarketGroup (group related markets)
  applier.py     -----> ThesisApplier, TierPrediction (apply thesis to tiers)
    |
    v
overnight/
  runner.py      -----> OvernightRunner, RollingLoop (crash-safe long runs)
  state.py       -----> StateManager, RunState (atomic checkpoints)
    |
    v
dashboard/
  api.py         -----> Flask Blueprint (all REST endpoints)
    |
    v
cost_calculator.py ---> CostCalculator, StageEstimate
cost_tracker.py  -----> CostTracker (runtime token counting)
```

## Backend Architecture

The backend is a Flask application that serves two roles:

1. **MiroFish Core API** (`app/api/`) -- Handles ontology generation, graph building, simulation running, and report generation. These are the endpoints that the `MiroFishPipeline` orchestrator calls.

2. **Polymarket Dashboard API** (`polymarket_predictor/dashboard/api.py`) -- A Flask Blueprint registered under `/api/polymarket/` that exposes prediction, paper trading, autopilot, backtest, ledger, and cost endpoints.

### Threading Model

- The Flask server runs with `threaded=True` on port 5001.
- Deep predictions, autopilot cycles, and backtests run in background `threading.Thread` instances.
- Each background task gets a UUID-based `task_id` stored in an in-memory dict (`_deep_tasks`).
- Clients poll `GET /api/polymarket/predict/deep/{task_id}` to check progress.
- Real-time logs are streamed via Server-Sent Events (SSE) at `GET /api/polymarket/logs/stream`.
- A background timer runs every 5 minutes to auto-resolve settled markets.

### Persistence

All persistent data lives in `polymarket_predictor/data/`:

| File | Purpose |
|------|---------|
| `portfolio.jsonl` | Paper trading positions (one JSON object per line) |
| `decision_ledger.jsonl` | Audit log of every system decision |
| `predictions.jsonl` | Prediction history for calibration |
| `resolutions.jsonl` | Market resolution outcomes |
| `strategy.json` | Current strategy optimizer parameters |
| `autopilot_config.json` | Autopilot tuning parameters |
| `backtest/` | Isolated backtest data directory |
| `overnight_state.json` | Checkpoint state for overnight/rolling runs |
| `monte_carlo_results.json` | Cached Monte Carlo simulation results |
| `method_comparisons.jsonl` | Per-prediction LLM vs quant comparison log |
| `method_performance.json` | Aggregated method accuracy and blend weights |
| `context_store.jsonl` | Persistent market intelligence (knowledge base) |

## Frontend Architecture

The frontend is a Vue 3 single-page application built with Vite and served on port 3000. It communicates with the backend exclusively through REST API calls and SSE for log streaming.

### Key Pages

| Page | Route | Description |
|------|-------|-------------|
| `PolymarketView` | `/polymarket` | Enter slugs, run quick/deep predictions, view signals |
| `PaperTradingView` | `/paper-trading` | Portfolio dashboard, open positions, P&L charts |
| `BacktestView` | `/backtest` | Run backtests, view calibration, incremental optimization |
| `DecisionLogView` | `/decision-log` | Browse and search the decision ledger |
| `KnowledgeBaseView` | `/knowledge-base` | Browse accumulated market intelligence and accuracy |
| `HowItWorksView` | `/how-it-works` | Visual explainer of the pipeline |
| `SimulationView` | `/simulation` | MiroFish simulation setup and execution |
| `ReportView` | `/report` | View generated simulation reports |

### Shared Components

| Component | Used In | Purpose |
|-----------|---------|---------|
| `GraphPanel` | SimulationView | Visualize the knowledge graph |
| `HistoryDatabase` | Multiple views | Browse historical predictions |
| `Step1-5` | SimulationView | Wizard-style simulation setup |

## External Dependencies

| Service | Purpose | Required |
|---------|---------|----------|
| Polymarket Gamma API | Market data (read-only, no auth) | Yes |
| Polymarket CLOB API | Order book data (read-only, no auth) | Yes |
| OpenAI API | LLM for simulation + reports | Yes (or alternative) |
| DeepSeek API | LLM for preprocessing stages | Recommended |
| Gemini API | LLM for agent profiles | Optional |
| Anthropic API | Claude for simulation reasoning | Optional |
| Ollama | Local model inference (OpenAI-compatible) | Optional (free, no key) |
| Zep API | Knowledge graph memory | Yes |
| DuckDuckGo | News article search | Yes (free, no key) |
