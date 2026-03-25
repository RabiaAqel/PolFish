<template>
  <div class="backtest-page">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1>Backtest Lab <span class="help-icon" @click.stop="showInfo = true">ⓘ</span></h1>
        <span class="subtitle">Test predictions against resolved markets</span>
      </div>
    </header>

    <!-- Info Modal -->
    <teleport to="body">
      <div v-if="showInfo" class="modal-overlay" @click.self="showInfo = false">
        <div class="modal-content">
          <button class="modal-close" @click="showInfo = false">&#10005;</button>
          <h2 class="modal-title">Backtest Lab &mdash; How It Works</h2>
          <div class="modal-warning">
            <span class="modal-warning-icon">&#9888;</span>
            <span>Infrastructure Test Mode</span>
          </div>
          <p class="modal-body">
            This page validates the betting, sizing, and optimization pipeline
            using simulated predictions (not real MiroFish analysis).
          </p>
          <h3 class="modal-section-title"><span class="modal-dot"></span> What It Does</h3>
          <ul class="modal-list">
            <li>Fetches already-resolved markets from Polymarket</li>
            <li>Generates fake predictions (market odds + random noise)</li>
            <li>Places paper bets using Kelly criterion sizing</li>
            <li>Immediately resolves bets (we know the outcome)</li>
            <li>Runs calibration and strategy optimization between batches</li>
          </ul>
          <h3 class="modal-section-title"><span class="modal-dot"></span> What The Numbers Mean</h3>
          <ul class="modal-list">
            <li><strong>Balance:</strong> Starting $10K + cumulative P&amp;L</li>
            <li><strong>Win Rate:</strong> % of bets that were profitable</li>
            <li><strong>ROI:</strong> P&amp;L / Total amount wagered</li>
            <li>The P&amp;L is NOT real alpha &mdash; it's noise</li>
          </ul>
          <h3 class="modal-section-title"><span class="modal-dot"></span> Quick vs Incremental</h3>
          <ul class="modal-list">
            <li><strong>Quick:</strong> Runs all 50 markets at once with fixed strategy</li>
            <li><strong>Incremental:</strong> Runs 5 batches of 10, optimizing strategy between each batch. Shows how the optimizer adjusts parameters over time</li>
          </ul>
          <h3 class="modal-section-title"><span class="modal-dot"></span> To Get Real Predictions</h3>
          <p class="modal-body">
            Use the Predictor page with Deep mode on live markets.
            That runs actual MiroFish agent simulations (~$3-5/market in API tokens).
            Once enough live predictions resolve, the calibrator will learn
            MiroFish's actual biases and improve accuracy.
          </p>
        </div>
      </div>
    </teleport>

    <!-- Honesty disclaimer -->
    <div class="disclaimer">
      <span class="disclaimer-icon">⚠</span>
      <div>
        <strong>Infrastructure test only.</strong> Predictions are simulated (market odds + random noise), not real MiroFish deep analysis. P&amp;L numbers are not meaningful. This validates the betting, sizing, and optimization plumbing — not prediction accuracy.
      </div>
    </div>

    <!-- Controls -->
    <div class="controls">
      <button
        class="btn btn-primary"
        @click="runQuickBacktest"
        :disabled="backtestRunning"
      >
        {{ backtestRunning ? 'Running...' : 'Run Quick Backtest (50 markets)' }}
      </button>
      <button
        class="btn btn-secondary"
        @click="runIncrementalBacktest"
        :disabled="backtestRunning"
      >
        {{ backtestRunning ? 'Running...' : 'Run Incremental (5 batches × 10)' }}
      </button>
      <button
        class="btn btn-secondary"
        @click="resetBacktest"
        :disabled="backtestRunning"
      >
        Reset
      </button>
    </div>

    <!-- Progress -->
    <div v-if="backtestRunning" class="backtest-progress">
      <span class="pulse-dot"></span>
      <span class="progress-text">{{ backtestProgressText }}</span>
    </div>

    <!-- Stats Row (always visible) -->
    <section class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ backtestBalanceDisplay }}</span>
        <span class="stat-label">Balance <span class="tip-wrap tip-below"><span class="help-icon">ⓘ</span><span class="tip-content">Starting $10K + cumulative P&amp;L from resolved backtest bets.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ backtestResults ? (backtestResults.total_bets || 0) : 0 }}</span>
        <span class="stat-label">Total Bets <span class="tip-wrap tip-below"><span class="help-icon">ⓘ</span><span class="tip-content">Number of bets placed. Some markets are skipped if edge is too small.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ backtestWinRate }}</span>
        <span class="stat-label">Win Rate <span class="tip-wrap tip-below"><span class="help-icon">ⓘ</span><span class="tip-content">Percentage of resolved bets that were profitable. Based on simulated predictions, not real alpha.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value" :class="backtestPnlClass">{{ backtestPnlDisplay }}</span>
        <span class="stat-label">Total P&amp;L <span class="tip-wrap tip-below"><span class="help-icon">ⓘ</span><span class="tip-content">Profit &amp; Loss across all resolved bets. Simulated — not real alpha.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value" :class="backtestRoiClass">{{ backtestRoiDisplay }}</span>
        <span class="stat-label">ROI <span class="tip-wrap tip-below"><span class="help-icon">ⓘ</span><span class="tip-content">Return on investment. Total P&amp;L divided by total amount wagered.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ backtestResults && backtestResults.total_wagered ? '$' + backtestResults.total_wagered.toLocaleString(undefined, {maximumFractionDigits:0}) : '$0' }}</span>
        <span class="stat-label">Total Wagered <span class="tip-wrap tip-below"><span class="help-icon">ⓘ</span><span class="tip-content">Sum of all bet amounts placed. Used to calculate ROI.</span></span></span>
      </div>
    </section>

    <!-- Calibration -->
    <div v-if="backtestResults && backtestResults.brier_score != null" class="backtest-calibration">
      <h3 class="subsection-title">Calibration After Backtest <span class="tip-wrap tip-below"><span class="help-icon">ⓘ</span><span class="tip-content">How well the predictions match reality. Lower Brier Score = better. Calibration Error shows average deviation from true probabilities.</span></span></h3>
      <div class="calibration-row">
        <span class="calibration-item">Brier Score: <strong>{{ backtestResults.brier_score?.toFixed(2) || '--' }}</strong></span>
        <span class="calibration-sep">|</span>
        <span class="calibration-item">Calibration Error: <strong>{{ backtestResults.calibration_error?.toFixed(2) || '--' }}</strong></span>
      </div>
    </div>

    <!-- Optimization Changes -->
    <div v-if="backtestResults && backtestResults.optimization_changes && backtestResults.optimization_changes.length > 0" class="backtest-optimization">
      <h3 class="subsection-title">Optimization Changes</h3>
      <ul class="opt-changes">
        <li v-for="(change, i) in backtestResults.optimization_changes" :key="i" class="opt-change">
          <span class="opt-param">{{ change.parameter }}:</span>
          <span class="opt-before">{{ change.before }}</span>
          <span class="opt-arrow">&rarr;</span>
          <span class="opt-after">{{ change.after }}</span>
          <span class="opt-reason" v-if="change.reason">({{ change.reason }})</span>
        </li>
      </ul>
    </div>

    <!-- Incremental Results (shown BEFORE the table) -->
    <div v-if="incrementalBatches.length > 0" class="backtest-incremental">
      <h3 class="subsection-title">Incremental Results</h3>
      <div class="batch-list">
        <div v-for="(batch, i) in incrementalBatches" :key="i" class="batch-row">
          <span class="batch-num">Batch {{ i + 1 }}:</span>
          <span class="batch-bets">{{ batch.total_bets || 0 }} bets,</span>
          <span class="batch-wr">{{ (batch.win_rate > 1 ? batch.win_rate : (batch.win_rate || 0) * 100).toFixed(0) }}% win rate,</span>
          <span :class="(batch.total_pnl || batch.pnl || 0) >= 0 ? 'pnl-pos' : 'pnl-neg'">
            {{ (batch.total_pnl || batch.pnl || 0) >= 0 ? '+' : '' }}${{ Math.abs(batch.total_pnl || batch.pnl || 0).toFixed(2) }} P&amp;L
          </span>
          <span class="batch-note" v-if="batch.note">{{ batch.note }}</span>
        </div>
      </div>
    </div>

    <!-- Individual Bet Results -->
    <div v-if="backtestMarkets.length > 0" class="backtest-trades">
      <h3 class="subsection-title">Backtest Trades <span class="count">{{ backtestMarkets.length }}</span></h3>
      <table class="data-table">
        <thead>
          <tr>
            <th>Market</th>
            <th>Batch</th>
            <th>Odds</th>
            <th>Prediction</th>
            <th>Side</th>
            <th>Amount</th>
            <th>Outcome</th>
            <th>P&amp;L</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(m, i) in backtestMarkets" :key="i" :class="{ 'batch-separator': m._batchStart }">
            <td class="market-cell">
              <a v-if="m.slug" :href="'https://polymarket.com/event/' + m.slug" target="_blank" rel="noopener" class="market-link">{{ m.question || '?' }}</a>
              <span v-else>{{ m.question || '?' }}</span>
            </td>
            <td><span v-if="m._batch" class="batch-tag">{{ m._batch }}</span></td>
            <td>{{ ((m.odds || 0) * 100).toFixed(0) }}%</td>
            <td>{{ ((m.prediction || 0) * 100).toFixed(0) }}%</td>
            <td>
              <span v-if="m.bet_side" class="side-badge" :class="m.bet_side === 'YES' ? 'side-yes' : 'side-no'">{{ m.bet_side }}</span>
              <span v-else style="color:#999">--</span>
            </td>
            <td>{{ m.bet_amount > 0 ? '$' + m.bet_amount.toFixed(0) : '--' }}</td>
            <td>
              <span v-if="m.outcome === 'win'" class="outcome-badge outcome-win">WIN</span>
              <span v-else-if="m.outcome === 'loss'" class="outcome-badge outcome-loss">LOSS</span>
              <span v-else style="color:#999">skip</span>
            </td>
            <td :class="(m.pnl || 0) > 0 ? 'pnl-pos' : (m.pnl || 0) < 0 ? 'pnl-neg' : ''">
              {{ m.pnl !== 0 ? ((m.pnl >= 0 ? '+$' : '-$') + Math.abs(m.pnl).toFixed(0)) : '--' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

// --- State ---
const showInfo = ref(false)
const backtestRunning = ref(false)
const backtestResults = ref(null)
const incrementalBatches = ref([])
const backtestProgress = ref({ current: 0, total: 0 })
let backtestPollTimer = null

// --- API helper ---
const api = async (path, opts = {}) => {
  try {
    const res = await fetch(`/api/polymarket${path}`, opts)
    return await res.json()
  } catch { return { success: false } }
}

// --- Computed ---
const backtestProgressText = computed(() => {
  const p = backtestProgress.value
  if (p.current_batch != null) {
    return `Batch ${p.current_batch}/${p.total_batches} — market ${p.batch_current || 0}/${p.batch_total || 0}`
  }
  return `Backtesting ${p.current || 0}/${p.total || 0}...`
})

const backtestWinRate = computed(() => {
  const wr = backtestResults.value?.win_rate
  if (wr == null) return '0.0%'
  const pct = wr > 1 ? wr : wr * 100
  return pct.toFixed(1) + '%'
})

const backtestPnlDisplay = computed(() => {
  const pnl = backtestResults.value?.total_pnl || backtestResults.value?.pnl || 0
  return (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(2)
})

const backtestPnlClass = computed(() => (backtestResults.value?.total_pnl || backtestResults.value?.pnl || 0) >= 0 ? 'pnl-pos' : 'pnl-neg')

const backtestBalanceDisplay = computed(() => {
  const pnl = backtestResults.value?.total_pnl || backtestResults.value?.pnl || 0
  const balance = 10000 + pnl
  return '$' + balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
})

const backtestRoiDisplay = computed(() => {
  const r = backtestResults.value?.roi
  if (r == null) return '0.0%'
  const pct = Math.abs(r) > 2 ? r : r * 100
  return (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%'
})

const backtestRoiClass = computed(() => (backtestResults.value?.roi || 0) >= 0 ? 'pnl-pos' : 'pnl-neg')

const backtestMarkets = computed(() => {
  // If incremental, tag each market with its batch number
  const batches = incrementalBatches.value
  if (batches.length > 0) {
    const tagged = []
    for (let bi = 0; bi < batches.length; bi++) {
      const batchMarkets = batches[bi].market_results || []
      for (let mi = 0; mi < batchMarkets.length; mi++) {
        tagged.push({
          ...batchMarkets[mi],
          _batch: bi + 1,
          _batchStart: mi === 0
        })
      }
    }
    return tagged
  }
  // Quick mode — no batch tagging
  const mr = backtestResults.value?.market_results || []
  return [...mr].sort((a, b) => {
    if (a.outcome === 'skipped' && b.outcome !== 'skipped') return 1
    if (a.outcome !== 'skipped' && b.outcome === 'skipped') return -1
    return 0
  })
})

// --- Actions ---
const pollBacktestStatus = (taskId) => {
  const poll = async () => {
    const data = await api(`/backtest/run/${taskId}`)
    if (!data.success) return
    if (data.progress) backtestProgress.value = data.progress
    if (data.status === 'completed' || data.status === 'failed') {
      backtestRunning.value = false
      if (data.status === 'completed' && data.result) {
        if (data.result.summary) {
          backtestResults.value = data.result.summary
        } else {
          backtestResults.value = data.result
        }
        if (data.result.batches) {
          incrementalBatches.value = data.result.batches
        }
      }
      return
    }
    backtestPollTimer = setTimeout(poll, 2000)
  }
  backtestPollTimer = setTimeout(poll, 2000)
}

const runQuickBacktest = async () => {
  backtestRunning.value = true
  backtestResults.value = null
  incrementalBatches.value = []
  backtestProgress.value = { current: 0, total: 50 }
  const data = await api('/backtest/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ num_markets: 50, mode: 'quick' }),
  })
  if (data.success && data.task_id) {
    pollBacktestStatus(data.task_id)
  } else {
    backtestRunning.value = false
  }
}

const runIncrementalBacktest = async () => {
  backtestRunning.value = true
  backtestResults.value = null
  incrementalBatches.value = []
  backtestProgress.value = { current_batch: 0, total_batches: 5 }
  const data = await api('/backtest/incremental', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ batch_size: 10, total_batches: 5 }),
  })
  if (data.success && data.task_id) {
    pollBacktestStatus(data.task_id)
  } else {
    backtestRunning.value = false
  }
}

const resetBacktest = async () => {
  await api('/backtest/reset', { method: 'POST' })
  backtestResults.value = null
  incrementalBatches.value = []
  backtestProgress.value = { current: 0, total: 0 }
}

// --- Fetch existing results on mount ---
const fetchBacktestResults = async () => {
  const data = await api('/backtest/results')
  if (data.success && data.data) {
    if (data.data.latest) {
      backtestResults.value = data.data.latest
    }
    if (data.data.incremental && data.data.incremental.batches) {
      incrementalBatches.value = data.data.incremental.batches
    }
  }
}

onMounted(() => {
  fetchBacktestResults()
})

onUnmounted(() => {
  if (backtestPollTimer) clearTimeout(backtestPollTimer)
})
</script>

<style scoped>
.backtest-page {
  font-family: 'Space Grotesk', 'JetBrains Mono', monospace;
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 24px 60px;
  color: var(--black, #1a1a1a);
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 32px;
}
.header h1 { font-size: 28px; font-weight: 700; margin: 0; }
.subtitle { color: #999; font-size: 14px; }

.disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  margin-bottom: 24px;
  background: #fff8e1;
  border: 1px solid #ffe082;
  font-size: 12px;
  line-height: 1.5;
  color: #6d4c00;
}
.disclaimer-icon { font-size: 16px; flex-shrink: 0; margin-top: 1px; }
.disclaimer strong { color: #4e3600; }

.controls {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 32px;
}

.btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  padding: 10px 20px;
  border: 2px solid var(--black, #1a1a1a);
  cursor: pointer;
  transition: all 0.15s;
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-primary { background: var(--black, #1a1a1a); color: #fff; }
.btn-primary:hover:not(:disabled) { background: #333; }
.btn-secondary { background: #fff; color: var(--black, #1a1a1a); }
.btn-secondary:hover:not(:disabled) { background: #f5f5f5; }

.backtest-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #666;
}
.progress-text { color: var(--black, #1a1a1a); }

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #28a745;
  animation: pulse 1.5s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.stats-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}
.stat-card {
  border: 1px solid var(--border, #E5E5E5);
  padding: 16px;
  display: flex;
  flex-direction: column;
}
.stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 700;
}
.stat-label { font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

.pnl-pos { color: #28a745; }
.pnl-neg { color: #dc3545; }

.subsection-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #999;
  margin-bottom: 10px;
}
.subsection-title .count {
  background: var(--border, #E5E5E5);
  padding: 2px 8px;
  border-radius: 2px;
  font-size: 12px;
  color: #666;
}

.backtest-calibration,
.backtest-optimization,
.backtest-incremental,
.backtest-trades {
  margin-top: 20px;
  margin-bottom: 20px;
}

.calibration-row {
  display: flex;
  align-items: center;
  gap: 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  padding: 10px 12px;
  background: #fafafa;
  border: 1px solid var(--border, #E5E5E5);
}
.calibration-item strong { color: var(--black, #1a1a1a); }
.calibration-sep { color: #ccc; }

.opt-changes {
  list-style: none;
  padding: 0;
  margin: 0;
}
.opt-change {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  padding: 6px 12px;
  border-left: 3px solid #f5a623;
  margin-bottom: 4px;
  background: #fafafa;
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.opt-param { font-weight: 700; color: var(--black, #1a1a1a); }
.opt-before { color: #999; }
.opt-arrow { color: #f5a623; font-weight: 700; }
.opt-after { color: var(--black, #1a1a1a); font-weight: 600; }
.opt-reason { color: #999; font-size: 11px; }

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th {
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #999;
  padding: 8px 12px;
  border-bottom: 2px solid var(--black, #1a1a1a);
}
.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border, #E5E5E5);
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}
.market-cell {
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'Space Grotesk', sans-serif !important;
  font-size: 13px !important;
}

.side-badge {
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
}
.side-yes { background: #e8f5e9; color: #28a745; }
.side-no { background: #fbe9e7; color: #dc3545; }

.outcome-badge {
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
}
.outcome-win { background: #28a745; color: #fff; }
.outcome-loss { background: #dc3545; color: #fff; }

.batch-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.batch-row {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  padding: 6px 12px;
  background: #fafafa;
  border: 1px solid var(--border, #E5E5E5);
  display: flex;
  gap: 8px;
  align-items: center;
}
.batch-num { font-weight: 700; color: var(--black, #1a1a1a); }
.batch-bets { color: #888; }
.batch-wr { color: #666; }
.batch-note { color: #999; font-size: 11px; font-style: italic; }

.market-link {
  color: var(--black, #1a1a1a);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.15s;
}
.market-link:hover {
  border-bottom-color: var(--black, #1a1a1a);
}

.batch-tag {
  display: inline-block;
  background: #f0f0f0;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 700;
  border-radius: 2px;
  color: #666;
}

.batch-separator td {
  border-top: 2px solid #ddd;
}

/* ---- Unified info icon ---- */
.help-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: #999;
  font-size: 16px;
  font-style: normal;
  font-family: sans-serif;
  font-weight: 400;
  cursor: pointer;
  margin-left: 5px;
  vertical-align: middle;
  line-height: 1;
  padding: 0;
  flex-shrink: 0;
  transition: color 0.15s;
  text-transform: lowercase;
}
.help-icon:hover { color: #333; }

/* ---- Unified tooltip system ---- */
.tip-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.tip-content {
  display: none;
  position: absolute;
  z-index: 500;
  background: #1a1a1a;
  color: #e5e5e5;
  font-size: 12px;
  font-weight: 400;
  font-family: 'Space Grotesk', sans-serif;
  line-height: 1.5;
  padding: 10px 14px;
  border-radius: 6px;
  width: 280px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.2);
  pointer-events: auto;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
}
.tip-content::before {
  content: '';
  position: absolute;
  bottom: -10px;
  left: 0;
  right: 0;
  height: 10px;
}
.tip-wrap.tip-below .tip-content {
  bottom: auto;
  top: calc(100% + 8px);
}
.tip-wrap.tip-below .tip-content::before {
  bottom: auto;
  top: -10px;
}
.tip-wrap.tip-left .tip-content {
  left: 0;
  transform: none;
}
.tip-wrap:hover .tip-content {
  display: block;
}
.tip-link-text {
  color: #fff;
  text-decoration: underline;
  font-weight: 700;
  font-size: 11px;
  margin-top: 4px;
  display: inline-block;
  cursor: pointer;
}
.tip-link-text:hover { color: #FF4500; }

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.modal-content {
  background: #fff;
  max-width: 640px;
  width: 90%;
  padding: 40px;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
  border-radius: 0;
}
.modal-close {
  position: absolute;
  top: 16px;
  right: 16px;
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #999;
  padding: 4px;
  line-height: 1;
}
.modal-close:hover { color: var(--black, #1a1a1a); }
.modal-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 16px;
}
.modal-warning {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #fff8e1;
  border: 1px solid #ffe082;
  font-size: 13px;
  font-weight: 600;
  color: #6d4c00;
  margin-bottom: 16px;
}
.modal-warning-icon { font-size: 16px; }
.modal-section-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  margin: 20px 0 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.modal-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--black, #1a1a1a);
  flex-shrink: 0;
}
.modal-body {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  line-height: 1.6;
  color: #444;
  margin: 0 0 8px;
}
.modal-list {
  list-style: none;
  padding: 0;
  margin: 0 0 8px;
}
.modal-list li {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  line-height: 1.6;
  color: #444;
  padding-left: 16px;
  position: relative;
  margin-bottom: 2px;
}
.modal-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #f5a623;
}
.modal-list li strong {
  color: var(--black, #1a1a1a);
}
</style>
