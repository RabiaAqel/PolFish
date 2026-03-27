<template>
  <div class="prediction-detail">
    <!-- Loading -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>Loading prediction...</span>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <router-link to="/predict" class="btn btn-primary">Back to Predict</router-link>
    </div>

    <!-- Content -->
    <template v-else-if="bet">
      <!-- Header -->
      <header class="detail-header">
        <router-link to="/predict" class="back-link">&larr; Back</router-link>
        <h1 class="detail-title">{{ bet.question || bet.slug || id }}</h1>
        <div class="detail-badges">
          <span v-if="bet.mode" class="badge" :class="bet.mode === 'deep' ? 'badge-deep' : 'badge-quick'">{{ bet.mode }}</span>
          <span v-if="bet.side" class="badge" :class="bet.side === 'YES' ? 'badge-yes' : 'badge-no'">{{ bet.side }}</span>
          <span class="badge badge-status" :class="bet.resolved ? 'badge-resolved' : 'badge-open'">{{ bet.resolved ? 'Resolved' : 'Open' }}</span>
          <a v-if="bet.slug" :href="'https://polymarket.com/event/' + bet.slug" target="_blank" rel="noopener" class="polymarket-link">View on Polymarket &nearr;</a>
        </div>
      </header>

      <!-- Tabs -->
      <nav class="detail-tabs">
        <button v-for="tab in tabs" :key="tab.id" class="tab-btn" :class="{ active: activeTab === tab.id }" @click="activeTab = tab.id">{{ tab.label }}</button>
      </nav>

      <!-- Overview Tab -->
      <section v-if="activeTab === 'overview'" class="tab-content">
        <!-- Prediction Comparison -->
        <div class="prediction-comparison">
          <div class="prediction-col">
            <div class="prediction-source">Market Says</div>
            <div class="prediction-number">{{ bet.odds != null ? ((bet.odds) * 100).toFixed(1) + '%' : '--' }}</div>
            <div class="prediction-sublabel">Polymarket odds</div>
          </div>

          <div class="prediction-edge-col">
            <div class="edge-indicator" :class="(bet.edge || 0) > 0 ? 'edge-up' : (bet.edge || 0) < 0 ? 'edge-down' : 'edge-neutral'">
              <span class="edge-arrow">{{ (bet.edge || 0) > 0 ? '&#9650;' : (bet.edge || 0) < 0 ? '&#9660;' : '&#9644;' }}</span>
              <span class="edge-value">{{ bet.edge ? ((bet.edge > 0 ? '+' : '') + (bet.edge * 100).toFixed(1) + '%') : '--' }}</span>
              <span class="edge-word">edge</span>
            </div>
          </div>

          <div class="prediction-col">
            <div class="prediction-source">PolFish Says</div>
            <div class="prediction-number">{{ bet.prediction != null ? ((bet.prediction) * 100).toFixed(1) + '%' : '--' }}</div>
            <div class="prediction-sublabel">Model prediction</div>
          </div>
        </div>

        <!-- Signal -->
        <div class="signal-row" v-if="bet.side">
          <span class="signal-badge-lg" :class="bet.side === 'YES' ? 'signal-buy-yes' : 'signal-buy-no'">
            BUY_{{ bet.side }}
          </span>
        </div>

        <!-- Bet Details -->
        <div class="detail-grid">
          <div class="detail-item" v-if="bet.amount != null">
            <span class="detail-label">Amount</span>
            <span class="detail-value">${{ bet.amount.toFixed(2) }}</span>
          </div>
          <div class="detail-item" v-if="bet.confidence">
            <span class="detail-label">Confidence</span>
            <span class="detail-value">{{ bet.confidence }}</span>
          </div>
          <div class="detail-item" v-if="bet.mode">
            <span class="detail-label">Mode</span>
            <span class="detail-value">{{ bet.mode }}</span>
          </div>
          <div class="detail-item" v-if="bet.pnl != null && bet.resolved">
            <span class="detail-label">P&amp;L</span>
            <span class="detail-value" :class="bet.pnl >= 0 ? 'pnl-pos' : 'pnl-neg'">{{ bet.pnl >= 0 ? '+' : '' }}${{ bet.pnl.toFixed(2) }}</span>
          </div>
          <div class="detail-item" v-if="bet.placed_at">
            <span class="detail-label">Placed</span>
            <span class="detail-value">{{ formatDate(bet.placed_at) }}</span>
          </div>
          <div class="detail-item" v-if="bet.closes_at">
            <span class="detail-label">Closes</span>
            <span class="detail-value">{{ formatDate(bet.closes_at) }}</span>
          </div>
        </div>

        <!-- Key Factors -->
        <div v-if="bet.key_factors && bet.key_factors.length" class="factors-block">
          <div class="factors-label">Key Factors</div>
          <ul class="factors-list">
            <li v-for="(f, i) in bet.key_factors" :key="i">{{ f }}</li>
          </ul>
        </div>
      </section>

      <!-- Simulation Tab -->
      <section v-if="activeTab === 'simulation'" class="tab-content">
        <div v-if="simulation" class="simulation-content">
          <div class="sim-stats">
            <div class="sim-stat" v-if="simulation.agent_count">
              <span class="sim-stat-value">{{ simulation.agent_count }}</span>
              <span class="sim-stat-label">Agents</span>
            </div>
            <div class="sim-stat" v-if="simulation.rounds">
              <span class="sim-stat-value">{{ simulation.rounds }}</span>
              <span class="sim-stat-label">Rounds</span>
            </div>
            <div class="sim-stat" v-if="simulation.total_interactions">
              <span class="sim-stat-value">{{ simulation.total_interactions }}</span>
              <span class="sim-stat-label">Interactions</span>
            </div>
          </div>
          <p class="placeholder-note">Full simulation timeline and agent interaction details will be available here when simulation data is linked. Graph visualization coming soon.</p>
        </div>
        <div v-else class="empty-state">
          <p>No simulation data available for this prediction.</p>
          <p class="placeholder-note">Run a Deep analysis to generate simulation data.</p>
        </div>
      </section>

      <!-- Report Tab -->
      <section v-if="activeTab === 'report'" class="tab-content">
        <div v-if="bet.report_summary" class="report-content" v-html="bet.report_summary"></div>
        <div v-else class="empty-state">
          <p>No report available for this prediction.</p>
          <p class="placeholder-note">Run a Deep analysis to generate a full report.</p>
        </div>
      </section>

      <!-- Verdict Tab -->
      <section v-if="activeTab === 'verdict'" class="tab-content">
        <div class="empty-state">
          <p>Superforecaster analysis will appear here once the 6-step verdict system is integrated.</p>
          <p class="placeholder-note">This tab will show: base rate anchor, factors for/against, final probability with reasoning, and method comparison (LLM vs Quantitative vs Combined).</p>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  id: { type: String, required: true }
})

const tabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'simulation', label: 'Simulation' },
  { id: 'report', label: 'Report' },
  { id: 'verdict', label: 'Verdict' },
]

const activeTab = ref('overview')
const loading = ref(true)
const error = ref('')
const bet = ref(null)
const simulation = ref(null)

const formatDate = (ts) => {
  if (!ts) return '--'
  try {
    return new Date(ts).toLocaleString()
  } catch { return ts }
}

const fetchPrediction = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/polymarket/prediction/${encodeURIComponent(props.id)}`)
    if (res.ok) {
      const json = await res.json()
      if (json.success && json.data) {
        bet.value = json.data.bet || json.data
        simulation.value = json.data.simulation || null
      } else {
        error.value = json.error || 'Prediction not found.'
      }
    } else {
      error.value = `Failed to load prediction (${res.status}).`
    }
  } catch {
    error.value = 'Network error: could not reach the API.'
  } finally {
    loading.value = false
  }
}

onMounted(fetchPrediction)
</script>

<style scoped>
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

.prediction-detail {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px 80px;
  font-family: var(--font-sans);
  color: var(--black);
}

/* Header */
.detail-header {
  margin-bottom: 32px;
}

.back-link {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--gray-text);
  text-decoration: none;
  margin-bottom: 12px;
  transition: color 0.15s;
}

.back-link:hover {
  color: var(--orange);
}

.detail-title {
  font-size: 1.8rem;
  font-weight: 600;
  margin: 0 0 12px;
  line-height: 1.3;
}

.detail-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
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

.badge-quick { background: #FFF3E0; color: #E65100; border: 1px solid #FFE0B2; }
.badge-deep { background: #E3F2FD; color: #1565C0; border: 1px solid #BBDEFB; }
.badge-yes { background: var(--green-bg); color: var(--green); border: 1px solid #C8E6C9; }
.badge-no { background: var(--red-bg); color: var(--red); border: 1px solid #FFCDD2; }
.badge-open { background: #FFF3E0; color: #E65100; border: 1px solid #FFE0B2; }
.badge-resolved { background: var(--gray-light); color: #999; border: 1px solid var(--border); }

.polymarket-link {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--orange);
  text-decoration: none;
  margin-left: auto;
}

.polymarket-link:hover {
  text-decoration: underline;
}

/* Tabs */
.detail-tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--black);
  margin-bottom: 32px;
}

.tab-btn {
  padding: 12px 24px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--gray-text);
  transition: all 0.15s;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}

.tab-btn:hover {
  color: var(--black);
}

.tab-btn.active {
  color: var(--orange);
  border-bottom-color: var(--orange);
}

/* Prediction Comparison */
.prediction-comparison {
  display: flex;
  align-items: center;
  padding: 32px;
  border: 1px solid var(--border);
  margin-bottom: 24px;
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

.edge-indicator.edge-up { background: var(--green-bg); color: var(--green); }
.edge-indicator.edge-down { background: var(--red-bg); color: var(--red); }
.edge-indicator.edge-neutral { background: var(--gray-light); color: var(--gray-text); }

.edge-arrow { font-size: 1rem; }
.edge-value { font-family: var(--font-mono); font-size: 1.1rem; font-weight: 700; }
.edge-word { font-family: var(--font-mono); font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1px; opacity: 0.7; }

/* Signal */
.signal-row {
  text-align: center;
  margin-bottom: 24px;
}

.signal-badge-lg {
  display: inline-block;
  padding: 8px 24px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 1px;
  border-radius: 2px;
}

.signal-buy-yes { background: var(--green-bg); color: var(--green); }
.signal-buy-no { background: var(--red-bg); color: var(--red); }

/* Detail Grid */
.detail-grid {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
  padding: 24px;
  border: 1px solid var(--border);
  margin-bottom: 24px;
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

.pnl-pos { color: var(--green); }
.pnl-neg { color: var(--red); }

/* Factors */
.factors-block {
  padding: 24px;
  border: 1px solid var(--border);
}

.factors-label {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.factors-list {
  margin: 0;
  padding-left: 20px;
  font-size: 0.9rem;
  line-height: 1.8;
  color: var(--gray-text);
}

/* Simulation */
.sim-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
}

.sim-stat {
  border: 1px solid var(--border);
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.sim-stat-value {
  font-family: var(--font-mono);
  font-size: 1.4rem;
  font-weight: 700;
}

.sim-stat-label {
  font-size: 0.7rem;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* Report */
.report-content {
  font-size: 0.95rem;
  line-height: 1.7;
  color: var(--gray-text);
}

.report-content h1, .report-content h2, .report-content h3 {
  color: var(--black);
  margin-top: 24px;
  margin-bottom: 12px;
}

/* States */
.loading-state {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 48px;
  justify-content: center;
  color: var(--gray-text);
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.error-state {
  text-align: center;
  padding: 48px;
  color: var(--red);
  font-family: var(--font-mono);
}

.empty-state {
  padding: 32px;
  color: #999;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  border: 1px dashed var(--border);
  text-align: center;
}

.placeholder-note {
  color: #bbb;
  font-size: 0.8rem;
  margin-top: 12px;
}

.btn {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 600;
  padding: 10px 20px;
  border: none;
  cursor: pointer;
  text-decoration: none;
  display: inline-block;
}

.btn-primary {
  background: var(--black);
  color: var(--white);
}

.btn-primary:hover {
  background: var(--orange);
}

.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--orange);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .prediction-comparison {
    flex-direction: column;
    gap: 24px;
  }

  .prediction-edge-col {
    flex: unset;
  }

  .prediction-number {
    font-size: 2.2rem;
  }

  .detail-grid {
    flex-direction: column;
    gap: 16px;
  }

  .sim-stats {
    flex-direction: column;
  }
}
</style>
