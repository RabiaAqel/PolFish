<template>
  <div class="knowledge-base">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1>Knowledge Base</h1>
        <span class="subtitle">Market intelligence accumulated across predictions</span>
      </div>
    </header>

    <!-- Stats Bar -->
    <section class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ stats.total_entries || 0 }}</span>
        <span class="stat-label">Total Entries</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ Object.keys(stats.categories || {}).length }}</span>
        <span class="stat-label">Categories</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ (stats.outcomes?.correct || 0) + (stats.outcomes?.incorrect || 0) }}</span>
        <span class="stat-label">Resolved</span>
      </div>
      <div class="stat-card">
        <span class="stat-value accent">{{ overallAccuracy }}</span>
        <span class="stat-label">Accuracy</span>
      </div>
    </section>

    <!-- Category Accuracy Cards -->
    <section class="section">
      <h2 class="section-title">Accuracy by Category</h2>
      <div v-if="loading" class="loading">Loading knowledge base...</div>
      <div v-else-if="Object.keys(accuracyData).length === 0" class="empty">
        No category data yet. Run predictions to build the knowledge base.
      </div>
      <div v-else class="accuracy-grid">
        <div
          v-for="(data, cat) in accuracyData"
          :key="cat"
          class="accuracy-card"
          :class="{ 'filter-active': filterCategory === cat }"
          @click="toggleCategoryFilter(cat)"
        >
          <div class="accuracy-card-header">
            <span class="category-name">{{ cat }}</span>
            <span class="category-count">{{ data.total + data.pending }} predictions</span>
          </div>
          <div class="accuracy-bar-wrapper">
            <div class="accuracy-bar">
              <div
                class="accuracy-fill correct"
                :style="{ width: data.total > 0 ? (data.correct / data.total * 100) + '%' : '0%' }"
              ></div>
              <div
                class="accuracy-fill incorrect"
                :style="{ width: data.total > 0 ? ((data.total - data.correct) / data.total * 100) + '%' : '0%' }"
              ></div>
            </div>
          </div>
          <div class="accuracy-card-footer">
            <span
              class="accuracy-pct"
              :class="accuracyColor(data.accuracy)"
            >
              {{ data.total > 0 ? (data.accuracy * 100).toFixed(1) + '%' : '--' }}
            </span>
            <span class="pending-count" v-if="data.pending > 0">{{ data.pending }} pending</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Market Intelligence Table -->
    <section class="section">
      <h2 class="section-title">Market Intelligence</h2>

      <!-- Filter Bar -->
      <div class="filter-bar">
        <div class="filter-chips">
          <button
            class="chip"
            :class="{ active: filterCategory === '' }"
            @click="filterCategory = ''"
          >All</button>
          <button
            v-for="cat in allCategories"
            :key="cat"
            class="chip"
            :class="{ active: filterCategory === cat }"
            @click="filterCategory = cat"
          >{{ cat }}</button>
        </div>
        <div class="filter-right">
          <select v-model="filterOutcome" class="filter-select">
            <option value="">All Outcomes</option>
            <option value="correct">Correct</option>
            <option value="incorrect">Incorrect</option>
            <option value="pending">Pending</option>
          </select>
          <select v-model="sortField" class="filter-select">
            <option value="timestamp">Sort: Newest</option>
            <option value="edge">Sort: Edge</option>
            <option value="our_prediction">Sort: Prediction</option>
          </select>
        </div>
      </div>

      <div v-if="loading" class="loading">Loading entries...</div>
      <div v-else-if="filteredEntries.length === 0" class="empty">
        No entries match your filters.
      </div>
      <div v-else class="table-wrapper">
        <table class="intel-table">
          <thead>
            <tr>
              <th class="col-question">Question</th>
              <th>Category</th>
              <th>Our Pred.</th>
              <th>Market</th>
              <th>Edge</th>
              <th>Consensus</th>
              <th>Outcome</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(entry, i) in filteredEntries" :key="i">
              <td class="col-question">
                <a
                  v-if="entry.market_id"
                  :href="'https://polymarket.com/event/' + entry.market_id"
                  target="_blank"
                  rel="noopener"
                  class="question-link"
                >{{ truncate(entry.question, 60) }}</a>
                <span v-else>{{ truncate(entry.question, 60) }}</span>
              </td>
              <td>
                <span class="category-chip" @click="filterCategory = entry.category">
                  {{ entry.category || 'other' }}
                </span>
              </td>
              <td class="mono">{{ pct(entry.our_prediction) }}</td>
              <td class="mono">{{ pct(entry.market_odds_at_prediction) }}</td>
              <td class="mono" :class="edgeColor(entry)">{{ edgeStr(entry) }}</td>
              <td>
                <span class="consensus-badge" :class="'consensus-' + (entry.agent_consensus || 'unknown')">
                  {{ entry.agent_consensus || '--' }}
                </span>
              </td>
              <td>
                <span class="outcome-badge" :class="outcomeClass(entry)">
                  {{ outcomeLabel(entry) }}
                </span>
              </td>
              <td class="mono ts-col">{{ formatTs(entry.timestamp) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Related Markets Search -->
    <section class="section">
      <h2 class="section-title">Related Markets Search</h2>
      <div class="search-bar">
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="Search for related markets (e.g. 'Trump tariff' or 'Bitcoin ETF')..."
          @keydown.enter="doSearch"
        />
        <button class="btn btn-primary" @click="doSearch" :disabled="!searchQuery.trim() || searching">
          {{ searching ? 'Searching...' : 'Search' }}
        </button>
      </div>
      <div v-if="searchResults.length > 0" class="search-results">
        <div v-for="(r, i) in searchResults" :key="i" class="search-result-card">
          <div class="search-result-header">
            <span class="search-result-question">{{ r.question }}</span>
            <span class="category-chip">{{ r.category || 'other' }}</span>
          </div>
          <div class="search-result-meta">
            <span>Our: <strong class="mono">{{ pct(r.our_prediction) }}</strong></span>
            <span>Market: <strong class="mono">{{ pct(r.market_odds_at_prediction) }}</strong></span>
            <span v-if="r.agent_consensus">
              Consensus:
              <strong class="consensus-badge" :class="'consensus-' + r.agent_consensus">{{ r.agent_consensus }}</strong>
            </span>
            <span class="outcome-badge" :class="outcomeClass(r)">{{ outcomeLabel(r) }}</span>
          </div>
          <div v-if="r.key_factors && r.key_factors.length" class="search-result-factors">
            <span v-for="(f, fi) in r.key_factors.slice(0, 3)" :key="fi" class="factor-tag">{{ f }}</span>
          </div>
        </div>
      </div>
      <div v-else-if="searchDone && searchResults.length === 0" class="empty small">
        No related markets found for "{{ lastSearchQuery }}".
      </div>
    </section>

    <!-- Knowledge Graph Placeholder -->
    <section class="section">
      <h2 class="section-title">Knowledge Graph</h2>
      <div class="graph-placeholder">
        <div class="graph-nodes">
          <div class="gnode n1"></div>
          <div class="gnode n2"></div>
          <div class="gnode n3"></div>
          <div class="gnode n4"></div>
          <div class="gnode n5"></div>
          <div class="gnode n6"></div>
          <svg class="graph-edges" viewBox="0 0 400 200">
            <line x1="80" y1="60" x2="200" y2="100" />
            <line x1="200" y1="100" x2="320" y2="50" />
            <line x1="200" y1="100" x2="150" y2="160" />
            <line x1="320" y1="50" x2="350" y2="150" />
            <line x1="80" y1="60" x2="60" y2="150" />
            <line x1="150" y1="160" x2="350" y2="150" />
          </svg>
        </div>
        <p class="graph-label">
          Graph visualization coming soon &mdash; will show entity relationships, agent interactions,
          and prediction clusters when Chroma vector DB is integrated.
        </p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const loading = ref(true)
const stats = ref({})
const accuracyData = ref({})
const entries = ref([])
const filterCategory = ref('')
const filterOutcome = ref('')
const sortField = ref('timestamp')
const searchQuery = ref('')
const lastSearchQuery = ref('')
const searchResults = ref([])
const searching = ref(false)
const searchDone = ref(false)

const allCategories = computed(() => {
  const cats = new Set()
  entries.value.forEach(e => { if (e.category) cats.add(e.category) })
  return [...cats].sort()
})

const overallAccuracy = computed(() => {
  const c = stats.value.outcomes?.correct || 0
  const ic = stats.value.outcomes?.incorrect || 0
  const total = c + ic
  if (total === 0) return '--'
  return (c / total * 100).toFixed(1) + '%'
})

const filteredEntries = computed(() => {
  let result = [...entries.value]

  if (filterCategory.value) {
    result = result.filter(e => e.category === filterCategory.value)
  }

  if (filterOutcome.value === 'correct') {
    result = result.filter(e => e.was_correct === true)
  } else if (filterOutcome.value === 'incorrect') {
    result = result.filter(e => e.was_correct === false)
  } else if (filterOutcome.value === 'pending') {
    result = result.filter(e => e.was_correct == null)
  }

  if (sortField.value === 'edge') {
    result.sort((a, b) => {
      const ea = Math.abs((a.our_prediction || 0) - (a.market_odds_at_prediction || 0))
      const eb = Math.abs((b.our_prediction || 0) - (b.market_odds_at_prediction || 0))
      return eb - ea
    })
  } else if (sortField.value === 'our_prediction') {
    result.sort((a, b) => (b.our_prediction || 0) - (a.our_prediction || 0))
  } else {
    result.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''))
  }

  return result
})

function toggleCategoryFilter(cat) {
  filterCategory.value = filterCategory.value === cat ? '' : cat
}

function truncate(s, max) {
  if (!s) return ''
  return s.length > max ? s.slice(0, max) + '...' : s
}

function pct(v) {
  if (v == null) return '--'
  return (v * 100).toFixed(1) + '%'
}

function edgeStr(entry) {
  const pred = entry.our_prediction || 0
  const market = entry.market_odds_at_prediction || 0
  const edge = pred - market
  if (edge === 0) return '--'
  return (edge > 0 ? '+' : '') + (edge * 100).toFixed(1) + '%'
}

function edgeColor(entry) {
  const pred = entry.our_prediction || 0
  const market = entry.market_odds_at_prediction || 0
  const edge = pred - market
  if (Math.abs(edge) < 0.01) return ''
  return edge > 0 ? 'text-positive' : 'text-negative'
}

function accuracyColor(acc) {
  if (acc >= 0.6) return 'text-good'
  if (acc >= 0.5) return 'text-mixed'
  return 'text-weak'
}

function outcomeClass(entry) {
  if (entry.was_correct === true) return 'outcome-win'
  if (entry.was_correct === false) return 'outcome-loss'
  return 'outcome-pending'
}

function outcomeLabel(entry) {
  if (entry.was_correct === true) return 'Win'
  if (entry.was_correct === false) return 'Loss'
  return 'Pending'
}

function formatTs(ts) {
  if (!ts) return '--'
  try {
    const d = new Date(ts)
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
           d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts
  }
}

async function fetchAll() {
  loading.value = true
  try {
    const [statsRes, entriesRes] = await Promise.all([
      fetch('/api/polymarket/knowledge/stats'),
      fetch('/api/polymarket/knowledge/entries?limit=500'),
    ])
    const statsJson = await statsRes.json()
    const entriesJson = await entriesRes.json()

    if (statsJson.success) {
      stats.value = statsJson.data
      accuracyData.value = statsJson.data.accuracy || {}
    }
    if (entriesJson.success) {
      entries.value = entriesJson.data.entries || []
    }
  } catch (err) {
    console.error('Failed to load knowledge base:', err)
  } finally {
    loading.value = false
  }
}

async function doSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  searchDone.value = false
  lastSearchQuery.value = searchQuery.value
  try {
    const res = await fetch('/api/polymarket/knowledge/related?q=' + encodeURIComponent(searchQuery.value) + '&limit=10')
    const json = await res.json()
    if (json.success) {
      searchResults.value = json.data.entries || []
    }
  } catch (err) {
    console.error('Search failed:', err)
    searchResults.value = []
  } finally {
    searching.value = false
    searchDone.value = true
  }
}

onMounted(fetchAll)
</script>

<style scoped>
/* ========================================
   Layout
   ======================================== */
.knowledge-base {
  max-width: 1280px;
  margin: 0 auto;
  padding: 32px 32px 80px;
  font-family: 'Space Grotesk', 'JetBrains Mono', sans-serif;
}

.header {
  margin-bottom: 24px;
}

.header h1 {
  font-family: 'JetBrains Mono', monospace;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.5px;
}

.subtitle {
  color: #666;
  font-size: 14px;
  margin-top: 4px;
  display: block;
}

/* ========================================
   Stats Row
   ======================================== */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.stat-card {
  background: #fafafa;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 28px;
  font-weight: 700;
}

.stat-value.accent {
  color: #FF4500;
}

.stat-label {
  font-size: 12px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

/* ========================================
   Section
   ======================================== */
.section {
  margin-bottom: 40px;
}

.section-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 16px;
  letter-spacing: -0.3px;
}

.loading {
  color: #888;
  font-size: 14px;
  padding: 24px 0;
}

.empty {
  color: #999;
  font-size: 14px;
  padding: 24px 0;
  text-align: center;
  background: #fafafa;
  border: 1px dashed #ddd;
  border-radius: 8px;
}

.empty.small {
  padding: 16px;
  font-size: 13px;
}

/* ========================================
   Accuracy Grid
   ======================================== */
.accuracy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.accuracy-card {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.15s;
}

.accuracy-card:hover {
  border-color: #000;
}

.accuracy-card.filter-active {
  border-color: #FF4500;
  box-shadow: 0 0 0 1px #FF4500;
}

.accuracy-card-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 10px;
}

.category-name {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  font-size: 14px;
  text-transform: capitalize;
}

.category-count {
  font-size: 11px;
  color: #999;
}

.accuracy-bar-wrapper {
  margin-bottom: 10px;
}

.accuracy-bar {
  height: 6px;
  background: #eee;
  border-radius: 3px;
  display: flex;
  overflow: hidden;
}

.accuracy-fill.correct {
  background: #22c55e;
  transition: width 0.4s ease;
}

.accuracy-fill.incorrect {
  background: #ef4444;
  transition: width 0.4s ease;
}

.accuracy-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.accuracy-pct {
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  font-weight: 700;
}

.text-good { color: #22c55e; }
.text-mixed { color: #eab308; }
.text-weak { color: #ef4444; }

.pending-count {
  font-size: 11px;
  color: #aaa;
}

/* ========================================
   Filter Bar
   ======================================== */
.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.filter-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.chip {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  padding: 4px 10px;
  border: 1px solid #ddd;
  border-radius: 20px;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
  text-transform: capitalize;
  font-weight: 600;
}

.chip:hover {
  border-color: #000;
}

.chip.active {
  background: #000;
  color: #fff;
  border-color: #000;
}

.filter-right {
  display: flex;
  gap: 8px;
}

.filter-select {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  padding: 6px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}

/* ========================================
   Intel Table
   ======================================== */
.table-wrapper {
  overflow-x: auto;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
}

.intel-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.intel-table th {
  background: #fafafa;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #888;
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid #e5e5e5;
  white-space: nowrap;
}

.intel-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: middle;
}

.intel-table tr:last-child td {
  border-bottom: none;
}

.intel-table tr:hover td {
  background: #fafafa;
}

.col-question {
  min-width: 240px;
  max-width: 340px;
}

.question-link {
  color: #000;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.15s;
}

.question-link:hover {
  color: #FF4500;
}

.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

.ts-col {
  white-space: nowrap;
  font-size: 11px;
  color: #999;
}

.text-positive { color: #22c55e; }
.text-negative { color: #ef4444; }

.category-chip {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  padding: 2px 8px;
  background: #f0f0f0;
  border-radius: 10px;
  text-transform: capitalize;
  cursor: pointer;
  transition: background 0.15s;
  font-weight: 600;
}

.category-chip:hover {
  background: #e0e0e0;
}

.consensus-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  text-transform: capitalize;
}

.consensus-bullish { background: #dcfce7; color: #166534; }
.consensus-bearish { background: #fee2e2; color: #991b1b; }
.consensus-divided { background: #fef9c3; color: #854d0e; }
.consensus-unknown { background: #f5f5f5; color: #999; }

.outcome-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}

.outcome-win { background: #dcfce7; color: #166534; }
.outcome-loss { background: #fee2e2; color: #991b1b; }
.outcome-pending { background: #f5f5f5; color: #999; }

/* ========================================
   Search
   ======================================== */
.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.search-input {
  flex: 1;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  padding: 10px 14px;
  border: 1px solid #ddd;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.15s;
}

.search-input:focus {
  border-color: #000;
}

.btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-primary {
  background: #000;
  color: #fff;
}

.btn-primary:hover:not(:disabled) {
  background: #333;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.search-results {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.search-result-card {
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 14px 16px;
  transition: border-color 0.15s;
}

.search-result-card:hover {
  border-color: #999;
}

.search-result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.search-result-question {
  font-weight: 600;
  font-size: 14px;
}

.search-result-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #666;
  flex-wrap: wrap;
  align-items: center;
}

.search-result-factors {
  margin-top: 8px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.factor-tag {
  font-size: 11px;
  padding: 2px 8px;
  background: #fff3e0;
  color: #e65100;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
}

/* ========================================
   Knowledge Graph Placeholder
   ======================================== */
.graph-placeholder {
  border: 1px dashed #ccc;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  background: #fafafa;
  position: relative;
  overflow: hidden;
}

.graph-nodes {
  position: relative;
  width: 400px;
  height: 200px;
  margin: 0 auto 24px;
}

.graph-edges {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.graph-edges line {
  stroke: #ddd;
  stroke-width: 1.5;
  stroke-dasharray: 4 4;
}

.gnode {
  position: absolute;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #ccc;
  animation: nodePulse 2.5s ease-in-out infinite;
}

.gnode.n1 { left: 73px; top: 53px; background: #FF4500; animation-delay: 0s; }
.gnode.n2 { left: 193px; top: 93px; background: #000; animation-delay: 0.4s; }
.gnode.n3 { left: 313px; top: 43px; background: #FF4500; animation-delay: 0.8s; }
.gnode.n4 { left: 143px; top: 153px; background: #999; animation-delay: 1.2s; }
.gnode.n5 { left: 343px; top: 143px; background: #999; animation-delay: 1.6s; }
.gnode.n6 { left: 53px; top: 143px; background: #000; animation-delay: 2.0s; }

@keyframes nodePulse {
  0%, 100% { transform: scale(1); opacity: 0.7; }
  50% { transform: scale(1.3); opacity: 1; }
}

.graph-label {
  color: #999;
  font-size: 13px;
  line-height: 1.6;
  max-width: 520px;
  margin: 0 auto;
}

/* ========================================
   Responsive
   ======================================== */
@media (max-width: 768px) {
  .knowledge-base {
    padding: 16px 16px 80px;
  }

  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .accuracy-grid {
    grid-template-columns: 1fr;
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-right {
    justify-content: flex-end;
  }

  .graph-nodes {
    transform: scale(0.7);
    transform-origin: top center;
    height: 140px;
  }
}
</style>
