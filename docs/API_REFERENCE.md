# API Reference

All endpoints are served by the Flask backend at `http://localhost:5001`. The Polymarket prediction endpoints are registered under the `/api/polymarket/` prefix.

**Common response format:**

```json
{
  "success": true,
  "data": { ... }
}
```

On error:

```json
{
  "success": false,
  "error": "Human-readable error message"
}
```

---

## Predictor

### POST /api/polymarket/predict

Run a quick prediction for a market. Fetches market data, gathers news articles, and generates a seed document. Does NOT run the full MiroFish simulation.

**Request body:**

```json
{
  "slug": "will-bitcoin-reach-100k-in-2025"
}
```

The `slug` field accepts:
- A bare slug: `will-bitcoin-reach-100k-in-2025`
- A full Polymarket URL: `https://polymarket.com/event/will-bitcoin-reach-100k-in-2025`

**Response (200):**

```json
{
  "success": true,
  "data": {
    "market": {
      "question": "Will Bitcoin reach $100k in 2025?",
      "slug": "will-bitcoin-reach-100k-in-2025",
      "current_odds": 0.65,
      "volume": 1500000,
      "category": "crypto"
    },
    "seed_file": "/tmp/polymarket_seeds/will-bitcoin-reach-100k-in-2025/seed_balanced.txt",
    "articles_found": 3,
    "status": "seed_ready",
    "message": "Seed document generated with 3 articles. Market odds: 65.0% YES."
  }
}
```

**Error codes:** `400` (missing slug), `404` (market not found), `500` (internal error)

---

### POST /api/polymarket/predict/deep

Start a full deep prediction pipeline as a background task. Runs the complete MiroFish simulation (ontology, graph, profiles, simulation, report) for each variant.

**Request body:**

```json
{
  "slug": "will-bitcoin-reach-100k-in-2025",
  "variants": 3
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `slug` | string | required | Market slug or full Polymarket URL |
| `variants` | int | `1` | Number of seed variants to run (1-5) |

**Response (202 Accepted):**

```json
{
  "success": true,
  "task_id": "a1b2c3d4e5f6",
  "status": "running"
}
```

---

### GET /api/polymarket/predict/deep/{task_id}

Check the status of a deep prediction task.

**Response (running):**

```json
{
  "success": true,
  "task_id": "a1b2c3d4e5f6",
  "status": "running",
  "step": "running_simulation"
}
```

Possible `step` values: `fetching_market`, `building_graph`, `setting_up`, `running_simulation`, `generating_report`, `extracting_prediction`, `completed`

**Response (completed):**

```json
{
  "success": true,
  "task_id": "a1b2c3d4e5f6",
  "status": "completed",
  "result": {
    "market": {
      "question": "Will Bitcoin reach $100k in 2025?",
      "slug": "will-bitcoin-reach-100k-in-2025",
      "current_odds": 0.65,
      "volume": 1500000,
      "category": "crypto"
    },
    "prediction": {
      "probability": 0.72,
      "edge": 0.07,
      "signal": "BUY_YES",
      "variants_run": 3,
      "variant_details": [
        {
          "variant": "balanced",
          "probability": 0.70,
          "confidence": "medium",
          "key_factors": ["Strong institutional adoption", "ETF inflows"],
          "extraction_method": "regex"
        }
      ]
    },
    "report_summary": "Based on the multi-agent simulation..."
  }
}
```

**Response (failed):**

```json
{
  "success": true,
  "task_id": "a1b2c3d4e5f6",
  "status": "failed",
  "error": "Market 'invalid-slug' not found on Polymarket"
}
```

**Error codes:** `404` (task not found)

---

## Paper Trading

### GET /api/polymarket/portfolio

Get current portfolio status including balance, open positions, and performance metrics.

**Response:**

```json
{
  "success": true,
  "data": {
    "balance": 9850.50,
    "total_value": 10150.50,
    "open_positions": [
      {
        "market_id": "0x1234...",
        "slug": "will-bitcoin-reach-100k-in-2025",
        "question": "Will Bitcoin reach $100k in 2025?",
        "side": "YES",
        "amount": 150.0,
        "odds": 0.65,
        "placed_at": "2025-03-20T10:30:00",
        "closes_at": "2025-12-31T00:00:00",
        "resolved": false,
        "prediction": 0.72,
        "edge": 0.07,
        "confidence": "medium",
        "mode": "deep",
        "kelly_fraction": 0.032,
        "cost_usd": 0.42
      }
    ],
    "performance": {
      "total_bets": 25,
      "wins": 15,
      "losses": 10,
      "win_rate": 60.0,
      "total_pnl": 250.50,
      "roi": 3.12,
      "sharpe_ratio": 1.245,
      "max_drawdown": 180.00
    }
  }
}
```

---

### GET /api/polymarket/portfolio/history

Get resolved positions with P&L history.

**Response:**

```json
{
  "success": true,
  "data": {
    "resolved": [
      {
        "market_id": "0xabcd...",
        "slug": "some-resolved-market",
        "question": "Did X happen?",
        "side": "YES",
        "amount": 100.0,
        "odds": 0.55,
        "resolved": true,
        "outcome_yes": true,
        "payout": 181.82,
        "pnl": 81.82,
        "resolved_at": "2025-03-18T14:00:00"
      }
    ],
    "performance": { ... }
  }
}
```

---

### POST /api/polymarket/portfolio/resolve

Manually trigger resolution check for all open positions. Queries Polymarket for each open position to see if the market has settled.

**Response:**

```json
{
  "success": true,
  "data": {
    "resolved_count": 2,
    "results": [
      {
        "market_id": "0xabcd...",
        "question": "Did X happen?",
        "outcome": "YES",
        "pnl": 81.82
      }
    ]
  }
}
```

---

### POST /api/polymarket/portfolio/reset

Reset the portfolio to a fresh $10,000 state. Clears ALL positions (open and resolved).

**Response:**

```json
{
  "success": true,
  "data": {
    "balance": 10000.0,
    "message": "Portfolio reset to $10,000"
  }
}
```

---

## Autopilot

### POST /api/polymarket/autopilot/run

Start a full autopilot cycle (scan, quick predict, deep predict top candidates, bet, resolve, optimize).

**Request body (optional):**

```json
{
  "quick_only": false
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `quick_only` | bool | `false` | If true, skip deep predictions and bet based on quick predictions only. |

**Response (202 Accepted):**

```json
{
  "success": true,
  "task_id": "abc123def456",
  "status": "running"
}
```

---

### GET /api/polymarket/autopilot/run/{task_id}

Check autopilot cycle status.

**Response (completed):**

```json
{
  "success": true,
  "task_id": "abc123def456",
  "status": "completed",
  "result": {
    "cycle_id": "cycle_a1b2c3d4",
    "phases": {
      "scan": { "markets_found": 35 },
      "quick_predict": { "predicted": 35, "above_threshold": 8 },
      "select": { "candidates": 3 },
      "deep_predict": { "confirmed": 2, "rejected": 1 },
      "bet": { "placed": 2 },
      "resolve": { "resolved": 1 },
      "optimize": { "changes": [] }
    }
  }
}
```

---

### GET /api/polymarket/autopilot/config

Get current autopilot configuration.

**Response:**

```json
{
  "success": true,
  "data": {
    "max_deep_per_cycle": 3,
    "max_cost_per_cycle": 15.0,
    "min_edge_for_deep": 0.05,
    "min_edge_for_bet": 0.03,
    "cycle_interval_hours": 6,
    "niche_focus": true,
    "quick_research": false,
    "max_markets_to_scan": 50,
    "days_ahead": 7.0,
    "min_volume": 500,
    "cost_per_deep": 4.0
  }
}
```

---

### PUT /api/polymarket/autopilot/config

Update autopilot configuration. Only include fields you want to change.

**Request body:**

```json
{
  "max_deep_per_cycle": 5,
  "min_edge_for_deep": 0.08,
  "days_ahead": 3.0
}
```

**Response:**

```json
{
  "success": true,
  "data": { ... }
}
```

---

## Backtest

### POST /api/polymarket/backtest/run

Start a backtest against resolved Polymarket markets.

**Request body:**

```json
{
  "num_markets": 50,
  "mode": "quick"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `num_markets` | int | `50` | Number of resolved markets to test against. |
| `mode` | string | `quick` | `"quick"` adds noise to market odds; `"deep"` is reserved for future use. |

**Response (202 Accepted):**

```json
{
  "success": true,
  "task_id": "bt_abc123",
  "status": "running"
}
```

---

### GET /api/polymarket/backtest/run/{task_id}

Check backtest status. Returns progress during execution and full results when complete.

**Response (running):**

```json
{
  "success": true,
  "task_id": "bt_abc123",
  "status": "running",
  "progress": { "current": 15, "total": 50 }
}
```

**Response (completed):**

```json
{
  "success": true,
  "task_id": "bt_abc123",
  "status": "completed",
  "result": {
    "total_markets": 50,
    "total_bets": 38,
    "total_skipped": 12,
    "wins": 22,
    "losses": 16,
    "win_rate": 0.58,
    "total_pnl": 145.30,
    "roi": 0.08,
    "calibration": {
      "brier_score": 0.2134,
      "calibration_error": 0.0456,
      "total_predictions": 38,
      "bins": [...]
    },
    "optimization_changes": { ... },
    "market_results": [...]
  }
}
```

---

### POST /api/polymarket/backtest/incremental

Run an incremental backtest that optimizes the strategy between batches.

**Request body:**

```json
{
  "batch_size": 10,
  "total_batches": 5
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `batch_size` | int | `10` | Markets per batch. |
| `total_batches` | int | `5` | Number of batches. Strategy is re-optimized between each. |

**Response (202 Accepted):**

```json
{
  "success": true,
  "task_id": "ibt_abc123",
  "status": "running"
}
```

The completed result includes per-batch results showing how the strategy improves over time, plus an aggregate summary.

---

### GET /api/polymarket/backtest/results

Get the latest backtest results without needing a task ID.

**Response:**

```json
{
  "success": true,
  "data": {
    "latest": { ... },
    "incremental": {
      "batches": [...],
      "summary": {
        "total_bets": 45,
        "wins": 26,
        "losses": 19,
        "win_rate": 0.578,
        "total_pnl": 234.50,
        "roi": 0.052
      }
    }
  }
}
```

---

### POST /api/polymarket/backtest/reset

Clear all backtest data for a fresh run.

**Response:**

```json
{
  "success": true,
  "message": "Backtest data reset"
}
```

---

## Decision Ledger

### GET /api/polymarket/ledger/entries

Get ledger entries with optional filters.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | (none) | Filter by entry type: `BET_PLACED`, `BET_SKIPPED`, `BET_RESOLVED`, `DEEP_CONFIRMED`, `DEEP_REJECTED`, `PARAM_CHANGED`, `CALIBRATION_UPDATE`, `CYCLE_SUMMARY` |
| `market_id` | string | (none) | Filter by market slug. |
| `cycle_id` | string | (none) | Filter by autopilot cycle ID. |
| `limit` | int | `100` | Max entries to return. |
| `offset` | int | `0` | Entries to skip (for pagination). |

**Response:**

```json
{
  "success": true,
  "data": {
    "entries": [
      {
        "id": "uuid-string",
        "timestamp": "2025-03-20T10:30:00+00:00",
        "entry_type": "BET_PLACED",
        "market_id": "will-bitcoin-reach-100k-in-2025",
        "question": "Will Bitcoin reach $100k in 2025?",
        "data": {
          "side": "YES",
          "amount": 150.0,
          "odds": 0.65,
          "edge": 0.07,
          "kelly_fraction": 0.032
        },
        "explanation": "Edge of 7% exceeds threshold; Kelly suggests 3.2% allocation.",
        "cycle_id": "cycle_a1b2c3d4"
      }
    ],
    "count": 1
  }
}
```

---

### GET /api/polymarket/ledger/recent

Get the most recent entries across all types.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `20` | Number of recent entries. |

---

### GET /api/polymarket/ledger/stats

Get a summary of ledger contents.

**Response:**

```json
{
  "success": true,
  "data": {
    "total_entries": 156,
    "entries_by_type": {
      "BET_PLACED": 45,
      "BET_SKIPPED": 30,
      "BET_RESOLVED": 38,
      "DEEP_CONFIRMED": 12,
      "DEEP_REJECTED": 8,
      "CYCLE_SUMMARY": 15,
      "PARAM_CHANGED": 5,
      "CALIBRATION_UPDATE": 3
    },
    "last_cycle_id": "cycle_a1b2c3d4",
    "last_entry_timestamp": "2025-03-20T10:30:00+00:00",
    "total_cycles": 15
  }
}
```

---

### GET /api/polymarket/ledger/search

Search ledger entries by text (matches against question and explanation fields).

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | required | Search query (case-insensitive). |
| `limit` | int | `50` | Max results. |

**Response:**

```json
{
  "success": true,
  "data": {
    "entries": [...],
    "count": 5,
    "query": "bitcoin"
  }
}
```

---

### GET /api/polymarket/ledger/cycle/{cycle_id}

Get all entries belonging to a specific autopilot cycle.

**Response:**

```json
{
  "success": true,
  "data": {
    "entries": [...],
    "count": 12,
    "cycle_id": "cycle_a1b2c3d4"
  }
}
```

---

## Cost

### GET /api/polymarket/cost/estimate

Estimate cost for a single deep prediction with the current pipeline configuration.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `rounds` | int | `15` | Simulation rounds. |
| `agents` | int | `10` | Number of agents in the simulation. |

**Response:**

```json
{
  "success": true,
  "data": {
    "total_cost_usd": 0.4215,
    "total_tokens": 111000,
    "stages": [
      {
        "stage": "ontology",
        "model": "deepseek-chat",
        "input_tokens": 3000,
        "output_tokens": 2000,
        "cost_usd": 0.001
      },
      {
        "stage": "simulation",
        "model": "gpt-4o",
        "input_tokens": 40000,
        "output_tokens": 20000,
        "cost_usd": 0.3
      }
    ],
    "model_breakdown": {
      "deepseek-chat": 0.0045,
      "gemini-2.0-flash": 0.0021,
      "gpt-4o": 0.4149
    }
  }
}
```

---

### GET /api/polymarket/cost/compare

Compare cost across all available presets and model configurations.

**Query parameters:** Same as `/cost/estimate`.

**Response:**

```json
{
  "success": true,
  "data": {
    "current_hybrid": { ... },
    "alternatives": {
      "all_gpt4o": { "cost_usd": 0.58, "model": "gpt-4o", "label": "All GPT-4o" },
      "all_deepseek": { "cost_usd": 0.02, "model": "deepseek-chat", "label": "All DeepSeek V3" }
    },
    "presets": {
      "balanced": {
        "label": "Balanced (recommended)",
        "description": "DeepSeek prep + Gemini profiles + GPT-4o sim/report",
        "stages": { "ontology": "deepseek-chat", ... },
        "cost_usd": 0.4215,
        "cost_50": 21.08,
        "active": true
      }
    },
    "savings_vs_gpt4o_percent": 27.3,
    "cost_for_50_predictions": 21.08,
    "active_preset": "balanced",
    "available_models": {
      "gpt-4o": { "input": 2.50, "output": 10.00, "provider": "openai" },
      "deepseek-chat": { "input": 0.14, "output": 0.28, "provider": "deepseek" }
    }
  }
}
```

---

### GET /api/polymarket/cost/batch

Estimate cost for a batch of predictions.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `num` | int | `50` | Number of predictions in the batch. |
| `rounds` | int | `15` | Simulation rounds per prediction. |
| `agents` | int | `10` | Agents per simulation. |

**Response:**

```json
{
  "success": true,
  "data": {
    "per_prediction": 0.4215,
    "total": 21.08,
    "num_predictions": 50,
    "stages": [...]
  }
}
```

---

### GET /api/polymarket/pipeline/config

Get the current pipeline model configuration (API keys are redacted).

**Response:**

```json
{
  "success": true,
  "data": {
    "ontology": {
      "model": "deepseek-chat",
      "base_url": "https://api.deepseek.com",
      "has_api_key": true,
      "price_input": 0.14,
      "price_output": 0.28
    },
    "graph": { ... },
    "profiles": { ... },
    "simulation": { ... },
    "report": { ... }
  }
}
```

---

## Predictions & Calibration

### GET /api/polymarket/predictions

Get all recent predictions with details.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `50` | Maximum number of predictions to return. |

**Response:**

```json
{
  "success": true,
  "data": {
    "predictions": [
      {
        "market_id": "will-bitcoin-reach-100k-in-2025",
        "question": "Will Bitcoin reach $100k in 2025?",
        "predicted_prob": 0.72,
        "market_prob": 0.65,
        "edge": 0.07,
        "signal": "BUY_YES",
        "reliability": "high",
        "timestamp": "2025-03-20T10:30:00"
      }
    ],
    "count": 25
  }
}
```

---

### GET /api/polymarket/calibration

Get current calibration statistics including Brier score and calibration bins.

**Response:**

```json
{
  "success": true,
  "data": {
    "brier_score": 0.2134,
    "calibration_error": 0.0456,
    "total_predictions": 50,
    "bins": [
      {
        "range": "0%-10%",
        "predicted_mean": 0.08,
        "actual_rate": 0.05,
        "count": 4
      }
    ]
  }
}
```

---

### GET /api/polymarket/strategy

Get current strategy optimizer configuration.

**Response:**

```json
{
  "success": true,
  "data": {
    "min_edge_threshold": 0.03,
    "max_bet_pct": 0.05,
    "kelly_factor": 0.25,
    "odds_range": [0.10, 0.90],
    "category_weights": { ... },
    "confidence_multipliers": { ... }
  }
}
```

---

## Signals & Stats

### GET /api/polymarket/signals

Get current prediction signals sorted by edge size.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `min_edge` | float | `0.05` | Minimum absolute edge to include. |

**Response:**

```json
{
  "success": true,
  "data": {
    "signals": [
      {
        "market_id": "some-market",
        "question": "Will X happen?",
        "predicted_prob": 0.72,
        "market_prob": 0.60,
        "edge": 0.12,
        "signal": "BUY_YES",
        "reliability": "high",
        "ensemble_std": 0.035,
        "num_variants": 3,
        "timestamp": "2025-03-20T10:30:00"
      }
    ],
    "count": 5
  }
}
```

---

### GET /api/polymarket/stats

Get summary statistics across all predictions.

**Response:**

```json
{
  "success": true,
  "data": {
    "total_predictions": 100,
    "total_resolutions": 75,
    "matched": 70,
    "accuracy": 0.614,
    "signals": {
      "buy_yes": 40,
      "buy_no": 35,
      "skip": 25
    }
  }
}
```

---

## Logs

### GET /api/polymarket/logs/stream

Server-Sent Events (SSE) endpoint for real-time log streaming. Stays open indefinitely.

**Usage:**

```javascript
const eventSource = new EventSource('/api/polymarket/logs/stream');
eventSource.onmessage = (event) => {
  const log = JSON.parse(event.data);
  console.log(`[${log.level}] ${log.msg}`);
};
```

**Event format:**

```json
{
  "ts": 1710934200.123,
  "msg": "Fetching market: will-bitcoin-reach-100k",
  "level": "info"
}
```

Log levels: `info`, `success`, `error`, `warning`

The connection sends a keepalive comment every 15 seconds if no logs are available.

---

## Trading Loop

### POST /api/polymarket/loop/start

Start the automated paper trading loop.

**Request body:**

```json
{
  "interval_hours": 6.0
}
```

---

### POST /api/polymarket/loop/stop

Stop the trading loop.

---

### POST /api/polymarket/loop/run-once

Run a single trading cycle immediately.

**Request body (optional):**

```json
{
  "prefer_deep": true
}
```

**Response (202 Accepted):**

```json
{
  "success": true,
  "task_id": "cyc_abc123",
  "status": "running"
}
```

---

### GET /api/polymarket/loop/status

Get the current loop status.

---

### GET /api/polymarket/loop/log

Get recent loop log entries.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `50` | Number of log entries. |

---

## Monte Carlo Simulation

### POST /api/polymarket/monte-carlo/run

Run a Monte Carlo portfolio simulation to evaluate viability across parameter combinations. Fetches resolved markets from Polymarket and simulates thousands of portfolio paths.

**Request body:**

```json
{
  "num_simulations": 1000,
  "num_bets": 50,
  "accuracies": [0.52, 0.55, 0.58, 0.60, 0.65],
  "edge_thresholds": [0.03, 0.05, 0.08, 0.10],
  "kelly_factors": [0.15, 0.25, 0.50]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `num_simulations` | int | `1000` | Monte Carlo runs per parameter combination. |
| `num_bets` | int | `50` | Number of bets per simulated portfolio path. |
| `accuracies` | list[float] | (default sweep) | Accuracy levels to test. |
| `edge_thresholds` | list[float] | (default sweep) | Edge thresholds to test. |
| `kelly_factors` | list[float] | (default sweep) | Kelly fractions to test. |

**Response (202 Accepted):**

```json
{
  "success": true,
  "task_id": "mc_abc123",
  "status": "running"
}
```

---

### GET /api/polymarket/monte-carlo/run/{task_id}

Check Monte Carlo simulation status. Returns progress during execution and full results when complete.

**Response (running):**

```json
{
  "success": true,
  "task_id": "mc_abc123",
  "status": "running",
  "progress": {
    "markets_loaded": 150,
    "combo_index": 24,
    "total_combos": 60,
    "percent": 40.0,
    "current": "accuracy=0.58, edge=0.05, kelly=0.25"
  }
}
```

**Response (completed):**

```json
{
  "success": true,
  "task_id": "mc_abc123",
  "status": "completed",
  "result": {
    "sweep_results": [...],
    "break_even": {
      "accuracy": 0.56,
      "edge_threshold": 0.05,
      "kelly_factor": 0.25,
      "probability_of_profit": 0.62
    },
    "best_config": { ... }
  }
}
```

---

### GET /api/polymarket/monte-carlo/results

Get the latest Monte Carlo results without needing a task ID. Results are cached in memory and persisted to `data/monte_carlo_results.json`.

**Response:**

```json
{
  "success": true,
  "data": {
    "sweep_results": [...],
    "break_even": { ... },
    "best_config": { ... }
  }
}
```

---

## Overnight Runner

### POST /api/polymarket/overnight/start

Start a resilient overnight calibration run. Runs N deep predictions with crash recovery -- if the process is interrupted, it resumes from the last checkpoint.

**Request body:**

```json
{
  "total": 50,
  "budget": 25.0
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `total` | int | `50` | Total number of deep predictions to run. |
| `budget` | float | `25.0` | Maximum budget in USD. Stops when exceeded. |

**Response (202 Accepted):**

```json
{
  "success": true,
  "status": "started",
  "total": 50,
  "budget": 25.0
}
```

---

### POST /api/polymarket/overnight/stop

Gracefully stop the overnight run after the current prediction completes. Does not abort mid-prediction.

**Response:**

```json
{
  "success": true,
  "status": "stop_requested"
}
```

---

### GET /api/polymarket/overnight/status

Get the current state of the overnight run, including progress, costs, and recent results.

**Response:**

```json
{
  "success": true,
  "data": {
    "run_id": "overnight_20250325_220000",
    "mode": "overnight",
    "status": "running",
    "current_round": 12,
    "completed": 11,
    "failed": 1,
    "skipped": 0,
    "total_target": 50,
    "total_cost_usd": 4.62,
    "max_budget_usd": 25.0,
    "current_market": "will-bitcoin-reach-100k",
    "current_phase": "predicting",
    "started_at": "2025-03-25T22:00:00+00:00",
    "last_checkpoint_at": "2025-03-25T23:15:00+00:00",
    "results_count": 12,
    "recent_results": [...],
    "recent_errors": [...],
    "strategy_version": 3
  }
}
```

---

### GET /api/polymarket/overnight/results

Get all overnight prediction results with summary statistics.

**Response:**

```json
{
  "success": true,
  "data": {
    "results": [...],
    "summary": {
      "completed": 45,
      "failed": 3,
      "total_cost_usd": 18.90,
      "avg_cost": 0.42,
      "predictions_with_edge": 28,
      "bets_placed": 22
    }
  }
}
```

---

## Rolling Loop

### POST /api/polymarket/rolling/start

Start a continuous rolling trading loop that runs prediction rounds at a configurable interval. Unlike the overnight runner (which runs a fixed number of predictions), the rolling loop runs indefinitely until stopped.

**Request body:**

```json
{
  "round_interval": 3600,
  "deep_per_round": 3,
  "budget_per_round": 12.0,
  "max_budget": 100.0
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `round_interval` | int | `3600` | Seconds between rounds. |
| `deep_per_round` | int | `3` | Deep predictions per round. |
| `budget_per_round` | float | `12.0` | Budget cap per round in USD. |
| `max_budget` | float | `100.0` | Total budget cap across all rounds. |

**Response (202 Accepted):**

```json
{
  "success": true,
  "status": "started"
}
```

---

### POST /api/polymarket/rolling/stop

Gracefully stop the rolling loop after the current round completes.

**Response:**

```json
{
  "success": true,
  "status": "stop_requested"
}
```

---

## Method Tracker

### GET /api/polymarket/methods/performance

Get aggregated performance comparison between LLM predictions, quantitative predictions, and the combined blend.

**Response:**

```json
{
  "success": true,
  "data": {
    "llm": {
      "method": "llm",
      "total_predictions": 45,
      "resolved": 30,
      "correct": 18,
      "accuracy": 0.60,
      "avg_brier": 0.2134
    },
    "quant": {
      "method": "quant",
      "total_predictions": 45,
      "resolved": 30,
      "correct": 20,
      "accuracy": 0.667,
      "avg_brier": 0.1945
    },
    "combined": {
      "method": "combined",
      "total_predictions": 45,
      "resolved": 30,
      "correct": 21,
      "accuracy": 0.70,
      "avg_brier": 0.1823
    }
  }
}
```

---

### GET /api/polymarket/methods/comparisons

Get recent individual prediction comparisons showing both methods side-by-side.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `limit` | int | `20` | Number of recent comparisons to return. |

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "market_id": "will-bitcoin-reach-100k",
      "question": "Will Bitcoin reach $100k in 2025?",
      "llm_prediction": 0.72,
      "quant_prediction": 0.65,
      "combined_prediction": 0.68,
      "market_odds": 0.60,
      "resolved": true,
      "outcome_yes": true,
      "llm_correct": true,
      "quant_correct": true
    }
  ]
}
```

---

### GET /api/polymarket/methods/weights

Get the current blending weights used to combine LLM and quantitative predictions.

**Response:**

```json
{
  "success": true,
  "data": {
    "llm_weight": 0.5,
    "quant_weight": 0.5
  }
}
```
