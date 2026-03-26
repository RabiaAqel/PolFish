<template>
  <div class="settings-page">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1>Settings</h1>
        <span class="subtitle">Configure the PolFish prediction engine</span>
      </div>
      <div class="header-right">
        <button class="btn btn-outline" @click="resetToDefaults">Reset to Defaults</button>
        <button class="btn btn-primary" @click="saveAll" :disabled="saving">
          {{ saving ? 'Saving...' : 'Save All' }}
        </button>
      </div>
    </header>

    <!-- Toast -->
    <transition name="toast">
      <div v-if="toast.show" class="toast" :class="'toast-' + toast.type">
        {{ toast.msg }}
      </div>
    </transition>

    <!-- ============================================================
         Section 1: Pipeline Preset
         ============================================================ -->
    <section class="section">
      <div class="section-header" @click="sections.pipeline = !sections.pipeline">
        <span class="dot"></span>
        <h2>PIPELINE PRESET</h2>
        <span class="tip-wrap tip-below tip-left">
          <span class="help-icon" @click.stop>&#9432;</span>
          <span class="tip-content">Choose which LLM models power each pipeline stage. Each preset trades off cost vs quality.</span>
        </span>
        <span class="collapse-arrow">{{ sections.pipeline ? '\u25BC' : '\u25B6' }}</span>
      </div>
      <div v-show="sections.pipeline" class="section-body">
        <div class="preset-grid">
          <label
            v-for="(info, name) in presets"
            :key="name"
            class="preset-card"
            :class="{ active: selectedPreset === name }"
          >
            <input type="radio" v-model="selectedPreset" :value="name" />
            <span class="preset-name">{{ name }}</span>
            <span class="preset-desc">{{ presetDescriptions[name] || '' }}</span>
            <span class="preset-cost">~${{ presetCosts[name] || '?' }}/prediction</span>
            <div class="preset-stages" v-if="info && info.stages">
              <span v-for="(model, stage) in info.stages" :key="stage" class="preset-stage">
                {{ stage }}: <strong>{{ model }}</strong>
              </span>
            </div>
          </label>
        </div>
      </div>
    </section>

    <!-- ============================================================
         Section 2: Market Selection
         ============================================================ -->
    <section class="section">
      <div class="section-header" @click="sections.market = !sections.market">
        <span class="dot"></span>
        <h2>MARKET SELECTION</h2>
        <span class="tip-wrap tip-below tip-left">
          <span class="help-icon" @click.stop>&#9432;</span>
          <span class="tip-content">Control which Polymarket markets the scanner considers for predictions.</span>
        </span>
        <span class="collapse-arrow">{{ sections.market ? '\u25BC' : '\u25B6' }}</span>
      </div>
      <div v-show="sections.market" class="section-body">
        <div class="config-grid">
          <!-- Categories -->
          <div class="config-field config-field-wide">
            <label>Categories to include</label>
            <div class="checkbox-group">
              <label v-for="cat in allCategories" :key="cat" class="checkbox-label">
                <input type="checkbox" :value="cat" v-model="marketCategories" />
                {{ cat }}
              </label>
            </div>
          </div>

          <!-- Min Volume -->
          <div class="config-field">
            <label>Minimum volume</label>
            <div class="chip-group">
              <button
                v-for="v in [100, 500, 1000, 5000, 10000]"
                :key="v"
                class="chip-btn"
                :class="{ active: autopilot.min_volume === v }"
                @click="autopilot.min_volume = v"
              >${{ v >= 1000 ? (v/1000) + 'K' : v }}</button>
            </div>
          </div>

          <!-- Odds Range -->
          <div class="config-field">
            <label>Odds range</label>
            <div class="range-row">
              <div class="stepper stepper-sm">
                <button class="stepper-btn" @click="strategy.odds_range[0] = Math.max(0.01, round2(strategy.odds_range[0] - 0.05))">-</button>
                <input type="number" v-model.number="strategy.odds_range[0]" min="0.01" max="0.99" step="0.05" class="stepper-input" />
                <button class="stepper-btn" @click="strategy.odds_range[0] = Math.min(strategy.odds_range[1] - 0.05, round2(strategy.odds_range[0] + 0.05))">+</button>
                <span class="stepper-suffix">{{ (strategy.odds_range[0] * 100).toFixed(0) }}%</span>
              </div>
              <span class="range-sep">to</span>
              <div class="stepper stepper-sm">
                <button class="stepper-btn" @click="strategy.odds_range[1] = Math.max(strategy.odds_range[0] + 0.05, round2(strategy.odds_range[1] - 0.05))">-</button>
                <input type="number" v-model.number="strategy.odds_range[1]" min="0.01" max="0.99" step="0.05" class="stepper-input" />
                <button class="stepper-btn" @click="strategy.odds_range[1] = Math.min(0.99, round2(strategy.odds_range[1] + 0.05))">+</button>
                <span class="stepper-suffix">{{ (strategy.odds_range[1] * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>

          <!-- Days Ahead -->
          <div class="config-field">
            <label>Days ahead</label>
            <div class="stepper">
              <button class="stepper-btn" @click="autopilot.days_ahead = Math.max(0.25, round2(autopilot.days_ahead - 1))">-</button>
              <input type="number" v-model.number="autopilot.days_ahead" min="0.25" max="30" step="1" class="stepper-input" />
              <button class="stepper-btn" @click="autopilot.days_ahead = Math.min(30, round2(autopilot.days_ahead + 1))">+</button>
              <span class="stepper-suffix">{{ autopilot.days_ahead < 1 ? (autopilot.days_ahead * 24).toFixed(0) + 'h' : autopilot.days_ahead + 'd' }}</span>
            </div>
          </div>

          <!-- Niche Focus -->
          <div class="config-field">
            <label>Niche focus</label>
            <div class="toggle-row">
              <button class="toggle-btn" :class="{ active: autopilot.niche_focus }" @click="autopilot.niche_focus = true">ON</button>
              <button class="toggle-btn" :class="{ active: !autopilot.niche_focus }" @click="autopilot.niche_focus = false">OFF</button>
            </div>
          </div>

          <!-- Excluded slugs -->
          <div class="config-field config-field-wide">
            <label>Excluded slugs <span class="field-hint">One slug per line. These markets will be skipped.</span></label>
            <textarea v-model="custom.excluded_slugs" rows="3" class="text-input" placeholder="e.g. will-bitcoin-reach-100k&#10;us-presidential-election-2028"></textarea>
          </div>

          <!-- Target slugs -->
          <div class="config-field config-field-wide">
            <label>Target slugs <span class="field-hint">One slug per line. If set, scanner only analyzes these markets.</span></label>
            <textarea v-model="custom.target_slugs" rows="3" class="text-input" placeholder="e.g. specific-market-slug"></textarea>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         Section 3: Simulation Parameters
         ============================================================ -->
    <section class="section">
      <div class="section-header" @click="sections.simulation = !sections.simulation">
        <span class="dot"></span>
        <h2>SIMULATION PARAMETERS</h2>
        <span class="tip-wrap tip-below tip-left">
          <span class="help-icon" @click.stop>&#9432;</span>
          <span class="tip-content">Control the Monte Carlo agent simulation that powers deep predictions.</span>
        </span>
        <span class="collapse-arrow">{{ sections.simulation ? '\u25BC' : '\u25B6' }}</span>
      </div>
      <div v-show="sections.simulation" class="section-body">
        <div class="config-grid">
          <!-- Max rounds -->
          <div class="config-field">
            <label>Max rounds</label>
            <div class="chip-group">
              <button v-for="v in [15, 25, 40, 60]" :key="v" class="chip-btn" :class="{ active: custom.max_rounds === v }" @click="custom.max_rounds = v">{{ v }}</button>
            </div>
          </div>

          <!-- Entity type limit -->
          <div class="config-field">
            <label>Entity type limit</label>
            <div class="chip-group">
              <button v-for="v in [10, 15, 20, 30]" :key="v" class="chip-btn" :class="{ active: custom.entity_type_limit === v }" @click="custom.entity_type_limit = v">{{ v }}</button>
            </div>
          </div>

          <!-- Deep research -->
          <div class="config-field">
            <label>Deep research <span class="field-hint">Wikipedia + multi-source seeds</span></label>
            <div class="toggle-row">
              <button class="toggle-btn" :class="{ active: custom.deep_research }" @click="custom.deep_research = true">ON</button>
              <button class="toggle-btn" :class="{ active: !custom.deep_research }" @click="custom.deep_research = false">OFF</button>
            </div>
          </div>

          <!-- Agent diversity -->
          <div class="config-field">
            <label>Agent diversity <span class="field-hint">Varied stances &amp; influence</span></label>
            <div class="toggle-row">
              <button class="toggle-btn" :class="{ active: custom.agent_diversity }" @click="custom.agent_diversity = true">ON</button>
              <button class="toggle-btn" :class="{ active: !custom.agent_diversity }" @click="custom.agent_diversity = false">OFF</button>
            </div>
          </div>

          <!-- Prediction method -->
          <div class="config-field config-field-wide">
            <label>Prediction method</label>
            <div class="mode-toggle">
              <label class="mode-option" :class="{ active: custom.prediction_method === 'combined' }">
                <input type="radio" v-model="custom.prediction_method" value="combined" />
                Combined (LLM+Quant)
              </label>
              <label class="mode-option" :class="{ active: custom.prediction_method === 'llm_only' }">
                <input type="radio" v-model="custom.prediction_method" value="llm_only" />
                LLM Only
              </label>
              <label class="mode-option" :class="{ active: custom.prediction_method === 'quant_only' }">
                <input type="radio" v-model="custom.prediction_method" value="quant_only" />
                Quantitative Only
              </label>
            </div>
          </div>

          <!-- LLM / Quant weight -->
          <div class="config-field config-field-wide">
            <label>LLM weight / Quant weight <span class="field-hint">Auto-learned: {{ (methodWeights.llm_weight * 100).toFixed(0) }}% / {{ (methodWeights.quant_weight * 100).toFixed(0) }}%</span></label>
            <div class="slider-row">
              <span class="slider-label">LLM {{ (custom.llm_weight_override * 100).toFixed(0) }}%</span>
              <input type="range" v-model.number="custom.llm_weight_override" min="0" max="1" step="0.05" class="slider" />
              <span class="slider-label">Quant {{ ((1 - custom.llm_weight_override) * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         Section 4: Trading Engine
         ============================================================ -->
    <section class="section">
      <div class="section-header" @click="sections.trading = !sections.trading">
        <span class="dot"></span>
        <h2>TRADING ENGINE</h2>
        <span class="tip-wrap tip-below tip-left">
          <span class="help-icon" @click.stop>&#9432;</span>
          <span class="tip-content">Configure how the trading engine sizes bets, manages risk, and allocates capital.</span>
        </span>
        <span class="collapse-arrow">{{ sections.trading ? '\u25BC' : '\u25B6' }}</span>
      </div>
      <div v-show="sections.trading" class="section-body">
        <div class="config-grid">
          <!-- Mode -->
          <div class="config-field config-field-wide">
            <label>Mode</label>
            <div class="mode-toggle">
              <label class="mode-option" :class="{ active: custom.engine_mode === 'quick' }">
                <input type="radio" v-model="custom.engine_mode" value="quick" />
                Quick
                <span class="mode-desc">scan &rarr; predict &rarr; bet (free)</span>
              </label>
              <label class="mode-option" :class="{ active: custom.engine_mode === 'autopilot' }">
                <input type="radio" v-model="custom.engine_mode" value="autopilot" />
                Autopilot
                <span class="mode-desc">scan &rarr; deep &rarr; bet (~$12/cycle)</span>
              </label>
            </div>
          </div>

          <!-- Min edge for bet -->
          <div class="config-field">
            <label>Min edge for bet</label>
            <div class="stepper">
              <button class="stepper-btn" @click="autopilot.min_edge_for_bet = Math.max(0, round2(autopilot.min_edge_for_bet - 0.01))">-</button>
              <input type="number" v-model.number="autopilot.min_edge_for_bet" min="0" max="0.5" step="0.01" class="stepper-input" />
              <button class="stepper-btn" @click="autopilot.min_edge_for_bet = Math.min(0.5, round2(autopilot.min_edge_for_bet + 0.01))">+</button>
              <span class="stepper-suffix">{{ (autopilot.min_edge_for_bet * 100).toFixed(0) }}%</span>
            </div>
          </div>

          <!-- Min edge for deep -->
          <div class="config-field">
            <label>Min edge for deep</label>
            <div class="stepper">
              <button class="stepper-btn" @click="autopilot.min_edge_for_deep = Math.max(0, round2(autopilot.min_edge_for_deep - 0.01))">-</button>
              <input type="number" v-model.number="autopilot.min_edge_for_deep" min="0" max="0.5" step="0.01" class="stepper-input" />
              <button class="stepper-btn" @click="autopilot.min_edge_for_deep = Math.min(0.5, round2(autopilot.min_edge_for_deep + 0.01))">+</button>
              <span class="stepper-suffix">{{ (autopilot.min_edge_for_deep * 100).toFixed(0) }}%</span>
            </div>
          </div>

          <!-- Max deep per cycle -->
          <div class="config-field">
            <label>Max deep per cycle</label>
            <div class="stepper">
              <button class="stepper-btn" @click="autopilot.max_deep_per_cycle = Math.max(0, autopilot.max_deep_per_cycle - 1)">-</button>
              <input type="number" v-model.number="autopilot.max_deep_per_cycle" min="0" max="10" class="stepper-input" />
              <button class="stepper-btn" @click="autopilot.max_deep_per_cycle = Math.min(10, autopilot.max_deep_per_cycle + 1)">+</button>
            </div>
          </div>

          <!-- Max cost per cycle -->
          <div class="config-field">
            <label>Max cost per cycle ($)</label>
            <div class="stepper">
              <button class="stepper-btn" @click="autopilot.max_cost_per_cycle = Math.max(0, autopilot.max_cost_per_cycle - 5)">-</button>
              <span class="stepper-prefix">$</span>
              <input type="number" v-model.number="autopilot.max_cost_per_cycle" min="0" step="5" class="stepper-input" />
              <button class="stepper-btn" @click="autopilot.max_cost_per_cycle = autopilot.max_cost_per_cycle + 5">+</button>
            </div>
          </div>

          <!-- Kelly factor -->
          <div class="config-field">
            <label>Kelly factor</label>
            <div class="chip-group">
              <button v-for="v in [0.10, 0.15, 0.25, 0.50]" :key="v" class="chip-btn" :class="{ active: strategy.kelly_factor === v }" @click="strategy.kelly_factor = v">{{ v }}</button>
            </div>
          </div>

          <!-- Cash reserve -->
          <div class="config-field">
            <label>Cash reserve</label>
            <div class="chip-group">
              <button v-for="v in [0.10, 0.15, 0.20, 0.25, 0.30]" :key="v" class="chip-btn" :class="{ active: custom.cash_reserve === v }" @click="custom.cash_reserve = v">{{ (v * 100).toFixed(0) }}%</button>
            </div>
          </div>

          <!-- Max sector exposure -->
          <div class="config-field">
            <label>Max sector exposure</label>
            <div class="chip-group">
              <button v-for="v in [0.20, 0.30, 0.40, 0.50]" :key="v" class="chip-btn" :class="{ active: custom.max_sector_exposure === v }" @click="custom.max_sector_exposure = v">{{ (v * 100).toFixed(0) }}%</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================================
         Section 5: API Keys Status
         ============================================================ -->
    <section class="section">
      <div class="section-header" @click="sections.apikeys = !sections.apikeys">
        <span class="dot"></span>
        <h2>API KEYS STATUS</h2>
        <span class="tip-wrap tip-below tip-left">
          <span class="help-icon" @click.stop>&#9432;</span>
          <span class="tip-content">Shows whether each API key is configured in your .env file. Keys are never displayed.</span>
        </span>
        <span class="collapse-arrow">{{ sections.apikeys ? '\u25BC' : '\u25B6' }}</span>
      </div>
      <div v-show="sections.apikeys" class="section-body">
        <div class="api-keys-grid">
          <div v-for="(configured, name) in apiKeys" :key="name" class="api-key-row">
            <span class="api-key-status" :class="configured ? 'status-ok' : 'status-missing'">
              {{ configured ? '\u2705' : '\u274C' }}
            </span>
            <span class="api-key-name">{{ apiKeyLabels[name] || name }}</span>
            <span class="api-key-state">{{ configured ? 'Configured' : 'Missing' }}</span>
          </div>
        </div>
        <p class="env-hint">
          API keys are read from environment variables. Edit your <code>.env</code> file in the project root to add or change keys.
        </p>
      </div>
    </section>

    <!-- Bottom actions -->
    <div class="bottom-actions">
      <button class="btn btn-outline" @click="resetToDefaults">Reset to Defaults</button>
      <button class="btn btn-primary" @click="saveAll" :disabled="saving">
        {{ saving ? 'Saving...' : 'Save All' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'

// ---- State ----
const loading = ref(true)
const saving = ref(false)
const toast = reactive({ show: false, msg: '', type: 'success' })

const sections = reactive({
  pipeline: true,
  market: true,
  simulation: true,
  trading: true,
  apikeys: true,
})

const selectedPreset = ref('balanced')
const presets = ref({})
const presetDescriptions = {
  balanced: 'DeepSeek prep + Gemini profiles + GPT-4o sim/report',
  budget: 'DeepSeek prep + GPT-4o-mini sim/report',
  premium: 'DeepSeek prep + Claude sim + GPT-4o report',
  cheapest: 'All DeepSeek',
  best: 'All GPT-4o',
  gemini: 'All Gemini 2.5 Flash',
  local: 'All Ollama local (free)',
  hybrid_local: 'Local prep + GPT-4o report',
}
const presetCosts = {
  balanced: '0.42',
  budget: '0.03',
  premium: '0.54',
  cheapest: '0.02',
  best: '0.58',
  gemini: '0.03',
  local: '0.00',
  hybrid_local: '0.12',
}

const allCategories = [
  'Geopolitics', 'Politics', 'Science', 'Business', 'Crypto', 'Culture', 'Sports', 'Other'
]
const marketCategories = ref([...allCategories])

const autopilot = reactive({
  max_deep_per_cycle: 3,
  max_cost_per_cycle: 15,
  min_edge_for_deep: 0.05,
  min_edge_for_bet: 0.03,
  cycle_interval_hours: 6,
  niche_focus: true,
  quick_research: false,
  max_markets_to_scan: 50,
  days_ahead: 7,
  min_volume: 500,
  cost_per_deep: 4.0,
})

const strategy = reactive({
  kelly_factor: 0.25,
  odds_range: [0.10, 0.90],
  max_bet_pct: 0.05,
  min_edge_threshold: 0.03,
  category_weights: {},
})

const methodWeights = reactive({ llm_weight: 0.5, quant_weight: 0.5 })

const custom = reactive({
  max_rounds: 40,
  entity_type_limit: 20,
  deep_research: true,
  agent_diversity: true,
  prediction_method: 'combined',
  llm_weight_override: 0.5,
  engine_mode: 'quick',
  cash_reserve: 0.20,
  max_sector_exposure: 0.40,
  excluded_slugs: '',
  target_slugs: '',
})

const apiKeys = ref({})
const apiKeyLabels = {
  openai: 'OpenAI',
  deepseek: 'DeepSeek',
  gemini: 'Gemini',
  anthropic: 'Anthropic',
  ollama: 'Ollama (Local)',
  zep: 'Zep (Memory)',
}

// ---- Helpers ----
const round2 = (v) => Math.round(v * 100) / 100

function showToast(msg, type = 'success') {
  toast.msg = msg
  toast.type = type
  toast.show = true
  setTimeout(() => { toast.show = false }, 3000)
}

// ---- API ----
async function fetchSettings() {
  loading.value = true
  try {
    const res = await fetch('/api/polymarket/settings')
    const json = await res.json()
    if (json.success && json.data) {
      const d = json.data

      // Autopilot
      if (d.autopilot) Object.assign(autopilot, d.autopilot)

      // Pipeline preset
      if (d.pipeline_preset) selectedPreset.value = d.pipeline_preset
      if (d.presets) presets.value = d.presets

      // Strategy
      if (d.strategy) {
        Object.assign(strategy, {
          kelly_factor: d.strategy.kelly_factor ?? 0.25,
          odds_range: d.strategy.odds_range ?? [0.10, 0.90],
          max_bet_pct: d.strategy.max_bet_pct ?? 0.05,
          min_edge_threshold: d.strategy.min_edge_threshold ?? 0.03,
          category_weights: d.strategy.category_weights ?? {},
        })
      }

      // Method weights
      if (d.method_weights) Object.assign(methodWeights, d.method_weights)

      // Custom
      if (d.custom) {
        Object.assign(custom, {
          max_rounds: d.custom.max_rounds ?? 40,
          entity_type_limit: d.custom.entity_type_limit ?? 20,
          deep_research: d.custom.deep_research ?? true,
          agent_diversity: d.custom.agent_diversity ?? true,
          prediction_method: d.custom.prediction_method ?? 'combined',
          llm_weight_override: d.custom.llm_weight_override ?? methodWeights.llm_weight,
          engine_mode: d.custom.engine_mode ?? 'quick',
          cash_reserve: d.custom.cash_reserve ?? 0.20,
          max_sector_exposure: d.custom.max_sector_exposure ?? 0.40,
          excluded_slugs: d.custom.excluded_slugs ?? '',
          target_slugs: d.custom.target_slugs ?? '',
        })
        if (d.custom.market_categories) marketCategories.value = d.custom.market_categories
      } else {
        // If no custom saved yet, seed llm_weight_override from auto-learned
        custom.llm_weight_override = methodWeights.llm_weight
      }

      // API keys
      if (d.api_keys) apiKeys.value = d.api_keys
    }
  } catch (e) {
    console.error('Failed to fetch settings', e)
    showToast('Failed to load settings', 'error')
  } finally {
    loading.value = false
  }
}

async function saveAll() {
  saving.value = true
  try {
    const body = {
      autopilot: { ...autopilot },
      strategy: {
        kelly_factor: strategy.kelly_factor,
        odds_range: strategy.odds_range,
        max_bet_pct: strategy.max_bet_pct,
        min_edge_threshold: strategy.min_edge_threshold,
      },
      custom: {
        ...custom,
        pipeline_preset: selectedPreset.value,
        market_categories: marketCategories.value,
      },
    }
    const res = await fetch('/api/polymarket/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const json = await res.json()
    if (json.success) {
      showToast('Settings saved successfully')
    } else {
      showToast('Save failed: ' + (json.errors?.join(', ') || json.error || 'Unknown error'), 'error')
    }
  } catch (e) {
    console.error('Save failed', e)
    showToast('Save failed: network error', 'error')
  } finally {
    saving.value = false
  }
}

function resetToDefaults() {
  selectedPreset.value = 'balanced'
  marketCategories.value = [...allCategories]
  Object.assign(autopilot, {
    max_deep_per_cycle: 3,
    max_cost_per_cycle: 15,
    min_edge_for_deep: 0.05,
    min_edge_for_bet: 0.03,
    cycle_interval_hours: 6,
    niche_focus: true,
    quick_research: false,
    max_markets_to_scan: 50,
    days_ahead: 7,
    min_volume: 500,
    cost_per_deep: 4.0,
  })
  Object.assign(strategy, {
    kelly_factor: 0.25,
    odds_range: [0.10, 0.90],
    max_bet_pct: 0.05,
    min_edge_threshold: 0.03,
  })
  Object.assign(custom, {
    max_rounds: 40,
    entity_type_limit: 20,
    deep_research: true,
    agent_diversity: true,
    prediction_method: 'combined',
    llm_weight_override: 0.5,
    engine_mode: 'quick',
    cash_reserve: 0.20,
    max_sector_exposure: 0.40,
    excluded_slugs: '',
    target_slugs: '',
  })
  showToast('Reset to defaults — click Save All to persist')
}

onMounted(() => {
  fetchSettings()
})
</script>

<style scoped>
/* ========================================
   Settings Page — PolFish Design System
   ======================================== */
.settings-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px 120px;
  font-family: 'Space Grotesk', 'JetBrains Mono', monospace;
  color: #000000;
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 32px;
  gap: 16px;
  flex-wrap: wrap;
}

.header h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
}

.subtitle {
  display: block;
  font-size: 14px;
  color: #888888;
  margin-top: 4px;
}

.header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

/* Buttons */
.btn {
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
  font-family: 'Space Grotesk', sans-serif;
  letter-spacing: 0.3px;
}

.btn-primary {
  background: #1a1a1a;
  color: #ffffff;
}

.btn-primary:hover:not(:disabled) {
  background: #333;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline {
  background: transparent;
  color: #1a1a1a;
  border: 1.5px solid #d0d0d0;
}

.btn-outline:hover {
  border-color: #999;
  background: #f8f8f8;
}

/* Toast */
.toast {
  position: fixed;
  top: 72px;
  right: 24px;
  padding: 12px 24px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  z-index: 9999;
  font-family: 'Space Grotesk', sans-serif;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}

.toast-success {
  background: #1a1a1a;
  color: #4ade80;
}

.toast-error {
  background: #1a1a1a;
  color: #f87171;
}

.toast-enter-active, .toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}

/* Sections */
.section {
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  margin-bottom: 20px;
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
  transition: background 0.1s;
}

.section-header:hover {
  background: #fafafa;
}

.section-header h2 {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1.5px;
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #000000;
  flex-shrink: 0;
}

.collapse-arrow {
  margin-left: auto;
  font-size: 10px;
  color: #888;
}

.section-body {
  padding: 0 20px 20px;
}

/* Config Grid */
.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-field-wide {
  grid-column: 1 / -1;
}

.config-field label {
  font-size: 13px;
  font-weight: 600;
  color: #333;
  font-family: 'Space Grotesk', sans-serif;
}

.field-hint {
  font-weight: 400;
  color: #999;
  font-size: 11px;
  margin-left: 4px;
}

/* Stepper */
.stepper {
  display: flex;
  align-items: center;
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
  width: fit-content;
}

.stepper-sm {
  font-size: 12px;
}

.stepper-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: #f5f5f5;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  color: #333;
  transition: background 0.1s;
}

.stepper-btn:hover {
  background: #e0e0e0;
}

.stepper-btn:active {
  background: #d0d0d0;
}

.stepper-input {
  width: 60px;
  text-align: center;
  border: none;
  outline: none;
  font-size: 14px;
  font-family: 'JetBrains Mono', monospace;
  padding: 0 4px;
  -moz-appearance: textfield;
}

.stepper-input::-webkit-inner-spin-button,
.stepper-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.stepper-prefix, .stepper-suffix {
  padding: 0 8px;
  font-size: 12px;
  font-family: 'Space Grotesk', sans-serif;
  color: #888;
}

.stepper-prefix {
  border-right: 1px solid #eee;
}

/* Range row */
.range-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.range-sep {
  font-size: 12px;
  color: #999;
}

/* Chip group */
.chip-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chip-btn {
  padding: 6px 14px;
  border-radius: 4px;
  border: 1px solid #e5e5e5;
  background: #fff;
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  transition: all 0.1s;
}

.chip-btn:hover {
  border-color: #999;
}

.chip-btn.active {
  background: #1a1a1a;
  color: #fff;
  border-color: #1a1a1a;
}

/* Toggle */
.toggle-row {
  display: flex;
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  overflow: hidden;
  width: fit-content;
}

.toggle-btn {
  padding: 8px 20px;
  border: none;
  background: #fff;
  font-size: 13px;
  font-family: 'Space Grotesk', sans-serif;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.1s;
}

.toggle-btn:first-child {
  border-right: 1px solid #e5e5e5;
}

.toggle-btn.active {
  background: #1a1a1a;
  color: #fff;
}

.toggle-btn:not(.active):hover {
  background: #f5f5f5;
}

/* Mode toggle */
.mode-toggle {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.mode-option {
  flex: 1;
  min-width: 180px;
  padding: 12px 16px;
  border: 1.5px solid #e5e5e5;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.15s;
  font-family: 'Space Grotesk', sans-serif;
}

.mode-option input[type="radio"] {
  display: none;
}

.mode-option.active {
  border-color: #1a1a1a;
  background: #f8f8f8;
}

.mode-option:hover {
  border-color: #999;
}

.mode-desc {
  font-size: 11px;
  font-weight: 400;
  color: #999;
}

/* Checkbox group */
.checkbox-group {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  font-family: 'Space Grotesk', sans-serif;
}

.checkbox-label input[type="checkbox"] {
  accent-color: #1a1a1a;
}

/* Text area */
.text-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
}

.text-input:focus {
  border-color: #999;
}

/* Slider */
.slider-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider-label {
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: #666;
  white-space: nowrap;
  min-width: 80px;
}

.slider {
  flex: 1;
  -webkit-appearance: none;
  height: 6px;
  border-radius: 3px;
  background: #e5e5e5;
  outline: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #1a1a1a;
  cursor: pointer;
}

/* Preset Grid */
.preset-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.preset-card {
  padding: 16px;
  border: 1.5px solid #e5e5e5;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: all 0.15s;
}

.preset-card input[type="radio"] {
  display: none;
}

.preset-card:hover {
  border-color: #999;
}

.preset-card.active {
  border-color: #1a1a1a;
  background: #f8f8f8;
  box-shadow: 0 0 0 1px #1a1a1a;
}

.preset-name {
  font-size: 16px;
  font-weight: 700;
  text-transform: capitalize;
  font-family: 'JetBrains Mono', monospace;
}

.preset-desc {
  font-size: 11px;
  color: #888;
  line-height: 1.4;
}

.preset-cost {
  font-size: 13px;
  font-weight: 700;
  color: #FF4500;
  font-family: 'JetBrains Mono', monospace;
}

.preset-stages {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}

.preset-stage {
  font-size: 10px;
  color: #999;
  font-family: 'JetBrains Mono', monospace;
}

.preset-stage strong {
  color: #555;
}

/* API Keys */
.api-keys-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.api-key-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #eee;
}

.api-key-status {
  font-size: 16px;
  width: 24px;
  text-align: center;
}

.api-key-name {
  font-size: 14px;
  font-weight: 600;
  font-family: 'Space Grotesk', sans-serif;
  flex: 1;
}

.api-key-state {
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
}

.status-ok .api-key-state,
.api-key-row:has(.status-ok) .api-key-state {
  color: #22c55e;
}

.status-missing .api-key-state,
.api-key-row:has(.status-missing) .api-key-state {
  color: #ef4444;
}

.env-hint {
  margin-top: 12px;
  font-size: 12px;
  color: #999;
}

.env-hint code {
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
}

/* Tooltip — same as other pages */
.tip-wrap {
  position: relative;
  display: inline-flex;
}

.help-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 12px;
  color: #aaa;
  cursor: help;
  transition: color 0.15s;
}

.help-icon:hover {
  color: #FF4500;
}

.tip-content {
  display: none;
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  top: 100%;
  margin-top: 8px;
  width: 260px;
  padding: 12px 14px;
  background: #1a1a1a;
  color: #ccc;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  z-index: 100;
  font-weight: 400;
  box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}

.tip-wrap:hover .tip-content {
  display: block;
}

.tip-left .tip-content {
  left: 0;
  transform: none;
}

/* Bottom Actions */
.bottom-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 24px 0;
  border-top: 1px solid #e5e5e5;
  margin-top: 12px;
}

/* Responsive */
@media (max-width: 768px) {
  .settings-page {
    padding: 20px 16px 120px;
  }

  .config-grid {
    grid-template-columns: 1fr;
  }

  .preset-grid {
    grid-template-columns: 1fr;
  }

  .header {
    flex-direction: column;
  }

  .header-right {
    width: 100%;
    justify-content: flex-end;
  }

  .range-row {
    flex-wrap: wrap;
  }
}
</style>
