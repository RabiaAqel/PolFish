<template>
  <div class="decision-log">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1>Decision Log</h1>
        <span class="subtitle">Every decision the system makes, explained</span>
      </div>
    </header>

    <!-- Stats Bar -->
    <section class="stats-row">
      <div class="stat-card">
        <span class="stat-value">{{ stats.total_entries || 0 }}</span>
        <span class="stat-label">Total Entries</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ stats.total_cycles || 0 }}</span>
        <span class="stat-label">Total Cycles</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ betsPlaced }}</span>
        <span class="stat-label">Bets Placed</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ betsSkipped }}</span>
        <span class="stat-label">Bets Skipped</span>
      </div>
    </section>

    <!-- Filter Bar -->
    <section class="filter-bar">
      <select v-model="filterType" class="filter-select" @change="applyFilters">
        <option value="">All Types</option>
        <option v-for="t in entryTypes" :key="t" :value="t">{{ t }}</option>
      </select>
      <div class="search-wrapper">
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="Search entries..."
          @keydown.enter="doSearch"
        />
        <button class="btn btn-search" @click="doSearch" :disabled="!searchQuery.trim()">Search</button>
      </div>
      <button
        v-if="filterType || searchQuery || activeCycleFilter"
        class="btn btn-clear"
        @click="clearFilters"
      >
        Clear Filters
      </button>
      <span v-if="activeCycleFilter" class="cycle-filter-badge">
        Cycle: {{ activeCycleFilter }}
        <button class="badge-close" @click="clearCycleFilter">&times;</button>
      </span>
    </section>

    <!-- Loading -->
    <div v-if="loading" class="loading">Loading entries...</div>

    <!-- Empty State -->
    <div v-else-if="entries.length === 0" class="empty">
      No entries found. Run a trading cycle to generate decisions.
    </div>

    <!-- Entry List -->
    <section v-else class="entries">
      <div
        v-for="entry in entries"
        :key="entry.id"
        class="entry-card"
        :class="borderClass(entry)"
      >
        <div class="entry-header">
          <span class="entry-type-badge" :class="typeBadgeClass(entry.entry_type)">
            {{ entry.entry_type }}
          </span>
          <span
            v-if="entry.cycle_id && entry.cycle_id !== 'manual'"
            class="cycle-link"
            @click="filterByCycle(entry.cycle_id)"
          >
            {{ entry.cycle_id }}
          </span>
          <span v-else-if="entry.cycle_id === 'manual'" class="cycle-manual">manual</span>
          <span class="entry-ts">{{ formatTs(entry.timestamp) }}</span>
        </div>

        <div v-if="entry.question" class="entry-question">
          {{ entry.question }}
        </div>

        <div v-if="entry.explanation" class="entry-explanation">
          {{ entry.explanation }}
        </div>

        <div v-if="hasDataFields(entry)" class="entry-data">
          <span v-if="entry.data.side" class="data-tag">
            Side: <strong>{{ entry.data.side }}</strong>
          </span>
          <span v-if="entry.data.amount != null" class="data-tag">
            Amount: <strong>${{ Number(entry.data.amount).toFixed(2) }}</strong>
          </span>
          <span v-if="entry.data.edge != null" class="data-tag">
            Edge: <strong>{{ entry.data.edge >= 0 ? '+' : '' }}{{ (entry.data.edge * 100).toFixed(1) }}%</strong>
          </span>
          <span v-if="entry.data.mode" class="data-tag">
            Mode: <strong>{{ entry.data.mode }}</strong>
          </span>
          <span v-if="entry.data.predicted_prob != null || entry.data.prediction != null" class="data-tag">
            Predicted: <strong>{{ ((entry.data.predicted_prob || entry.data.prediction || 0) * 100).toFixed(1) }}%</strong>
          </span>
          <span v-if="entry.data.market_prob != null || entry.data.yes_price != null" class="data-tag">
            Market: <strong>{{ ((entry.data.market_prob || entry.data.yes_price || 0) * 100).toFixed(1) }}%</strong>
          </span>
          <span v-if="entry.data.kelly_fraction != null" class="data-tag">
            Kelly: <strong>{{ entry.data.kelly_fraction.toFixed(3) }}</strong>
          </span>
          <span v-if="entry.data.confidence" class="data-tag">
            Confidence: <strong>{{ entry.data.confidence }}</strong>
          </span>
          <span v-if="entry.data.won != null" class="data-tag">
            Result: <strong :class="entry.data.won ? 'text-win' : 'text-loss'">{{ entry.data.won ? 'WIN' : 'LOSS' }}</strong>
          </span>
          <span v-if="entry.data.pnl != null" class="data-tag">
            P&amp;L: <strong :class="entry.data.pnl >= 0 ? 'text-win' : 'text-loss'">
              ${{ entry.data.pnl >= 0 ? '+' : '' }}{{ Number(entry.data.pnl).toFixed(2) }}
            </strong>
          </span>
          <span v-if="entry.data.scanned != null" class="data-tag">
            Scanned: <strong>{{ entry.data.scanned }}</strong>
          </span>
          <span v-if="entry.data.bets_placed != null" class="data-tag">
            Bets: <strong>{{ entry.data.bets_placed }}</strong>
          </span>
          <span v-if="entry.data.resolved != null" class="data-tag">
            Resolved: <strong>{{ entry.data.resolved }}</strong>
          </span>
          <span v-if="entry.data.quick_prediction != null" class="data-tag">
            Quick: <strong>{{ (entry.data.quick_prediction * 100).toFixed(1) }}%</strong>
          </span>
          <span v-if="entry.data.deep_prediction != null" class="data-tag">
            Deep: <strong>{{ (entry.data.deep_prediction * 100).toFixed(1) }}%</strong>
          </span>
          <span v-if="entry.data.quick_edge != null" class="data-tag">
            Quick Edge: <strong>{{ (entry.data.quick_edge * 100).toFixed(1) }}%</strong>
          </span>
          <span v-if="entry.data.deep_edge != null" class="data-tag">
            Deep Edge: <strong>{{ (entry.data.deep_edge * 100).toFixed(1) }}%</strong>
          </span>
        </div>
      </div>
    </section>

    <!-- Load More -->
    <div v-if="entries.length > 0 && hasMore" class="load-more">
      <button class="btn btn-secondary" @click="loadMore" :disabled="loadingMore">
        {{ loadingMore ? 'Loading...' : 'Load More' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const entryTypes = [
  'BET_PLACED',
  'BET_SKIPPED',
  'BET_RESOLVED',
  'DEEP_CONFIRMED',
  'DEEP_REJECTED',
  'PARAM_CHANGED',
  'CALIBRATION_UPDATE',
  'CYCLE_SUMMARY',
]

// State
const entries = ref([])
const stats = ref({})
const loading = ref(true)
const loadingMore = ref(false)
const filterType = ref('')
const searchQuery = ref('')
const activeCycleFilter = ref('')
const hasMore = ref(true)
const pageSize = 50

let pollInterval = null

// Computed
const betsPlaced = computed(() => {
  const bt = stats.value.entries_by_type
  return bt ? (bt.BET_PLACED || 0) : 0
})
const betsSkipped = computed(() => {
  const bt = stats.value.entries_by_type
  return bt ? (bt.BET_SKIPPED || 0) : 0
})

// API helper
const api = async (path) => {
  try {
    const res = await fetch(`/api/polymarket${path}`)
    return await res.json()
  } catch {
    return { success: false }
  }
}

// Fetch functions
const fetchStats = async () => {
  const data = await api('/ledger/stats')
  if (data.success && data.data) {
    stats.value = data.data
  }
}

const fetchEntries = async () => {
  loading.value = true

  try {
    let path = ''

    if (searchQuery.value.trim()) {
      path = `/ledger/search?q=${encodeURIComponent(searchQuery.value.trim())}&limit=${pageSize}`
    } else if (activeCycleFilter.value) {
      path = `/ledger/cycle/${encodeURIComponent(activeCycleFilter.value)}`
    } else if (filterType.value) {
      path = `/ledger/entries?type=${filterType.value}&limit=${pageSize}&offset=0`
    } else {
      path = `/ledger/recent?limit=${pageSize}`
    }

    const data = await api(path)
    if (data.success && data.data) {
      entries.value = data.data.entries || []
      hasMore.value = (data.data.entries || []).length >= pageSize
    }
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  activeCycleFilter.value = ''
  searchQuery.value = ''
  fetchEntries()
}

const doSearch = () => {
  if (!searchQuery.value.trim()) return
  filterType.value = ''
  activeCycleFilter.value = ''
  fetchEntries()
}

const clearFilters = () => {
  filterType.value = ''
  searchQuery.value = ''
  activeCycleFilter.value = ''
  fetchEntries()
}

const filterByCycle = (cycleId) => {
  activeCycleFilter.value = cycleId
  filterType.value = ''
  searchQuery.value = ''
  fetchEntries()
}

const clearCycleFilter = () => {
  activeCycleFilter.value = ''
  fetchEntries()
}

const loadMore = () => {
  if (activeCycleFilter.value || searchQuery.value.trim()) return
  const offset = entries.value.length
  loadingMore.value = true

  const typePart = filterType.value ? `type=${filterType.value}&` : ''
  api(`/ledger/entries?${typePart}limit=${pageSize}&offset=${offset}`).then((data) => {
    if (data.success && data.data) {
      const newEntries = data.data.entries || []
      entries.value = [...entries.value, ...newEntries]
      hasMore.value = newEntries.length >= pageSize
    }
    loadingMore.value = false
  })
}

// Display helpers
const formatTs = (ts) => {
  if (!ts) return '--'
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

const borderClass = (entry) => {
  const t = entry.entry_type
  if (t === 'BET_PLACED' || t === 'DEEP_CONFIRMED') return 'border-green'
  if (t === 'BET_SKIPPED') return 'border-gray'
  if (t === 'BET_RESOLVED') {
    return entry.data && entry.data.won ? 'border-green' : 'border-red'
  }
  if (t === 'DEEP_REJECTED') return 'border-orange'
  if (t === 'PARAM_CHANGED' || t === 'CALIBRATION_UPDATE') return 'border-blue'
  if (t === 'CYCLE_SUMMARY') return 'border-black'
  return ''
}

const typeBadgeClass = (type) => {
  if (type === 'BET_PLACED' || type === 'DEEP_CONFIRMED') return 'badge-green'
  if (type === 'BET_SKIPPED') return 'badge-gray'
  if (type === 'BET_RESOLVED') return 'badge-purple'
  if (type === 'DEEP_REJECTED') return 'badge-orange'
  if (type === 'PARAM_CHANGED' || type === 'CALIBRATION_UPDATE') return 'badge-blue'
  if (type === 'CYCLE_SUMMARY') return 'badge-black'
  return 'badge-gray'
}

const hasDataFields = (entry) => {
  const d = entry.data
  if (!d || typeof d !== 'object') return false
  return (
    d.side || d.amount != null || d.edge != null || d.mode ||
    d.predicted_prob != null || d.prediction != null ||
    d.market_prob != null || d.yes_price != null ||
    d.kelly_fraction != null || d.confidence ||
    d.won != null || d.pnl != null ||
    d.scanned != null || d.bets_placed != null || d.resolved != null ||
    d.quick_prediction != null || d.deep_prediction != null ||
    d.quick_edge != null || d.deep_edge != null
  )
}

// Lifecycle
onMounted(() => {
  Promise.all([fetchStats(), fetchEntries()])
  pollInterval = setInterval(fetchStats, 15000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
})
</script>

<style scoped>
.decision-log {
  font-family: 'Space Grotesk', 'JetBrains Mono', monospace;
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 24px 60px;
  color: var(--black, #1a1a1a);
}

/* Header */
.header {
  margin-bottom: 32px;
}
.header h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
}
.subtitle {
  color: #999;
  font-size: 14px;
}

/* Stats Row */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
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
.stat-label {
  font-size: 11px;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-top: 4px;
}

/* Filter Bar */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.filter-select {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  padding: 8px 12px;
  border: 2px solid var(--black, #1a1a1a);
  background: #fff;
  cursor: pointer;
  appearance: none;
  min-width: 180px;
}
.search-wrapper {
  display: flex;
  gap: 0;
  flex: 1;
  max-width: 400px;
}
.search-input {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  padding: 8px 12px;
  border: 2px solid var(--black, #1a1a1a);
  border-right: none;
  flex: 1;
  outline: none;
}
.search-input:focus {
  border-color: #FF4500;
}
.btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  padding: 8px 16px;
  border: 2px solid var(--black, #1a1a1a);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.btn-search {
  background: var(--black, #1a1a1a);
  color: #fff;
}
.btn-search:hover:not(:disabled) {
  background: #333;
}
.btn-clear {
  background: #fff;
  color: var(--black, #1a1a1a);
}
.btn-clear:hover {
  background: #f5f5f5;
}
.btn-secondary {
  background: #fff;
  color: var(--black, #1a1a1a);
}
.btn-secondary:hover:not(:disabled) {
  background: #f5f5f5;
}

.cycle-filter-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  padding: 6px 10px;
  background: #f0f0f0;
  border: 1px solid #ddd;
  color: #666;
}
.badge-close {
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
  color: #999;
  padding: 0 2px;
  line-height: 1;
}
.badge-close:hover {
  color: var(--black, #1a1a1a);
}

/* Loading / Empty */
.loading, .empty {
  color: #999;
  font-size: 14px;
  padding: 48px 0;
  text-align: center;
  border: 1px dashed var(--border, #E5E5E5);
}

/* Entry Cards */
.entries {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.entry-card {
  border: 1px solid var(--border, #E5E5E5);
  border-left: 4px solid #E5E5E5;
  padding: 16px 20px;
  transition: border-color 0.15s;
}
.entry-card:hover {
  border-color: #ccc;
}

/* Border colors by type */
.border-green { border-left-color: #28a745; }
.border-gray { border-left-color: #999; }
.border-red { border-left-color: #dc3545; }
.border-orange { border-left-color: #FF4500; }
.border-blue { border-left-color: #2196F3; }
.border-black { border-left-color: var(--black, #1a1a1a); }

/* Entry Header */
.entry-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.entry-type-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 3px 8px;
  text-transform: uppercase;
}
.badge-green { background: #e8f5e9; color: #28a745; }
.badge-gray { background: #f5f5f5; color: #999; }
.badge-purple { background: #f3e5f5; color: #9c27b0; }
.badge-orange { background: #fff3e0; color: #e65100; }
.badge-blue { background: #e3f2fd; color: #1565c0; }
.badge-black { background: #f0f0f0; color: var(--black, #1a1a1a); }

.cycle-link {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #FF4500;
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 2px;
}
.cycle-link:hover {
  color: #cc3700;
}
.cycle-manual {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #bbb;
}
.entry-ts {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #999;
  margin-left: auto;
}

/* Entry Content */
.entry-question {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 6px;
  line-height: 1.4;
}
.entry-explanation {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  color: #555;
  line-height: 1.5;
  margin-bottom: 10px;
}

/* Entry Data Tags */
.entry-data {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.data-tag {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  padding: 3px 8px;
  background: #fafafa;
  border: 1px solid var(--border, #E5E5E5);
  color: #666;
}
.data-tag strong {
  color: var(--black, #1a1a1a);
}
.text-win { color: #28a745 !important; }
.text-loss { color: #dc3545 !important; }

/* Load More */
.load-more {
  text-align: center;
  padding: 24px 0;
}
</style>
