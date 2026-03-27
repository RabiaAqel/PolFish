<template>
  <teleport to="body">
    <div class="settings-overlay" @click.self="$emit('close')">
      <div class="settings-panel">
        <!-- Header -->
        <div class="panel-header">
          <h2>Settings</h2>
          <button class="panel-close" @click="$emit('close')">&times;</button>
        </div>

        <!-- Tabs -->
        <div class="panel-tabs">
          <button v-for="tab in tabs" :key="tab.id" class="panel-tab" :class="{ active: activeTab === tab.id }" @click="activeTab = tab.id">{{ tab.label }}</button>
        </div>

        <!-- Content -->
        <div class="panel-body">
          <!-- Pipeline Tab -->
          <div v-if="activeTab === 'pipeline'" class="tab-content">
            <label class="field-label">Pipeline Preset</label>
            <div class="preset-list">
              <label
                v-for="(info, name) in presets"
                :key="name"
                class="preset-option"
                :class="{ active: selectedPreset === name }"
              >
                <input type="radio" v-model="selectedPreset" :value="name" />
                <span class="preset-name">{{ name }}</span>
                <span class="preset-cost">~${{ presetCosts[name] || '?' }}/pred</span>
              </label>
            </div>

            <label class="field-label">Prediction Method</label>
            <div class="radio-group">
              <label class="radio-option" :class="{ active: custom.prediction_method === 'combined' }">
                <input type="radio" v-model="custom.prediction_method" value="combined" /> Combined
              </label>
              <label class="radio-option" :class="{ active: custom.prediction_method === 'llm_only' }">
                <input type="radio" v-model="custom.prediction_method" value="llm_only" /> LLM Only
              </label>
              <label class="radio-option" :class="{ active: custom.prediction_method === 'quant_only' }">
                <input type="radio" v-model="custom.prediction_method" value="quant_only" /> Quant Only
              </label>
            </div>

            <label class="field-label">Max Rounds</label>
            <div class="chip-group">
              <button v-for="v in [15, 25, 40, 60]" :key="v" class="chip-btn" :class="{ active: custom.max_rounds === v }" @click="custom.max_rounds = v">{{ v }}</button>
            </div>
          </div>

          <!-- Trading Tab -->
          <div v-if="activeTab === 'trading'" class="tab-content">
            <label class="field-label">Engine Mode</label>
            <div class="radio-group">
              <label class="radio-option" :class="{ active: custom.engine_mode === 'quick' }">
                <input type="radio" v-model="custom.engine_mode" value="quick" /> Quick (free)
              </label>
              <label class="radio-option" :class="{ active: custom.engine_mode === 'autopilot' }">
                <input type="radio" v-model="custom.engine_mode" value="autopilot" /> Autopilot (~$12/cycle)
              </label>
            </div>

            <label class="field-label">Kelly Factor</label>
            <div class="chip-group">
              <button v-for="v in [0.10, 0.15, 0.25, 0.50]" :key="v" class="chip-btn" :class="{ active: strategy.kelly_factor === v }" @click="strategy.kelly_factor = v">{{ v }}</button>
            </div>

            <label class="field-label">Min Edge for Bet</label>
            <div class="stepper">
              <button class="stepper-btn" @click="autopilot.min_edge_for_bet = Math.max(0, round2(autopilot.min_edge_for_bet - 0.01))">-</button>
              <span class="stepper-value">{{ (autopilot.min_edge_for_bet * 100).toFixed(0) }}%</span>
              <button class="stepper-btn" @click="autopilot.min_edge_for_bet = Math.min(0.5, round2(autopilot.min_edge_for_bet + 0.01))">+</button>
            </div>

            <label class="field-label">Min Volume</label>
            <div class="chip-group">
              <button v-for="v in [100, 500, 1000, 5000, 10000]" :key="v" class="chip-btn" :class="{ active: autopilot.min_volume === v }" @click="autopilot.min_volume = v">${{ v >= 1000 ? (v/1000) + 'K' : v }}</button>
            </div>

            <label class="field-label">Niche Focus</label>
            <div class="toggle-row">
              <button class="toggle-btn" :class="{ active: autopilot.niche_focus }" @click="autopilot.niche_focus = true">ON</button>
              <button class="toggle-btn" :class="{ active: !autopilot.niche_focus }" @click="autopilot.niche_focus = false">OFF</button>
            </div>
          </div>

          <!-- Keys Tab -->
          <div v-if="activeTab === 'keys'" class="tab-content">
            <div v-for="(configured, name) in apiKeys" :key="name" class="api-key-row">
              <span class="api-key-status" :class="configured ? 'status-ok' : 'status-missing'">{{ configured ? '&#10003;' : '&#10007;' }}</span>
              <span class="api-key-name">{{ apiKeyLabels[name] || name }}</span>
              <span class="api-key-state">{{ configured ? 'Configured' : 'Missing' }}</span>
            </div>
            <p class="env-hint">API keys are read from environment variables. Edit your <code>.env</code> file to add or change keys.</p>
          </div>

          <!-- Advanced Tab -->
          <div v-if="activeTab === 'advanced'" class="tab-content">
            <label class="field-label">Cash Reserve</label>
            <div class="chip-group">
              <button v-for="v in [0.10, 0.15, 0.20, 0.25, 0.30]" :key="v" class="chip-btn" :class="{ active: custom.cash_reserve === v }" @click="custom.cash_reserve = v">{{ (v * 100).toFixed(0) }}%</button>
            </div>

            <label class="field-label">Max Sector Exposure</label>
            <div class="chip-group">
              <button v-for="v in [0.20, 0.30, 0.40, 0.50]" :key="v" class="chip-btn" :class="{ active: custom.max_sector_exposure === v }" @click="custom.max_sector_exposure = v">{{ (v * 100).toFixed(0) }}%</button>
            </div>

            <label class="field-label">Deep Research</label>
            <div class="toggle-row">
              <button class="toggle-btn" :class="{ active: custom.deep_research }" @click="custom.deep_research = true">ON</button>
              <button class="toggle-btn" :class="{ active: !custom.deep_research }" @click="custom.deep_research = false">OFF</button>
            </div>

            <label class="field-label">Agent Diversity</label>
            <div class="toggle-row">
              <button class="toggle-btn" :class="{ active: custom.agent_diversity }" @click="custom.agent_diversity = true">ON</button>
              <button class="toggle-btn" :class="{ active: !custom.agent_diversity }" @click="custom.agent_diversity = false">OFF</button>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="panel-footer">
          <button class="btn btn-outline" @click="resetToDefaults">Reset</button>
          <button class="btn btn-primary" @click="saveAll" :disabled="saving">{{ saving ? 'Saving...' : 'Save' }}</button>
        </div>

        <!-- Toast -->
        <transition name="toast">
          <div v-if="toast.show" class="toast" :class="'toast-' + toast.type">{{ toast.msg }}</div>
        </transition>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'

defineEmits(['close'])

const tabs = [
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'trading', label: 'Trading' },
  { id: 'keys', label: 'Keys' },
  { id: 'advanced', label: 'Advanced' },
]

const activeTab = ref('pipeline')
const saving = ref(false)
const toast = reactive({ show: false, msg: '', type: 'success' })

const selectedPreset = ref('balanced')
const presets = ref({})
const presetCosts = {
  balanced: '0.42', budget: '0.03', premium: '0.54', cheapest: '0.02',
  best: '0.58', gemini: '0.03', local: '0.00', hybrid_local: '0.12',
}

const autopilot = reactive({
  max_deep_per_cycle: 3, max_cost_per_cycle: 15, min_edge_for_deep: 0.05,
  min_edge_for_bet: 0.03, cycle_interval_hours: 6, niche_focus: true,
  quick_research: false, max_markets_to_scan: 50, days_ahead: 7, min_volume: 500,
})

const strategy = reactive({ kelly_factor: 0.25, odds_range: [0.10, 0.90], max_bet_pct: 0.05, min_edge_threshold: 0.03 })

const custom = reactive({
  max_rounds: 40, entity_type_limit: 20, deep_research: true, agent_diversity: true,
  prediction_method: 'combined', llm_weight_override: 0.5, engine_mode: 'quick',
  cash_reserve: 0.20, max_sector_exposure: 0.40, excluded_slugs: '', target_slugs: '',
})

const apiKeys = ref({})
const apiKeyLabels = { openai: 'OpenAI', deepseek: 'DeepSeek', gemini: 'Gemini', anthropic: 'Anthropic', ollama: 'Ollama (Local)', zep: 'Zep (Memory)' }

const round2 = (v) => Math.round(v * 100) / 100

function showToast(msg, type = 'success') {
  toast.msg = msg; toast.type = type; toast.show = true
  setTimeout(() => { toast.show = false }, 3000)
}

async function fetchSettings() {
  try {
    const res = await fetch('/api/polymarket/settings')
    const json = await res.json()
    if (json.success && json.data) {
      const d = json.data
      if (d.autopilot) Object.assign(autopilot, d.autopilot)
      if (d.pipeline_preset) selectedPreset.value = d.pipeline_preset
      if (d.presets) presets.value = d.presets
      if (d.strategy) Object.assign(strategy, { kelly_factor: d.strategy.kelly_factor ?? 0.25, odds_range: d.strategy.odds_range ?? [0.10, 0.90], max_bet_pct: d.strategy.max_bet_pct ?? 0.05, min_edge_threshold: d.strategy.min_edge_threshold ?? 0.03 })
      if (d.custom) Object.assign(custom, d.custom)
      if (d.api_keys) apiKeys.value = d.api_keys
    }
  } catch { /* ignore */ }
}

async function saveAll() {
  saving.value = true
  try {
    const body = {
      autopilot: { ...autopilot },
      strategy: { kelly_factor: strategy.kelly_factor, odds_range: strategy.odds_range, max_bet_pct: strategy.max_bet_pct, min_edge_threshold: strategy.min_edge_threshold },
      custom: { ...custom, pipeline_preset: selectedPreset.value },
    }
    const res = await fetch('/api/polymarket/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    const json = await res.json()
    if (json.success) showToast('Settings saved')
    else showToast('Save failed', 'error')
  } catch { showToast('Save failed: network error', 'error') }
  finally { saving.value = false }
}

function resetToDefaults() {
  selectedPreset.value = 'balanced'
  Object.assign(autopilot, { max_deep_per_cycle: 3, max_cost_per_cycle: 15, min_edge_for_deep: 0.05, min_edge_for_bet: 0.03, cycle_interval_hours: 6, niche_focus: true, quick_research: false, max_markets_to_scan: 50, days_ahead: 7, min_volume: 500 })
  Object.assign(strategy, { kelly_factor: 0.25, odds_range: [0.10, 0.90], max_bet_pct: 0.05, min_edge_threshold: 0.03 })
  Object.assign(custom, { max_rounds: 40, entity_type_limit: 20, deep_research: true, agent_diversity: true, prediction_method: 'combined', llm_weight_override: 0.5, engine_mode: 'quick', cash_reserve: 0.20, max_sector_exposure: 0.40, excluded_slugs: '', target_slugs: '' })
  showToast('Reset to defaults - click Save to persist')
}

onMounted(fetchSettings)
</script>

<style scoped>
.settings-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 2000;
  display: flex;
  justify-content: flex-end;
}

.settings-panel {
  width: 400px;
  max-width: 100vw;
  height: 100%;
  background: #fff;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.15);
  position: relative;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e5e5;
  flex-shrink: 0;
}

.panel-header h2 {
  font-family: 'JetBrains Mono', monospace;
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}

.panel-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
  padding: 0 4px;
  line-height: 1;
}

.panel-close:hover { color: #000; }

/* Tabs */
.panel-tabs {
  display: flex;
  border-bottom: 1px solid #e5e5e5;
  flex-shrink: 0;
}

.panel-tab {
  flex: 1;
  padding: 10px 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  color: #999;
  transition: all 0.15s;
}

.panel-tab:hover { color: #333; }
.panel-tab.active { color: #FF4500; border-bottom-color: #FF4500; }

/* Body */
.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #888;
  margin-bottom: -8px;
}

/* Presets */
.preset-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preset-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  transition: all 0.15s;
}

.preset-option:hover { border-color: #999; }
.preset-option.active { border-color: #FF4500; background: #FFF3E0; }
.preset-option input { display: none; }

.preset-name { font-weight: 700; text-transform: capitalize; flex: 1; }
.preset-cost { color: #999; font-size: 11px; }

/* Radio group */
.radio-group {
  display: flex;
  gap: 4px;
}

.radio-option {
  flex: 1;
  padding: 8px 10px;
  text-align: center;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}

.radio-option:hover { border-color: #999; }
.radio-option.active { border-color: #000; background: #000; color: #fff; }
.radio-option input { display: none; }

/* Chips */
.chip-group {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.chip-btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  padding: 6px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.chip-btn:hover { border-color: #000; }
.chip-btn.active { background: #000; color: #fff; border-color: #000; }

/* Stepper */
.stepper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stepper-btn {
  width: 32px;
  height: 32px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stepper-btn:hover { border-color: #000; }

.stepper-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  font-weight: 700;
  min-width: 40px;
  text-align: center;
}

/* Toggle */
.toggle-row {
  display: flex;
  gap: 4px;
}

.toggle-btn {
  padding: 6px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.toggle-btn:hover { border-color: #000; }
.toggle-btn.active { background: #000; color: #fff; border-color: #000; }

/* API Keys */
.api-key-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}

.api-key-status { font-size: 14px; }
.status-ok { color: #22c55e; }
.status-missing { color: #ef4444; }
.api-key-name { font-weight: 600; flex: 1; }
.api-key-state { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #999; }

.env-hint {
  font-size: 12px;
  color: #999;
  margin-top: 12px;
  line-height: 1.5;
}

.env-hint code {
  background: #f5f5f5;
  padding: 1px 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

/* Footer */
.panel-footer {
  display: flex;
  gap: 8px;
  padding: 16px 24px;
  border-top: 1px solid #e5e5e5;
  flex-shrink: 0;
}

.btn {
  flex: 1;
  padding: 10px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-primary { background: #000; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #FF4500; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline { background: #fff; color: #000; border: 1px solid #ddd; }
.btn-outline:hover { border-color: #000; }

/* Toast */
.toast {
  position: absolute;
  bottom: 80px;
  left: 24px;
  right: 24px;
  padding: 10px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  border-radius: 4px;
  z-index: 10;
}

.toast-success { background: #E8F5E9; color: #2E7D32; }
.toast-error { background: #FFEBEE; color: #C62828; }

.toast-enter-active, .toast-leave-active { transition: all 0.3s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(10px); }

@media (max-width: 480px) {
  .settings-panel {
    width: 100vw;
  }
}
</style>
