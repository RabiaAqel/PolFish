<template>
  <div class="polymarket-container">
    <div class="main-content">
      <!-- 1. Hero / Header -->
      <section class="header-section">
        <div class="tag-row">
          <span class="orange-tag">Prediction Markets</span>
        </div>
        <h1 class="main-title">Polymarket Predictor</h1>
        <p class="subtitle">Analyze prediction markets with MiroFish intelligence</p>
      </section>

      <!-- 2. Predict Section (Main Feature) -->
      <section class="predict-section">
        <div class="predict-input-wrapper">
          <input
            ref="slugInput"
            v-model="predictSlug"
            type="text"
            class="predict-input"
            placeholder="Paste a Polymarket URL or event slug..."
            :disabled="isRunning"
            @keyup.enter="runAnalysis"
          />
        </div>

        <!-- Mode Toggle -->
        <div class="mode-row">
          <div class="mode-toggle">
            <button
              class="mode-btn"
              :class="{ active: mode === 'quick' }"
              @click="mode = 'quick'"
              :disabled="isRunning"
            >
              &#9889; Quick
            </button>
            <button
              class="mode-btn"
              :class="{ active: mode === 'deep' }"
              @click="mode = 'deep'"
              :disabled="isRunning"
            >
              &#128300; Deep
            </button>
          </div>
          <button
            class="analyze-btn"
            @click="runAnalysis"
            :disabled="!predictSlug.trim() || isRunning"
          >
            <span v-if="!isRunning">Analyze</span>
            <span v-else class="btn-loading">
              <span class="spinner spinner-sm"></span>
              Analyzing...
            </span>
          </button>
        </div>

        <div class="mode-description">
          <span v-if="mode === 'quick'">Fetches market data, news articles, and generates a seed document (~5 seconds)</span>
          <span v-else>Runs full MiroFish simulation with agent debates and report generation (~5-10 minutes, uses API tokens)</span>
        </div>

        <!-- Progress Steps -->
        <div v-if="isRunning" class="progress-tracker">
          <div
            v-for="(step, idx) in currentSteps"
            :key="idx"
            class="progress-step"
            :class="{
              completed: idx < currentStepIndex,
              active: idx === currentStepIndex,
              pending: idx > currentStepIndex
            }"
          >
            <div class="step-indicator">
              <span v-if="idx < currentStepIndex" class="step-check">&#10003;</span>
              <span v-else-if="idx === currentStepIndex" class="step-dot-pulse"></span>
              <span v-else class="step-dot"></span>
            </div>
            <span class="step-label">{{ step }}</span>
          </div>
        </div>

        <!-- Error -->
        <div v-if="predictError" class="error-msg">
          <span class="error-icon">&#10005;</span>
          {{ predictError }}
        </div>
      </section>

      <!-- 3. Result Card -->
      <section v-if="predictResult" class="result-section">
        <div class="result-card">
          <!-- Market Info Bar -->
          <div class="result-market-bar">
            <h2 class="result-question">{{ predictResult.question }}</h2>
            <div class="result-badges">
              <span v-if="predictResult.category" class="badge badge-category">{{ predictResult.category }}</span>
              <span v-if="predictResult.volume" class="badge badge-volume">${{ formatVolume(predictResult.volume) }} volume</span>
              <span class="badge badge-mode" :class="predictResult.mode === 'deep' ? 'badge-deep' : 'badge-quick'">
                {{ predictResult.mode === 'deep' ? '&#128300; Deep' : '&#9889; Quick' }}
              </span>
            </div>
          </div>

          <!-- Prediction Comparison -->
          <div class="prediction-comparison">
            <div class="prediction-col">
              <div class="prediction-source">Market Says</div>
              <div class="prediction-number">
                {{ predictResult.marketOdds != null ? (predictResult.marketOdds * 100).toFixed(1) + '%' : '--' }}
              </div>
              <div class="prediction-sublabel">Current Polymarket odds</div>
            </div>

            <div class="prediction-edge-col">
              <div v-if="predictResult.edge != null" class="edge-indicator" :class="predictResult.edge > 0 ? 'edge-up' : predictResult.edge < 0 ? 'edge-down' : 'edge-neutral'">
                <span class="edge-arrow">{{ predictResult.edge > 0 ? '&#9650;' : predictResult.edge < 0 ? '&#9660;' : '&#9644;' }}</span>
                <span class="edge-value">{{ (predictResult.edge > 0 ? '+' : '') + (predictResult.edge * 100).toFixed(1) }}%</span>
                <span class="edge-word">edge</span>
              </div>
              <div v-else class="edge-indicator edge-neutral">
                <span class="edge-value">--</span>
              </div>
            </div>

            <div class="prediction-col">
              <div class="prediction-source">MiroFish Says</div>
              <div class="prediction-number">
                {{ predictResult.prediction != null ? (predictResult.prediction * 100).toFixed(1) + '%' : '--' }}
              </div>
              <div class="prediction-sublabel">
                {{ predictResult.prediction != null ? 'Model prediction' : 'Run Deep mode for prediction' }}
              </div>
            </div>
          </div>

          <!-- Signal Badge -->
          <div class="signal-row" v-if="predictResult.signal">
            <span class="signal-badge-lg" :class="signalClass(predictResult.signal)">
              {{ predictResult.signal }}
            </span>
          </div>

          <!-- Details Section -->
          <div class="result-details">
            <div class="detail-grid">
              <div class="detail-item" v-if="predictResult.articlesFound != null">
                <span class="detail-label">Articles Found</span>
                <span class="detail-value">{{ predictResult.articlesFound }}</span>
              </div>
              <div class="detail-item" v-if="predictResult.confidence">
                <span class="detail-label">Confidence</span>
                <span class="detail-value">{{ typeof predictResult.confidence === 'number' ? (predictResult.confidence * 100).toFixed(0) + '%' : predictResult.confidence }}</span>
              </div>
              <div class="detail-item" v-if="predictResult.status">
                <span class="detail-label">Status</span>
                <span class="detail-value">{{ predictResult.status }}</span>
              </div>
            </div>

            <!-- Reasoning / Message -->
            <div v-if="predictResult.reasoning" class="reasoning-block">
              <div class="reasoning-label">Analysis</div>
              <p class="reasoning-text">{{ predictResult.reasoning }}</p>
            </div>

            <!-- Key Factors (deep mode) -->
            <div v-if="predictResult.keyFactors && predictResult.keyFactors.length" class="factors-block">
              <div class="factors-label">Key Factors</div>
              <ul class="factors-list">
                <li v-for="(factor, idx) in predictResult.keyFactors" :key="idx">{{ factor }}</li>
              </ul>
            </div>

            <!-- Report Summary (deep mode) -->
            <div v-if="predictResult.reportSummary" class="report-block">
              <div class="report-label">Report Summary</div>
              <p class="report-text">{{ predictResult.reportSummary }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- 4. Follow-up Actions -->
      <section v-if="predictResult" class="followup-section">
        <div class="followup-row">
          <button
            v-if="predictResult.mode === 'quick'"
            class="followup-btn followup-primary"
            @click="runDeepForCurrent"
            :disabled="isRunning"
          >
            &#128300; Run Deep Analysis
          </button>
          <button class="followup-btn" disabled>
            Compare with Similar Markets
          </button>
          <button class="followup-btn" disabled>
            View Seed Document
          </button>
          <button class="followup-btn" @click="clearAndFocus">
            Analyze Another Market
          </button>
        </div>
      </section>

      <!-- 5. History Section -->
      <section v-if="history.length > 0" class="history-section">
        <div class="section-header">
          <span class="status-dot">&#9632;</span>
          <span class="section-label">Session History</span>
          <span class="history-count">{{ history.length }}</span>
        </div>
        <div class="history-list">
          <div
            v-for="(item, idx) in history"
            :key="idx"
            class="history-row"
            @click="viewHistoryItem(item)"
          >
            <div class="history-question">{{ item.question }}</div>
            <span class="badge badge-mode" :class="item.mode === 'deep' ? 'badge-deep' : 'badge-quick'">
              {{ item.mode === 'deep' ? 'Deep' : 'Quick' }}
            </span>
            <span class="history-stat">
              {{ item.marketOdds != null ? (item.marketOdds * 100).toFixed(1) + '%' : '--' }}
            </span>
            <span class="history-arrow">&#8594;</span>
            <span class="history-stat" :class="{ 'edge-positive': item.edge > 0, 'edge-negative': item.edge < 0 }">
              {{ item.prediction != null ? (item.prediction * 100).toFixed(1) + '%' : '--' }}
            </span>
            <span v-if="item.signal" class="signal-badge signal-sm" :class="signalClass(item.signal)">
              {{ item.signal }}
            </span>
            <span class="history-time">{{ formatTime(item.timestamp) }}</span>
          </div>
        </div>
      </section>

      <!-- 6. Stats Bar -->
      <section class="stats-section">
        <div class="section-header clickable" @click="statsOpen = !statsOpen">
          <span class="status-dot">&#9632;</span>
          <span class="section-label">Platform Stats</span>
          <span class="collapse-icon">{{ statsOpen ? '&#9660;' : '&#9654;' }}</span>
        </div>
        <div v-if="statsOpen" class="stats-bar">
          <div class="stat-chip">
            <span class="stat-val">{{ stats.totalPredictions ?? '--' }}</span>
            <span class="stat-lbl">Predictions</span>
          </div>
          <div class="stat-chip">
            <span class="stat-val">{{ stats.marketsWithSignals ?? '--' }}</span>
            <span class="stat-lbl">Markets</span>
          </div>
          <div class="stat-chip">
            <span class="stat-val">{{ stats.averageEdge != null ? (stats.averageEdge * 100).toFixed(1) + '%' : '--' }}</span>
            <span class="stat-lbl">Avg Edge</span>
          </div>
          <div class="stat-chip">
            <span class="stat-val">{{ stats.accuracy != null ? (stats.accuracy * 100).toFixed(1) + '%' : '--' }}</span>
            <span class="stat-lbl">Accuracy</span>
          </div>
        </div>
      </section>

      <!-- 7. Calibration Section -->
      <section class="calibration-section">
        <div class="section-header clickable" @click="toggleCalibration">
          <span class="status-dot">&#9632;</span>
          <span class="section-label">Calibration</span>
          <span class="collapse-icon">{{ calibrationOpen ? '&#9660;' : '&#9654;' }}</span>
        </div>

        <div v-if="calibrationOpen" class="calibration-content">
          <div v-if="calibrationLoading" class="loading-state">
            <div class="spinner"></div>
            <span>Loading calibration data...</span>
          </div>

          <template v-else-if="calibration">
            <div class="calibration-metrics">
              <div class="stat-chip">
                <span class="stat-val">{{ calibration.brierScore != null ? calibration.brierScore.toFixed(4) : '--' }}</span>
                <span class="stat-lbl">Brier Score</span>
              </div>
              <div class="stat-chip">
                <span class="stat-val">{{ calibration.calibrationError != null ? calibration.calibrationError.toFixed(4) : '--' }}</span>
                <span class="stat-lbl">Calibration Error</span>
              </div>
            </div>

            <div class="table-wrapper" v-if="calibration.bins && calibration.bins.length > 0">
              <table class="cal-table">
                <thead>
                  <tr>
                    <th>Predicted Range</th>
                    <th>Actual Rate</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(bin, idx) in calibration.bins" :key="idx">
                    <td>{{ bin.range || bin.predictedRange || '--' }}</td>
                    <td>{{ bin.actualRate != null ? (bin.actualRate * 100).toFixed(1) + '%' : '--' }}</td>
                    <td>{{ bin.count ?? '--' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-else class="empty-state">No calibration bins available.</div>
          </template>

          <div v-else class="empty-state">No calibration data available.</div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'

// --- Refs ---
const slugInput = ref(null)

// --- Mode ---
const mode = ref('quick')

// --- Predict State ---
const predictSlug = ref('')
const predictLoading = ref(false)
const deepPolling = ref(false)
const predictResult = ref(null)
const predictError = ref('')
const currentStepIndex = ref(0)

const isRunning = computed(() => predictLoading.value || deepPolling.value)

// Quick steps
const quickSteps = [
  'Fetching market data...',
  'Searching news...',
  'Generating seed...',
  'Done'
]

// Deep steps
const deepSteps = [
  'Fetching market data...',
  'Building knowledge graph...',
  'Setting up simulation...',
  'Running agent simulation...',
  'Generating report...',
  'Extracting prediction...',
  'Done'
]

const currentSteps = computed(() => mode.value === 'deep' ? deepSteps : quickSteps)

// --- History ---
const history = ref([])

// --- Stats ---
const stats = ref({
  totalPredictions: null,
  marketsWithSignals: null,
  averageEdge: null,
  accuracy: null
})
const statsOpen = ref(false)

// --- Calibration ---
const calibrationOpen = ref(false)
const calibrationLoading = ref(false)
const calibration = ref(null)

// Log stream is now handled globally in App.vue

// --- Helpers ---
const signalClass = (signal) => {
  if (signal === 'BUY_YES') return 'signal-buy-yes'
  if (signal === 'BUY_NO') return 'signal-buy-no'
  return 'signal-skip'
}

const formatVolume = (vol) => {
  if (vol == null) return '0'
  const n = typeof vol === 'string' ? parseFloat(vol) : vol
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toFixed(0)
}

const formatTime = (ts) => {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const extractSlug = (input) => {
  const trimmed = input.trim()
  // If it looks like a URL, extract the slug
  try {
    const url = new URL(trimmed)
    const parts = url.pathname.split('/').filter(Boolean)
    // polymarket.com/event/slug or polymarket.com/market/slug
    if (parts.length >= 2) return parts[parts.length - 1]
    if (parts.length === 1) return parts[0]
  } catch {
    // Not a URL, treat as slug
  }
  return trimmed
}

// --- Progress simulation for quick mode ---
let stepTimer = null

const simulateQuickProgress = () => {
  currentStepIndex.value = 0
  clearInterval(stepTimer)
  let step = 0
  stepTimer = setInterval(() => {
    step++
    if (step < quickSteps.length - 1) {
      currentStepIndex.value = step
    } else {
      clearInterval(stepTimer)
      stepTimer = null
    }
  }, 1500)
}

const finishProgress = () => {
  clearInterval(stepTimer)
  stepTimer = null
  currentStepIndex.value = currentSteps.value.length - 1
}

// Map deep step strings from API to step index
const deepStepMap = {
  'fetching_market': 0,
  'building_graph': 1,
  'knowledge_graph': 1,
  'setting_up': 2,
  'setup': 2,
  'running_simulation': 3,
  'simulation': 3,
  'generating_report': 4,
  'report': 4,
  'extracting_prediction': 5,
  'extracting': 5,
  'completed': 6,
  'done': 6
}

// --- API: Quick Predict ---
const runQuickPredict = async () => {
  predictLoading.value = true
  predictResult.value = null
  predictError.value = ''
  // Log stream handled globally in App.vue
  simulateQuickProgress()

  try {
    const slug = extractSlug(predictSlug.value)
    const res = await fetch('/api/polymarket/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug })
    })

    if (res.ok) {
      const json = await res.json()
      const d = json.data || json
      const m = d.market || {}

      finishProgress()

      const result = {
        question: m.question || d.question || predictSlug.value,
        marketOdds: m.current_odds ?? d.market_prob ?? null,
        prediction: d.predicted_prob ?? null,
        edge: d.predicted_prob != null && m.current_odds != null
          ? d.predicted_prob - m.current_odds
          : null,
        signal: d.signal || null,
        reasoning: d.message || d.reasoning || null,
        category: m.category || null,
        volume: m.volume || null,
        articlesFound: d.articles_found || 0,
        status: d.status || null,
        confidence: d.confidence ?? null,
        keyFactors: null,
        reportSummary: null,
        mode: 'quick',
        slug: slug,
        timestamp: Date.now()
      }

      predictResult.value = result
      history.value.unshift(result)
    } else {
      finishProgress()
      const errData = await res.json().catch(() => null)
      predictError.value = errData?.message || errData?.error || `Request failed (${res.status})`
    }
  } catch {
    finishProgress()
    predictError.value = 'Network error: could not reach the prediction API.'
  } finally {

    predictLoading.value = false
  }
}

// --- API: Deep Predict ---
const runDeepPredict = async () => {
  predictLoading.value = true
  predictResult.value = null
  predictError.value = ''
  // Log stream handled globally in App.vue
  currentStepIndex.value = 0

  try {
    const slug = extractSlug(predictSlug.value)
    const res = await fetch('/api/polymarket/predict/deep', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug })
    })

    if (!res.ok) {
      const errData = await res.json().catch(() => null)
      predictError.value = errData?.message || errData?.error || `Request failed (${res.status})`
      predictLoading.value = false
      return
    }

    const initData = await res.json()
    const taskId = initData.task_id

    if (!taskId) {
      // Maybe the API returned the result directly
      handleDeepResult(initData, slug)
      predictLoading.value = false
      return
    }

    // Start polling
    predictLoading.value = false
    deepPolling.value = true
    pollDeepTask(taskId, slug)
  } catch {
    predictError.value = 'Network error: could not reach the prediction API.'

    predictLoading.value = false
  }
}

const pollDeepTask = async (taskId, slug) => {
  const poll = async () => {
    try {
      const res = await fetch(`/api/polymarket/predict/deep/${taskId}`)
      if (!res.ok) {
        predictError.value = `Polling failed (${res.status})`
    
        deepPolling.value = false
        return
      }

      const data = await res.json()

      // Update step
      if (data.step && deepStepMap[data.step] !== undefined) {
        currentStepIndex.value = deepStepMap[data.step]
      }

      if (data.status === 'completed' || data.status === 'done') {
        handleDeepResult(data, slug)
        deepPolling.value = false
        return
      }

      if (data.status === 'failed' || data.status === 'error') {
        predictError.value = data.message || data.error || 'Deep analysis failed.'
    
        deepPolling.value = false
        return
      }

      // Continue polling
      setTimeout(poll, 3000)
    } catch {
      predictError.value = 'Lost connection while polling deep analysis.'
  
      deepPolling.value = false
    }
  }

  setTimeout(poll, 3000)
}

const handleDeepResult = (data, slug) => {
  const d = data.result || data.data || data
  const m = d.market || {}
  const p = d.prediction || {}

  currentStepIndex.value = deepSteps.length - 1

  const result = {
    question: m.question || d.question || predictSlug.value,
    marketOdds: m.current_odds ?? d.market_prob ?? null,
    prediction: p.probability ?? d.predicted_prob ?? null,
    edge: p.edge ?? (p.probability != null && m.current_odds != null
      ? p.probability - m.current_odds
      : null),
    signal: p.signal || d.signal || null,
    reasoning: d.message || d.reasoning || null,
    category: m.category || null,
    volume: m.volume || null,
    articlesFound: d.articles_found || p.variants_run || 0,
    status: d.status || 'completed',
    confidence: (p.variant_details && p.variant_details[0] && p.variant_details[0].confidence) || d.confidence || null,
    keyFactors: (p.variant_details && p.variant_details[0] && p.variant_details[0].key_factors) || d.key_factors || null,
    reportSummary: d.report_summary || d.reportSummary || null,
    mode: 'deep',
    slug: slug,
    timestamp: Date.now()
  }

  predictResult.value = result
  history.value.unshift(result)
}

// --- Run Analysis (routes to quick or deep) ---
const runAnalysis = () => {
  if (!predictSlug.value.trim() || isRunning.value) return
  if (mode.value === 'deep') {
    runDeepPredict()
  } else {
    runQuickPredict()
  }
}

// --- Follow-up actions ---
const runDeepForCurrent = () => {
  if (!predictResult.value) return
  mode.value = 'deep'
  predictSlug.value = predictResult.value.slug || predictResult.value.question
  runDeepPredict()
}

const clearAndFocus = () => {
  predictSlug.value = ''
  predictResult.value = null
  predictError.value = ''
  currentStepIndex.value = 0
  nextTick(() => {
    slugInput.value?.focus()
  })
}

const viewHistoryItem = (item) => {
  predictResult.value = item
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// --- Calibration ---
const toggleCalibration = () => {
  calibrationOpen.value = !calibrationOpen.value
  if (calibrationOpen.value && !calibration.value && !calibrationLoading.value) {
    fetchCalibration()
  }
}

// --- API Calls ---
const fetchStats = async () => {
  try {
    const res = await fetch('/api/polymarket/stats')
    if (res.ok) {
      const data = await res.json()
      stats.value = {
        totalPredictions: data.totalPredictions ?? data.total_predictions ?? null,
        marketsWithSignals: data.marketsWithSignals ?? data.markets_with_signals ?? null,
        averageEdge: data.averageEdge ?? data.average_edge ?? null,
        accuracy: data.accuracy ?? null
      }
    }
  } catch {
    // stats remain defaults
  }
}

const fetchCalibration = async () => {
  calibrationLoading.value = true
  try {
    const res = await fetch('/api/polymarket/calibration')
    if (res.ok) {
      calibration.value = await res.json()
    }
  } catch {
    // calibration remains null
  } finally {
    calibrationLoading.value = false
  }
}

onMounted(() => {
  fetchStats()
})
</script>

<style scoped>
/* ========================================
   MiroFish Design System
   ======================================== */

:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  --green: #2E7D32;
  --green-bg: #E8F5E9;
  --red: #C62828;
  --red-bg: #FFEBEE;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

* {
  box-sizing: border-box;
}

.polymarket-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

/* ========================================
   Main Content
   ======================================== */

.main-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 48px 24px 80px;
}

/* ========================================
   1. Header
   ======================================== */

.header-section {
  margin-bottom: 40px;
}

.tag-row {
  margin-bottom: 16px;
}

.orange-tag {
  display: inline-block;
  background: var(--orange);
  color: var(--white);
  padding: 4px 12px;
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.7rem;
  text-transform: uppercase;
}

.main-title {
  font-size: 2.8rem;
  font-weight: 500;
  margin: 0 0 8px 0;
  letter-spacing: -1px;
  line-height: 1.1;
}

.subtitle {
  color: var(--gray-text);
  font-size: 1.05rem;
  margin: 0;
}

/* ========================================
   2. Predict Section
   ======================================== */

.predict-section {
  margin-bottom: 48px;
}

.predict-input-wrapper {
  margin-bottom: 16px;
}

.predict-input {
  width: 100%;
  border: 2px solid var(--black);
  background: var(--white);
  padding: 18px 24px;
  font-family: var(--font-mono);
  font-size: 1rem;
  outline: none;
  transition: border-color 0.2s;
}

.predict-input:focus {
  border-color: var(--orange);
}

.predict-input:disabled {
  opacity: 0.5;
  background: var(--gray-light);
}

.predict-input::placeholder {
  color: #aaa;
}

.mode-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 10px;
}

.mode-toggle {
  display: flex;
  border: 1px solid var(--border);
  overflow: hidden;
}

.mode-btn {
  padding: 10px 20px;
  background: var(--white);
  border: none;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--gray-text);
  white-space: nowrap;
}

.mode-btn:first-child {
  border-right: 1px solid var(--border);
}

.mode-btn.active {
  background: var(--orange);
  color: var(--white);
}

.mode-btn:hover:not(.active):not(:disabled) {
  background: var(--gray-light);
  color: var(--black);
}

.mode-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.analyze-btn {
  flex: 1;
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 10px 32px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1rem;
  cursor: pointer;
  letter-spacing: 0.5px;
  transition: all 0.2s;
  white-space: nowrap;
  min-width: 160px;
}

.analyze-btn:hover:not(:disabled) {
  background: var(--orange);
}

.analyze-btn:disabled {
  background: var(--border);
  color: #999;
  cursor: not-allowed;
}

.btn-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.mode-description {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
  margin-bottom: 16px;
}

/* ========================================
   Progress Tracker
   ======================================== */

.progress-tracker {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 20px 0;
  border: 1px solid var(--border);
  padding: 24px;
  margin-top: 16px;
  background: var(--gray-light);
}

.progress-step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: #bbb;
  transition: color 0.3s;
}

.progress-step.completed {
  color: var(--green);
}

.progress-step.active {
  color: var(--black);
  font-weight: 600;
}

.step-indicator {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-check {
  color: var(--green);
  font-size: 0.9rem;
  font-weight: 700;
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border);
}

.step-dot-pulse {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--orange);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

/* ========================================
   Error
   ======================================== */

.error-msg {
  margin-top: 16px;
  padding: 14px 20px;
  background: var(--red-bg);
  color: var(--red);
  font-family: var(--font-mono);
  font-size: 0.85rem;
  border: 1px solid #FFCDD2;
  display: flex;
  align-items: center;
  gap: 10px;
}

.error-icon {
  font-weight: 700;
}

/* ========================================
   3. Result Card
   ======================================== */

.result-section {
  margin-bottom: 32px;
}

.result-card {
  border: 2px solid var(--black);
  background: var(--white);
}

.result-market-bar {
  padding: 28px 32px 20px;
  border-bottom: 1px solid var(--border);
}

.result-question {
  font-size: 1.4rem;
  font-weight: 600;
  margin: 0 0 12px 0;
  line-height: 1.3;
}

.result-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.badge {
  display: inline-block;
  padding: 3px 10px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.badge-category {
  background: var(--gray-light);
  color: var(--gray-text);
  border: 1px solid var(--border);
}

.badge-volume {
  background: var(--gray-light);
  color: var(--black);
  border: 1px solid var(--border);
}

.badge-mode {
  border: 1px solid var(--border);
  background: var(--gray-light);
  color: var(--gray-text);
}

.badge-quick {
  background: #FFF3E0;
  color: #E65100;
  border-color: #FFE0B2;
}

.badge-deep {
  background: #E3F2FD;
  color: #1565C0;
  border-color: #BBDEFB;
}

/* Prediction Comparison */

.prediction-comparison {
  display: flex;
  align-items: center;
  padding: 32px;
  border-bottom: 1px solid var(--border);
}

.prediction-col {
  flex: 1;
  text-align: center;
}

.prediction-source {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 8px;
}

.prediction-number {
  font-family: var(--font-mono);
  font-size: 2.8rem;
  font-weight: 700;
  line-height: 1;
  margin-bottom: 6px;
}

.prediction-sublabel {
  font-size: 0.8rem;
  color: #bbb;
}

.prediction-edge-col {
  flex: 0 0 140px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.edge-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 12px 16px;
  border-radius: 4px;
}

.edge-indicator.edge-up {
  background: var(--green-bg);
  color: var(--green);
}

.edge-indicator.edge-down {
  background: var(--red-bg);
  color: var(--red);
}

.edge-indicator.edge-neutral {
  background: var(--gray-light);
  color: var(--gray-text);
}

.edge-arrow {
  font-size: 1rem;
}

.edge-value {
  font-family: var(--font-mono);
  font-size: 1.1rem;
  font-weight: 700;
}

.edge-word {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  opacity: 0.7;
}

/* Signal Row */

.signal-row {
  padding: 20px 32px;
  border-bottom: 1px solid var(--border);
  text-align: center;
}

.signal-badge-lg {
  display: inline-block;
  padding: 8px 24px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 1px;
}

/* Result Details */

.result-details {
  padding: 24px 32px 28px;
}

.detail-grid {
  display: flex;
  gap: 32px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-value {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 600;
}

.reasoning-block,
.factors-block,
.report-block {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

.reasoning-label,
.factors-label,
.report-label {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.reasoning-text,
.report-text {
  font-size: 0.95rem;
  line-height: 1.7;
  color: var(--gray-text);
  margin: 0;
}

.factors-list {
  margin: 0;
  padding-left: 20px;
  font-size: 0.9rem;
  line-height: 1.8;
  color: var(--gray-text);
}

.factors-list li {
  margin-bottom: 4px;
}

/* ========================================
   Signal Badges (shared)
   ======================================== */

.signal-badge,
.signal-badge-lg {
  border-radius: 2px;
}

.signal-buy-yes {
  background: var(--green-bg);
  color: var(--green);
}

.signal-buy-no {
  background: var(--red-bg);
  color: var(--red);
}

.signal-skip {
  background: var(--gray-light);
  color: #999;
}

.signal-badge.signal-sm {
  padding: 2px 8px;
  font-family: var(--font-mono);
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.5px;
}

/* ========================================
   4. Follow-up Actions
   ======================================== */

.followup-section {
  margin-bottom: 48px;
}

.followup-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.followup-btn {
  padding: 10px 20px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 600;
  background: var(--white);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all 0.15s;
  color: var(--black);
}

.followup-btn:hover:not(:disabled) {
  border-color: var(--black);
}

.followup-btn:disabled {
  color: #ccc;
  cursor: not-allowed;
}

.followup-btn.followup-primary {
  background: var(--black);
  color: var(--white);
  border-color: var(--black);
}

.followup-btn.followup-primary:hover:not(:disabled) {
  background: var(--orange);
  border-color: var(--orange);
}

/* ========================================
   5. History
   ======================================== */

.history-section {
  margin-bottom: 48px;
  border-top: 1px solid var(--border);
  padding-top: 32px;
}

.history-count {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  background: var(--gray-light);
  padding: 2px 8px;
  color: var(--gray-text);
}

.history-list {
  border: 1px solid var(--border);
}

.history-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #F0F0F0;
  cursor: pointer;
  transition: background 0.1s;
  font-size: 0.85rem;
}

.history-row:last-child {
  border-bottom: none;
}

.history-row:hover {
  background: var(--gray-light);
}

.history-question {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.history-stat {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
  white-space: nowrap;
}

.history-arrow {
  color: #ccc;
  font-size: 0.85rem;
}

.history-time {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #bbb;
  white-space: nowrap;
}

.edge-positive {
  color: var(--green);
}

.edge-negative {
  color: var(--red);
}

/* ========================================
   6. Stats Section
   ======================================== */

.stats-section {
  margin-bottom: 32px;
  border-top: 1px solid var(--border);
  padding-top: 32px;
}

.stats-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.stat-chip {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 24px;
  border: 1px solid var(--border);
  flex: 1;
  min-width: 120px;
}

.stat-val {
  font-family: var(--font-mono);
  font-size: 1.4rem;
  font-weight: 600;
}

.stat-lbl {
  font-size: 0.75rem;
  color: #999;
}

/* ========================================
   7. Calibration
   ======================================== */

.calibration-section {
  border-top: 1px solid var(--border);
  padding-top: 32px;
}

.calibration-content {
  margin-top: 12px;
}

.calibration-metrics {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.cal-table {
  width: 100%;
  max-width: 500px;
  border-collapse: collapse;
  font-size: 0.85rem;
  border: 1px solid var(--border);
}

.cal-table thead {
  background: var(--gray-light);
}

.cal-table th {
  text-align: left;
  padding: 10px 14px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 600;
  color: #999;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border);
}

.cal-table td {
  padding: 10px 14px;
  border-bottom: 1px solid #F0F0F0;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.cal-table tbody tr:hover {
  background: var(--gray-light);
}

/* ========================================
   Section Headers (shared)
   ======================================== */

.section-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.section-header.clickable {
  cursor: pointer;
  user-select: none;
}

.section-header.clickable:hover {
  color: var(--black);
}

.status-dot {
  color: var(--orange);
  font-size: 0.7rem;
}

.section-label {
  font-weight: 600;
  letter-spacing: 0.5px;
}

.collapse-icon {
  margin-left: auto;
  font-size: 0.65rem;
}

/* ========================================
   Loading / Empty States
   ======================================== */

.loading-state {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px;
  color: var(--gray-text);
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.empty-state {
  padding: 24px;
  color: #999;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  border: 1px dashed var(--border);
  text-align: center;
}

/* ========================================
   Spinner
   ======================================== */

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--orange);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.spinner-sm {
  width: 14px;
  height: 14px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ========================================
   Table wrapper
   ======================================== */

.table-wrapper {
  overflow-x: auto;
}

/* ========================================
   Responsive
   ======================================== */

@media (max-width: 768px) {
  .main-content {
    padding: 32px 16px 60px;
  }

  .main-title {
    font-size: 2rem;
  }

  .mode-row {
    flex-direction: column;
  }

  .analyze-btn {
    width: 100%;
  }

  .prediction-comparison {
    flex-direction: column;
    gap: 24px;
    padding: 24px;
  }

  .prediction-edge-col {
    flex: unset;
  }

  .prediction-number {
    font-size: 2.2rem;
  }

  .result-market-bar,
  .result-details,
  .signal-row {
    padding-left: 20px;
    padding-right: 20px;
  }

  .followup-row {
    flex-direction: column;
  }

  .followup-btn {
    width: 100%;
    text-align: center;
  }

  .history-row {
    flex-wrap: wrap;
  }

  .stats-bar {
    flex-direction: column;
  }

  .detail-grid {
    flex-direction: column;
    gap: 16px;
  }

  .calibration-metrics {
    flex-direction: column;
  }
}
</style>
