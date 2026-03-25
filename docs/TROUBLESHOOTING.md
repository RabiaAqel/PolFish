# Troubleshooting

## Common Issues

### "Market not found" errors

**Symptom:** `Market 'xxx' not found on Polymarket` when running a prediction.

**Cause:** The system looks up markets by slug on the Polymarket Gamma API. Slugs are case-sensitive and must match exactly.

**Fixes:**

1. **If you pasted a full URL:** The system auto-extracts slugs from URLs like `https://polymarket.com/event/your-slug`. If the URL has query parameters or a different path format, extraction may fail. Try passing just the slug portion.

2. **Event URL vs. market slug:** Polymarket event pages may contain multiple markets. The slug from the URL bar is the *event* slug, not the individual market slug. If the event has sub-markets, you may need the specific market's `conditionId` instead.

3. **Market may have been removed or renamed:** Polymarket occasionally removes or renames markets. Check that the market still exists by visiting the URL directly.

4. **URL parsing regex:** The system uses this pattern to extract slugs:
   ```python
   re.search(r"polymarket\.com/event/([^/?#]+)", slug)
   ```
   If your URL does not match this pattern, strip it down to just the slug.

---

### "Insufficient quota" / OpenAI billing errors

**Symptom:** HTTP 429 or "insufficient_quota" errors from the OpenAI API.

**Cause:** Your OpenAI account does not have enough credits or has hit a rate limit.

**Fixes:**

1. Check your usage at [platform.openai.com/usage](https://platform.openai.com/usage)
2. Add billing payment method if not already set up
3. Verify your API key is correct in `.env`:
   ```
   LLM_API_KEY=sk-proj-...
   ```
4. Switch to a cheaper preset while debugging:
   ```
   PIPELINE_PRESET=cheapest
   ```
5. If using per-stage overrides, make sure the correct provider's API key is set. For example, if `SIMULATION_MODEL=gemini-2.5-flash`, you need `GEMINI_API_KEY` set.

---

### "No markets found" during scanning

**Symptom:** The scanner returns 0 markets, autopilot cycle produces no candidates.

**Cause:** Filter settings are too restrictive, or the Polymarket API returned unexpected data.

**Fixes:**

1. **Relax the time window:** Increase `days_ahead` in autopilot config:
   ```json
   { "days_ahead": 14.0 }
   ```

2. **Lower volume threshold:** Many interesting markets have low volume:
   ```json
   { "min_volume": 100 }
   ```

3. **Check the Polymarket API directly:**
   ```bash
   curl "https://gamma-api.polymarket.com/events?active=true&limit=10"
   ```
   If this returns empty or errors, Polymarket's API may be experiencing issues.

4. **Odds range filtering:** The scanner filters out markets with YES odds below 0.15 or above 0.85 (effectively decided markets). If all available markets are in this range, no results will pass.

---

### Resolution not detecting settled markets

**Symptom:** Markets have clearly resolved on Polymarket but the auto-resolver does not pick them up.

**Cause:** The resolver checks the market's `resolution` field and outcome prices. Polymarket may take time to officially resolve a market after the event occurs.

**How resolution detection works:**

1. The resolver fetches the market by slug
2. Checks if `market.closed` is True
3. Looks for a `resolution` string ("yes"/"no")
4. If no explicit resolution, infers from outcome prices (YES price >= 0.95 = resolved YES)
5. If outcome prices are ambiguous (between 0.05 and 0.95), the market is treated as unresolved

**Fixes:**

1. **Wait:** Some markets take hours or days to officially resolve after the event. The auto-resolver runs every 5 minutes.

2. **Manual trigger:** Call the resolve endpoint directly:
   ```bash
   curl -X POST http://localhost:5001/api/polymarket/portfolio/resolve
   ```

3. **Check market status:** If the market shows as resolved on the Polymarket website but not in your system, the API data may be stale. The Gamma API sometimes delays resolution data.

---

### Deep prediction timeout

**Symptom:** Deep prediction task stays in "running" state for 10+ minutes, or the connection times out.

**Cause:** The full MiroFish pipeline (ontology + graph + simulation + report) can take 3-8 minutes depending on the model and simulation rounds. Each step involves multiple API calls with polling.

**Fixes:**

1. **Be patient:** A 3-variant deep prediction with 15 rounds can legitimately take 5-10 minutes. Monitor progress via the SSE log stream:
   ```javascript
   const es = new EventSource('/api/polymarket/logs/stream');
   es.onmessage = (e) => console.log(JSON.parse(e.data).msg);
   ```

2. **Reduce complexity:**
   ```bash
   # Fewer rounds
   PREDICTOR_MAX_ROUNDS=8

   # Fewer variants
   curl -X POST /api/polymarket/predict/deep \
     -d '{"slug": "...", "variants": 1}'
   ```

3. **Check MiroFish backend:** The pipeline makes HTTP calls to `http://localhost:5001/api`. If the MiroFish backend is not running or is overloaded, steps will fail. Check:
   ```bash
   curl http://localhost:5001/api/graph/ontology/generate  # Should return method not allowed, not connection refused
   ```

4. **Check task status:** Poll the task endpoint to see which step is stuck:
   ```bash
   curl http://localhost:5001/api/polymarket/predict/deep/YOUR_TASK_ID
   ```
   The `step` field shows: `fetching_market`, `building_graph`, `setting_up`, `running_simulation`, `generating_report`, `extracting_prediction`

---

### Duplicate bets on the same market

**Symptom:** Multiple paper bets placed on the same market.

**How dedup works:** The system does NOT have built-in deduplication for bets. Each call to `place_bet()` creates a new `BetRecord` with a unique `bet_id` (generated from `market_id` + timestamp). This is by design -- you might want multiple bets at different odds as the market moves.

**If you want to avoid duplicates:**

1. Check open positions before betting:
   ```bash
   curl http://localhost:5001/api/polymarket/portfolio | jq '.data.open_positions[].slug'
   ```

2. The autopilot engine tracks which markets it has already processed within a cycle, but does NOT check across cycles. If the same market appears in consecutive scans (common for multi-day markets), it may generate another bet.

3. To limit exposure, configure:
   ```json
   { "max_bet_pct": 0.02 }
   ```
   This caps each bet at 2% of balance regardless of Kelly sizing.

---

### Portfolio reset warning

**Symptom:** After resetting the portfolio, old data persists or the balance is wrong.

**What reset does:**

1. Deletes `polymarket_predictor/data/portfolio.jsonl`
2. Re-creates a fresh `PaperPortfolio` instance with $10,000
3. Resets the global `_autopilot` instance (so it picks up the new portfolio)

**What reset does NOT do:**

- Does NOT clear the decision ledger (`decision_ledger.jsonl`)
- Does NOT clear prediction history (`predictions.jsonl`, `resolutions.jsonl`)
- Does NOT clear the strategy optimizer config (`strategy.json`)
- Does NOT clear backtest data (stored in `data/backtest/`)

**To do a full system reset:**

```bash
rm -f polymarket_predictor/data/portfolio.jsonl
rm -f polymarket_predictor/data/decision_ledger.jsonl
rm -f polymarket_predictor/data/predictions.jsonl
rm -f polymarket_predictor/data/resolutions.jsonl
rm -f polymarket_predictor/data/strategy.json
rm -f polymarket_predictor/data/autopilot_config.json
rm -rf polymarket_predictor/data/backtest/
```

Then restart the backend.

---

### CORS / proxy issues

**Symptom:** Frontend at `localhost:3000` cannot reach backend at `localhost:5001`. Browser console shows CORS errors.

**Fixes:**

1. **Vite proxy:** The frontend Vite dev server should be configured to proxy `/api` requests to the backend. Check `MiroFish/frontend/vite.config.js` for a proxy configuration:
   ```javascript
   server: {
     proxy: {
       '/api': 'http://localhost:5001'
     }
   }
   ```

2. **Direct access:** If using the API directly (curl, Postman), CORS does not apply. CORS only affects browser-based requests.

3. **Flask CORS:** If the backend does not have flask-cors configured, add it:
   ```python
   from flask_cors import CORS
   app = Flask(__name__)
   CORS(app)
   ```

---

### Backend won't start -- circular import

**Symptom:** `ImportError` or `AttributeError` when starting the Flask backend, often mentioning `AutopilotEngine` or `TradingLoop`.

**Cause:** The `dashboard/api.py` module lazily imports `AutopilotEngine` and `TradingLoop` to avoid circular imports. If the import chain is broken (e.g., a module references something before it is defined), Python raises an error at import time.

**Fixes:**

1. **Check the lazy import pattern:** `_get_autopilot()` and `_get_loop()` use a global variable that is initialized on first call:
   ```python
   def _get_autopilot():
       global _autopilot
       if _autopilot is None:
           from polymarket_predictor.autopilot.engine import AutopilotEngine
           _autopilot = AutopilotEngine(...)
       return _autopilot
   ```

2. **Test the import chain manually:**
   ```bash
   cd /path/to/mirofish
   python -c "from polymarket_predictor.dashboard.api import dashboard_bp; print('OK')"
   ```

3. **Common culprit:** If you add a new top-level import in `dashboard/api.py` that pulls in a module which itself imports from `dashboard/api.py`, you create a circular dependency. Keep heavy imports inside functions.

---

### "Model not found" or API provider errors

**Symptom:** `404 Not Found` or `invalid_model` errors from an LLM provider.

**Fixes:**

1. **Verify model name:** Check that the model string in `MODEL_PRICING` matches the provider's actual model ID. Provider model names can change.

2. **Check provider base URL:** Each provider has a specific base URL format:
   ```
   OpenAI:    https://api.openai.com/v1
   DeepSeek:  https://api.deepseek.com
   Gemini:    https://generativelanguage.googleapis.com/v1beta/openai
   Anthropic: https://api.anthropic.com/v1
   Mistral:   https://api.mistral.ai/v1
   Groq:      https://api.groq.com/openai/v1
   ```

3. **API key mismatch:** If `SIMULATION_MODEL=gemini-2.5-flash` but `GEMINI_API_KEY` is not set, the system falls back to the primary `LLM_API_KEY` (OpenAI), which will not work with Gemini's base URL.

4. **Check the pipeline config:**
   ```bash
   curl http://localhost:5001/api/polymarket/pipeline/config
   ```
   Verify each stage has `has_api_key: true` and the correct `base_url`.

---

### Backtest shows unrealistic results

**Symptom:** Backtest reports very high win rates (>70%) or unrealistically large PnL.

**Cause:** The quick-mode backtest generates predictions by adding random noise to market odds. Since it knows the true outcome, noise that happens to push in the right direction gets rewarded. This is intentional -- the backtest is designed to test the betting infrastructure and optimization loop, not to measure prediction accuracy.

**What to expect:**
- Quick-mode backtests typically show 50-60% win rates (slightly above random due to edge detection)
- PnL depends heavily on bet sizing parameters
- The incremental backtest shows how the optimizer adjusts parameters across batches

**For realistic accuracy testing:** Use the deep prediction mode (not yet implemented in backtest) or track live paper trading performance over time.

---

### SSE log stream disconnects

**Symptom:** The real-time log stream (`/api/polymarket/logs/stream`) disconnects or stops receiving events.

**Cause:** SSE connections can be interrupted by:
- Nginx/reverse proxy timeouts (common in production)
- Browser tab going to sleep
- Server restart

**Fixes:**

1. **Auto-reconnect in frontend:**
   ```javascript
   function connectLogs() {
     const es = new EventSource('/api/polymarket/logs/stream');
     es.onerror = () => {
       es.close();
       setTimeout(connectLogs, 3000);
     };
     es.onmessage = (e) => { /* handle */ };
   }
   ```

2. **Disable buffering in reverse proxy (Nginx):**
   ```nginx
   location /api/polymarket/logs/stream {
     proxy_pass http://localhost:5001;
     proxy_set_header Connection '';
     proxy_http_version 1.1;
     chunked_transfer_encoding off;
     proxy_buffering off;
     proxy_cache off;
   }
   ```
   The backend already sets `X-Accel-Buffering: no` in the response.

3. **Keepalive:** The server sends a keepalive comment every 15 seconds. If your proxy has a shorter idle timeout, increase it.

---

### Seed generation fails with no articles

**Symptom:** Seed document is generated but contains "No articles available" section.

**Cause:** The `NewsAggregator` uses DuckDuckGo search to find related articles. If the search returns no results (rate limiting, network issues, or very niche topic), the seed is generated without news context.

**Impact:** Predictions without news context rely entirely on the market question and data. This reduces quality for complex or nuanced markets.

**Fixes:**

1. This is usually transient. Retry after a few minutes.
2. DuckDuckGo may rate-limit aggressive scraping. The system fetches 3-5 articles per prediction, which is usually fine.
3. For very niche markets, the search query (derived from the market question) may not match any recent articles. This is expected behavior.

---

## Diagnostic Commands

### Check system health

```bash
# Backend running?
curl http://localhost:5001/api/polymarket/pipeline/config

# Frontend running?
curl http://localhost:3000

# Polymarket API accessible?
curl "https://gamma-api.polymarket.com/events?active=true&limit=1"
```

### Check configuration

```bash
# Current pipeline models and pricing
curl http://localhost:5001/api/polymarket/pipeline/config | python -m json.tool

# Current cost estimate
curl http://localhost:5001/api/polymarket/cost/estimate | python -m json.tool

# Autopilot config
curl http://localhost:5001/api/polymarket/autopilot/config | python -m json.tool
```

### Check data state

```bash
# Portfolio status
curl http://localhost:5001/api/polymarket/portfolio | python -m json.tool

# Ledger summary
curl http://localhost:5001/api/polymarket/ledger/stats | python -m json.tool

# Recent decisions
curl "http://localhost:5001/api/polymarket/ledger/recent?limit=5" | python -m json.tool
```

### Tail the log stream

```bash
curl -N http://localhost:5001/api/polymarket/logs/stream
```

Press Ctrl+C to stop.
