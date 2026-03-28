<template>
  <div class="paper-trading">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1>Trade <span class="paper-mode-badge">PAPER</span> <span class="help-icon" @click.stop="showInfo = true">ⓘ</span></h1>
        <span class="subtitle">Automated prediction testing &amp; self-optimization</span>
      </div>
      <div class="header-right">
        <div class="balance-card">
          <span class="balance-label">Portfolio Value</span>
          <span class="balance-value">${{ Number(portfolioValue).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) }}</span>
          <button class="reset-portfolio-btn" @click="resetPortfolio" title="Reset to $10,000">↺ Reset</button>
        </div>
      </div>
    </header>

    <!-- TRADING ENGINE -->
    <section class="engine-section">
      <div class="section-header">
        <span class="dot"></span>
        <h2>TRADING ENGINE</h2>
        <span v-if="engineMode === 'quick'" class="mode-badge mode-badge-info">Quick</span>
        <span v-else class="mode-badge mode-badge-warn">Autopilot</span>
        <span class="tip-wrap tip-below tip-left">
          <span class="help-icon">ⓘ</span>
          <span class="tip-content"><strong>{{ engineMode === 'quick' ? 'Quick' : 'Autopilot' }} mode active.</strong><br/>{{ engineMode === 'quick' ? 'Scans markets, predicts using market odds + noise, bets on edge. Free but no real alpha — good for testing the system.' : 'Scans markets, ranks by edge, runs deep MiroFish simulation on top candidates (~$4/market), confirms or rejects, then places bets. Real predictions using OpenAI API.' }}<br/><span class="tip-link-text" @click.stop="showInfo = true">Read More</span></span>
        </span>
      </div>

      <!-- Mode + Configure row -->
      <div class="engine-controls">
        <div class="mode-toggle">
          <label class="mode-option" :class="{ active: engineMode === 'quick' }">
            <input type="radio" v-model="engineMode" value="quick" />
            Quick
            <span class="mode-desc">scan &rarr; predict &rarr; bet (free)</span>
          </label>
          <label class="mode-option" :class="{ active: engineMode === 'autopilot' }">
            <input type="radio" v-model="engineMode" value="autopilot" />
            Autopilot
            <span class="mode-desc">scan &rarr; deep &rarr; bet (~$12/cycle)</span>
          </label>
        </div>

        <button class="btn btn-outline btn-configure" @click="showConfig = !showConfig">
          <span style="font-size:27px;line-height:1">&#9881;</span> Configure
        </button>
      </div>

      <!-- Run button row -->
      <div class="engine-run-row">
        <button class="btn btn-primary" @click="runCycle" :disabled="cycleRunning">
          {{ cycleRunning ? 'Running...' : '\u25B6 Run Cycle' }}
        </button>
        <span class="engine-status" v-if="lastCycleResult">
          Last run: {{ formatTime(lastCycleResult.started_at) }} &middot;
          {{ lastCycleResult.scanned }} scanned &middot;
          {{ lastCycleResult.predicted }} predicted &middot;
          {{ lastCycleResult.bets_placed }} bets
        </span>
        <span class="engine-status" v-else>
          Idle
        </span>
      </div>

      <!-- Config drawer -->
      <teleport to="body">
        <div v-if="showConfig" class="config-drawer-overlay" @click.self="showConfig = false">
          <div class="config-drawer">
            <div class="config-drawer-header">
              <h3>Engine Configuration</h3>
              <button class="config-drawer-close" @click="showConfig = false">&times;</button>
            </div>
            <div class="config-grid">
              <!-- Max deep per cycle -->
              <div class="config-field" :class="{ 'config-disabled': engineMode === 'quick' }">
                <label>Max deep per cycle <span v-if="engineMode === 'quick'" class="config-mode-tag">Autopilot only</span><span class="tip-wrap tip-below tip-left"><span class="help-icon">ⓘ</span><span class="tip-content"><strong>How many markets get deep analysis per cycle.</strong><br/><br/>Each deep prediction runs a full MiroFish agent simulation and costs ~$4 in OpenAI API tokens.<br/><br/>Range: 0–10<br/>Recommended: 3</span></span></label>
                <div class="stepper">
                  <button class="stepper-btn" :disabled="engineMode === 'quick'" @click="config.max_deep_per_cycle = Math.max(0, (config.max_deep_per_cycle || 0) - 1)">−</button>
                  <input type="number" v-model.number="config.max_deep_per_cycle" min="0" max="10" class="stepper-input" :disabled="engineMode === 'quick'" />
                  <button class="stepper-btn" :disabled="engineMode === 'quick'" @click="config.max_deep_per_cycle = Math.min(10, (config.max_deep_per_cycle || 0) + 1)">+</button>
                </div>
              </div>

              <!-- Max cost per cycle -->
              <div class="config-field" :class="{ 'config-disabled': engineMode === 'quick' }">
                <label>Max cost per cycle <span v-if="engineMode === 'quick'" class="config-mode-tag">Autopilot only</span><span class="tip-wrap tip-below tip-left"><span class="help-icon">ⓘ</span><span class="tip-content"><strong>Budget cap for API costs per cycle.</strong><br/><br/>The engine stops running deep predictions once this limit is reached, even if more candidates remain.<br/><br/>Calculated as: max_deep × ~$4/prediction<br/>Recommended: $15</span></span></label>
                <div class="stepper">
                  <button class="stepper-btn" :disabled="engineMode === 'quick'" @click="config.max_cost_per_cycle = Math.max(0, (config.max_cost_per_cycle || 0) - 5)">−</button>
                  <span class="stepper-prefix">$</span>
                  <input type="number" v-model.number="config.max_cost_per_cycle" min="0" step="5" class="stepper-input" :disabled="engineMode === 'quick'" />
                  <button class="stepper-btn" :disabled="engineMode === 'quick'" @click="config.max_cost_per_cycle = (config.max_cost_per_cycle || 0) + 5">+</button>
                </div>
              </div>

              <!-- Min edge for deep -->
              <div class="config-field" :class="{ 'config-disabled': engineMode === 'quick' }">
                <label>Min edge for deep <span v-if="engineMode === 'quick'" class="config-mode-tag">Autopilot only</span><span class="tip-wrap tip-below tip-left"><span class="help-icon">ⓘ</span><span class="tip-content"><strong>Minimum edge before spending tokens on deep analysis.</strong><br/><br/>Edge = |your prediction − market odds|<br/><br/>Quick scan finds candidates, but only those with edge above this threshold get expensive deep analysis.<br/><br/>Higher = fewer deep runs, but higher quality.<br/>Recommended: 5% (0.05)</span></span></label>
                <div class="stepper">
                  <button class="stepper-btn" :disabled="engineMode === 'quick'" @click="config.min_edge_for_deep = Math.max(0, Math.round(((config.min_edge_for_deep || 0) - 0.01) * 100) / 100)">−</button>
                  <input type="number" v-model.number="config.min_edge_for_deep" min="0" max="0.5" step="0.01" class="stepper-input" :disabled="engineMode === 'quick'" />
                  <button class="stepper-btn" :disabled="engineMode === 'quick'" @click="config.min_edge_for_deep = Math.min(0.5, Math.round(((config.min_edge_for_deep || 0) + 0.01) * 100) / 100)">+</button>
                  <span class="stepper-suffix">{{ ((config.min_edge_for_deep || 0) * 100).toFixed(0) }}%</span>
                </div>
              </div>

              <!-- Min edge for bet -->
              <div class="config-field">
                <label>Min edge for bet <span class="tip-wrap tip-below tip-left"><span class="help-icon">ⓘ</span><span class="tip-content"><strong>Minimum edge required to place a paper bet.</strong><br/><br/>After deep analysis confirms or updates the prediction, the final edge must exceed this to trigger a bet.<br/><br/>Lower = more bets but riskier.<br/>Higher = fewer bets but higher conviction.<br/>Recommended: 3–5% (0.03–0.05)</span></span></label>
                <div class="stepper">
                  <button class="stepper-btn" @click="config.min_edge_for_bet = Math.max(0, Math.round(((config.min_edge_for_bet || 0) - 0.01) * 100) / 100)">−</button>
                  <input type="number" v-model.number="config.min_edge_for_bet" min="0" max="0.5" step="0.01" class="stepper-input" />
                  <button class="stepper-btn" @click="config.min_edge_for_bet = Math.min(0.5, Math.round(((config.min_edge_for_bet || 0) + 0.01) * 100) / 100)">+</button>
                  <span class="stepper-suffix">{{ ((config.min_edge_for_bet || 0) * 100).toFixed(0) }}%</span>
                </div>
              </div>

              <!-- Time window -->
              <div class="config-field">
                <label>Time window <span class="tip-wrap tip-below tip-left"><span class="help-icon">ⓘ</span><span class="tip-content"><strong>How far out to look for expiring markets.</strong><br/><br/>Supports fractions for short-term trading:<br/>0.25 = 6 hours, 0.5 = 12 hours, 1 = 24 hours<br/><br/>Shorter = faster feedback for optimizer.<br/>Longer = more candidates to choose from.<br/><br/>Recommended: 1–7 days. For testing: 0.25–1 day</span></span></label>
                <div class="stepper">
                  <button class="stepper-btn" @click="config.days_ahead = Math.max(0.1, Math.round(((config.days_ahead || 1) - 0.25) * 100) / 100)">−</button>
                  <input type="number" v-model.number="config.days_ahead" min="0.1" max="30" step="0.25" class="stepper-input" />
                  <button class="stepper-btn" @click="config.days_ahead = Math.min(30, Math.round(((config.days_ahead || 1) + 0.25) * 100) / 100)">+</button>
                  <span class="stepper-suffix">{{ config.days_ahead < 1 ? (config.days_ahead * 24).toFixed(0) + 'h' : config.days_ahead + 'd' }}</span>
                </div>
              </div>

              <!-- Min volume -->
              <div class="config-field">
                <label>Min volume <span class="tip-wrap tip-below tip-left"><span class="help-icon">ⓘ</span><span class="tip-content"><strong>Minimum trading volume to consider a market.</strong><br/><br/>Low-volume markets have unreliable odds — few traders means the price may not reflect reality.<br/><br/>Higher = more reliable odds but fewer markets.<br/>Recommended: $500–$1,000</span></span></label>
                <div class="chip-group">
                  <button v-for="v in [100, 500, 1000, 2500, 5000, 10000]" :key="v" class="chip-btn" :class="{ active: config.min_volume === v }" @click="config.min_volume = v">${{ v >= 1000 ? (v/1000) + 'K' : v }}</button>
                </div>
              </div>

              <!-- Quick mode research -->
              <div class="config-field" :class="{ 'config-disabled': engineMode === 'autopilot' }">
                <label>Quick mode research <span v-if="engineMode === 'autopilot'" class="config-mode-tag">Quick only</span><span class="tip-wrap tip-below tip-left"><span class="help-icon">ⓘ</span><span class="tip-content"><strong>Fetch news articles in Quick mode.</strong><br/><br/><strong>OFF:</strong> Instant — uses market odds + noise. Free, no API calls. Good for testing plumbing.<br/><br/><strong>ON:</strong> Fetches 3–5 news articles per market and builds a seed document. Still uses odds + noise for the prediction, but the research data is logged for review.<br/><br/>~2–3 sec/market, no API cost (DuckDuckGo).</span></span></label>
                <div class="toggle-row">
                  <button class="toggle-btn" :class="{ active: config.quick_research }" @click="config.quick_research = true">ON</button>
                  <button class="toggle-btn" :class="{ active: !config.quick_research }" @click="config.quick_research = false">OFF</button>
                </div>
              </div>

              <!-- Niche focus -->
              <div class="config-field">
                <label>Niche focus <span class="tip-wrap tip-below tip-left"><span class="help-icon">ⓘ</span><span class="tip-content"><strong>Prioritize obscure, less-traded markets.</strong><br/><br/>Niche markets (science, obscure politics, culture) tend to have fewer informed traders — meaning more potential edge for MiroFish's simulations.<br/><br/>Mainstream markets (US elections, BTC price) are heavily traded and harder to beat.</span></span></label>
                <div class="toggle-row">
                  <button class="toggle-btn" :class="{ active: config.niche_focus }" @click="config.niche_focus = true">ON</button>
                  <button class="toggle-btn" :class="{ active: !config.niche_focus }" @click="config.niche_focus = false">OFF</button>
                </div>
              </div>

              <!-- Auto-loop interval -->
              <div class="config-field">
                <label>Auto-loop interval <span class="tip-wrap tip-below tip-left"><span class="help-icon">ⓘ</span><span class="tip-content"><strong>Automatically run a cycle on a schedule.</strong><br/><br/>Set to 0 to disable auto-loop and only run manually.<br/><br/>Each cycle scans for new markets, runs predictions, and places bets.<br/>Recommended: 6 hours</span></span></label>
                <div class="stepper">
                  <button class="stepper-btn" @click="config.cycle_interval_hours = Math.max(0, (config.cycle_interval_hours || 0) - 1)">−</button>
                  <input type="number" v-model.number="config.cycle_interval_hours" min="0" max="24" class="stepper-input" />
                  <button class="stepper-btn" @click="config.cycle_interval_hours = Math.min(24, (config.cycle_interval_hours || 0) + 1)">+</button>
                  <span class="stepper-suffix">{{ config.cycle_interval_hours === 0 ? 'disabled' : 'hours' }}</span>
                </div>
              </div>
            </div>
            <div class="config-actions">
              <button class="btn btn-primary btn-sm" @click="saveConfig">Save</button>
              <button class="btn btn-outline btn-sm" @click="showConfig = false">Cancel</button>
            </div>
          </div>
        </div>
      </teleport>
    </section>

    <!-- Stats Row -->
    <section class="stats-row">
      <div class="stat-card">
        <span class="stat-value">${{ balanceDisplay }}</span>
        <span class="stat-label">Cash Balance <span class="tip-wrap"><span class="help-icon">ⓘ</span><span class="tip-content">Available cash not locked in open positions. Starts at $10,000.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ openCount }}</span>
        <span class="stat-label">Open Positions <span class="tip-wrap"><span class="help-icon">ⓘ</span><span class="tip-content">Bets placed but not yet resolved. Cash is locked until the market closes.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ winRateDisplay }}</span>
        <span class="stat-label">Win Rate <span class="tip-wrap"><span class="help-icon">ⓘ</span><span class="tip-content">Percentage of resolved bets that were correct.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ roiDisplay }}</span>
        <span class="stat-label">ROI <span class="tip-wrap"><span class="help-icon">ⓘ</span><span class="tip-content">Return on investment. Total P&amp;L divided by total amount wagered.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value" :class="pnlClass">{{ pnlDisplay }}</span>
        <span class="stat-label">Total P&amp;L <span class="tip-wrap"><span class="help-icon">ⓘ</span><span class="tip-content">Profit &amp; Loss across all resolved bets.</span></span></span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ perf.total_bets || 0 }}</span>
        <span class="stat-label">Total Bets</span>
      </div>
    </section>

    <!-- Open Positions -->
    <section class="section">
      <h2 class="section-title">
        <span class="dot"></span> Open Positions
        <span class="count">{{ openPositions.length }}</span>
      </h2>
      <div v-if="openPositions.length === 0" class="empty">No open positions yet. Run a cycle to start.</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>Market</th>
            <th>Odds</th>
            <th>Prediction</th>
            <th>Side</th>
            <th>Bet</th>
            <th>Outcome</th>
            <th>P&amp;L</th>
            <th>Closes</th>
            <th>Placed</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="pos in openPositions" :key="pos.market_id">
            <td class="market-cell">
              <a
                v-if="pos.slug"
                :href="'https://polymarket.com/market/' + pos.slug"
                target="_blank"
                rel="noopener noreferrer"
                class="market-link"
              >{{ pos.question || pos.slug || pos.market_id }}</a>
              <span v-else>{{ pos.question || pos.market_id }}</span>
            </td>
            <td>{{ ((pos.odds || 0) * 100).toFixed(1) }}%</td>
            <td>{{ pos.prediction ? ((pos.prediction) * 100).toFixed(1) + '%' : '--' }}</td>
            <td><span class="side-badge" :class="pos.side === 'YES' ? 'side-yes' : 'side-no'">{{ pos.side }}</span></td>
            <td class="amount-cell">
              ${{ (pos.amount || 0).toFixed(2) }}
              <span class="tip-wrap tip-below">
                <span class="help-icon" style="font-size:14px;width:16px;height:16px">ⓘ</span>
                <span class="tip-content bet-tip">
                  <span class="bt-row"><span class="bt-key">Edge</span><span class="bt-val">{{ pos.edge ? (pos.edge * 100).toFixed(1) + '%' : '--' }}</span></span>
                  <span class="bt-row"><span class="bt-key">Kelly</span><span class="bt-val">{{ pos.kelly_fraction != null ? pos.kelly_fraction.toFixed(2) : '--' }}</span></span>
                  <span class="bt-row"><span class="bt-key">Confidence</span><span class="bt-val">{{ pos.confidence || '--' }}</span></span>
                  <span class="bt-row"><span class="bt-key">Mode</span><span class="bt-val">{{ pos.mode || 'quick' }}</span></span>
                  <span class="bt-row"><span class="bt-key">Max bet</span><span class="bt-val">{{ pos.max_bet_pct ? (pos.max_bet_pct * 100).toFixed(0) + '%' : '5%' }} of balance</span></span>
                  <span class="bt-row" v-if="pos.cost_usd > 0 || pos.mode === 'deep'"><span class="bt-key">API Cost</span><span class="bt-val" style="color:#FF4500">{{ pos.cost_usd ? '$' + pos.cost_usd.toFixed(2) : '~$2.70 est' }}</span></span>
                </span>
              </span>
            </td>
            <td><span class="outcome-pending">Pending</span></td>
            <td class="pnl-pending">--</td>
            <td :class="closesClass(pos.closes_at)"><span class="tip-wrap"><span>{{ formatCloses(pos.closes_at) }}</span><span v-if="pos.closes_at" class="tip-content closes-tip">{{ new Date(pos.closes_at).toLocaleString() }}</span></span></td>
            <td class="ts-cell">{{ formatTs(pos.placed_at) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Resolved Positions -->
    <section class="section">
      <h2 class="section-title">
        <span class="dot"></span> Trade History
        <span class="count">{{ resolvedPositions.length }}</span>
      </h2>
      <div v-if="resolvedPositions.length === 0" class="empty">No resolved trades yet.</div>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>Market</th>
            <th>Odds</th>
            <th>Prediction</th>
            <th>Side</th>
            <th>Bet</th>
            <th>Payout</th>
            <th>Outcome</th>
            <th>P&amp;L</th>
            <th>Return</th>
            <th>Placed</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="pos in resolvedPositions" :key="pos.market_id + pos.resolved_at">
            <td class="market-cell">
              <a
                v-if="pos.slug"
                :href="'https://polymarket.com/market/' + pos.slug"
                target="_blank"
                rel="noopener noreferrer"
                class="market-link"
              >{{ pos.question || pos.slug || pos.market_id }}</a>
              <span v-else>{{ pos.question || pos.market_id }}</span>
            </td>
            <td>{{ ((pos.odds || 0) * 100).toFixed(1) }}%</td>
            <td>{{ pos.prediction ? ((pos.prediction) * 100).toFixed(1) + '%' : '--' }}</td>
            <td><span class="side-badge" :class="pos.side === 'YES' ? 'side-yes' : 'side-no'">{{ pos.side }}</span></td>
            <td class="amount-cell">
              ${{ (pos.amount || 0).toFixed(2) }}
              <span class="tip-wrap tip-below">
                <span class="help-icon" style="font-size:14px;width:16px;height:16px">ⓘ</span>
                <span class="tip-content bet-tip">
                  <span class="bt-row"><span class="bt-key">Edge</span><span class="bt-val">{{ pos.edge ? (pos.edge * 100).toFixed(1) + '%' : '--' }}</span></span>
                  <span class="bt-row"><span class="bt-key">Kelly</span><span class="bt-val">{{ pos.kelly_fraction != null ? pos.kelly_fraction.toFixed(2) : '--' }}</span></span>
                  <span class="bt-row"><span class="bt-key">Confidence</span><span class="bt-val">{{ pos.confidence || '--' }}</span></span>
                  <span class="bt-row"><span class="bt-key">Mode</span><span class="bt-val">{{ pos.mode || 'quick' }}</span></span>
                  <span class="bt-row"><span class="bt-key">Max bet</span><span class="bt-val">{{ pos.max_bet_pct ? (pos.max_bet_pct * 100).toFixed(0) + '%' : '5%' }} of balance</span></span>
                  <span class="bt-row" v-if="pos.cost_usd > 0 || pos.mode === 'deep'"><span class="bt-key">API Cost</span><span class="bt-val" style="color:#FF4500">{{ pos.cost_usd ? '$' + pos.cost_usd.toFixed(2) : '~$2.70 est' }}</span></span>
                </span>
              </span>
            </td>
            <td :class="(pos.payout || 0) > 0 ? 'pnl-pos' : 'pnl-neg'" style="font-family:'JetBrains Mono',monospace;font-size:13px">
              {{ (pos.payout || 0) > 0 ? '$' + (pos.payout).toFixed(2) : '$0.00' }}
            </td>
            <td>
              <span class="outcome-badge" :class="(pos.pnl || 0) >= 0 ? 'outcome-win' : 'outcome-loss'">
                {{ (pos.pnl || 0) >= 0 ? 'WIN' : 'LOSS' }}
              </span>
            </td>
            <td :class="(pos.pnl || 0) >= 0 ? 'pnl-pos' : 'pnl-neg'" style="font-family:'JetBrains Mono',monospace;font-size:13px">
              {{ (pos.pnl || 0) >= 0 ? '+' : '' }}${{ Math.abs(pos.pnl || 0).toFixed(2) }}
            </td>
            <td :class="(pos.pnl || 0) >= 0 ? 'pnl-pos' : 'pnl-neg'" style="font-family:'JetBrains Mono',monospace;font-size:12px">
              {{ pos.amount > 0 ? ((pos.pnl || 0) >= 0 ? '+' : '') + ((pos.pnl || 0) / pos.amount * 100).toFixed(0) + '%' : '--' }}
            </td>
            <td class="ts-cell">{{ formatTs(pos.placed_at) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Info Modal -->
    <teleport to="body">
      <div v-if="showInfo" class="modal-overlay" @click.self="showInfo = false">
        <div class="modal-content">
          <button class="modal-close" @click="showInfo = false">&#10005;</button>
          <h2 class="modal-title">How Paper Trading Works</h2>
          <p style="font-size:13px;color:#888;margin-top:-8px">For the full engine deep-dive, see <a href="/research/how-it-works" style="color:#FF4500;text-decoration:underline" @click="showInfo = false">How PolFish Thinks</a></p>

          <div class="guide-tabs">
            <button v-for="tab in guideTabs" :key="tab.id" class="guide-tab" :class="{ active: activeGuideTab === tab.id }" @click="activeGuideTab = tab.id">{{ tab.label }}</button>
          </div>

          <div v-if="activeGuideTab === 'overview'" class="guide-body">
            <p>Paper Trading lets you test prediction strategies with simulated money before risking real bets. It scans live Polymarket markets, runs predictions, and places paper bets to measure accuracy over time.</p>
            <h3 class="modal-section-title"><span class="modal-dot"></span> The Loop</h3>
            <ol class="modal-list modal-list-numbered">
              <li><strong>Scan</strong> &mdash; Find expiring markets on Polymarket (filtered by volume, category, odds)</li>
              <li><strong>Predict</strong> &mdash; Run quick or deep MiroFish analysis on each market</li>
              <li><strong>Bet</strong> &mdash; Size bets using Kelly criterion based on edge &amp; confidence</li>
              <li><strong>Resolve</strong> &mdash; Wait for markets to close, check outcomes</li>
              <li><strong>Optimize</strong> &mdash; Calibrate predictions, tune strategy parameters</li>
            </ol>
            <p>Every decision is logged in the <strong>Decision Log</strong> page with full reasoning.</p>
          </div>

          <div v-if="activeGuideTab === 'modes'" class="guide-body">
            <h3 class="modal-section-title"><span class="modal-dot"></span> Mode Comparison</h3>
            <table class="mode-compare-table">
              <thead>
                <tr><th></th><th>Quick</th><th>Deep (Autopilot)</th></tr>
              </thead>
              <tbody>
                <tr><td class="compare-key">Fetch market data</td><td>&#10003;</td><td>&#10003;</td></tr>
                <tr><td class="compare-key">Search news articles</td><td class="compare-no">&#10007;</td><td>&#10003;</td></tr>
                <tr><td class="compare-key">Build seed document</td><td class="compare-no">&#10007;</td><td>&#10003;</td></tr>
                <tr><td class="compare-key">MiroFish graph building</td><td class="compare-no">&#10007;</td><td>&#10003;</td></tr>
                <tr><td class="compare-key">Agent simulation</td><td class="compare-no">&#10007;</td><td>&#10003;</td></tr>
                <tr><td class="compare-key">Report generation</td><td class="compare-no">&#10007;</td><td>&#10003;</td></tr>
                <tr><td class="compare-key">Prediction method</td><td>Odds + noise</td><td>From simulation</td></tr>
                <tr><td class="compare-key">Cost per market</td><td>Free</td><td>~$3&ndash;5</td></tr>
                <tr><td class="compare-key">Time per market</td><td>&lt;1 sec</td><td>5&ndash;10 min</td></tr>
                <tr><td class="compare-key">Real edge?</td><td class="compare-no">No</td><td>Possible</td></tr>
              </tbody>
            </table>

            <h3 class="modal-section-title"><span class="modal-dot"></span> Quick Mode (Free)</h3>
            <p>Uses market odds + small random noise as "predictions." No API cost. Good for testing the pipeline end-to-end.</p>
            <div class="guide-note">Quick mode predictions have no real edge &mdash; win rates will hover around 50%.</div>

            <h3 class="modal-section-title"><span class="modal-dot"></span> Autopilot Mode (~$4/market)</h3>
            <p>Runs full MiroFish deep simulation: builds knowledge graph, creates AI agents, simulates debates, generates reports. This is where real edge comes from.</p>
            <ul class="modal-list">
              <li>Scans markets &rarr; ranks by quick edge &rarr; deep on top N</li>
              <li>Only bets if deep confirms the edge (confirmation gate)</li>
              <li>Budget-capped (configurable via Configure panel)</li>
            </ul>
          </div>

          <div v-if="activeGuideTab === 'portfolio'" class="guide-body">
            <h3 class="modal-section-title"><span class="modal-dot"></span> Portfolio</h3>
            <ul class="modal-list">
              <li><strong>Starting balance:</strong> $10,000 paper money</li>
              <li><strong>Cash Balance:</strong> Available cash not locked in bets</li>
              <li><strong>Open Positions:</strong> Active bets waiting for market resolution</li>
              <li><strong>Trade History:</strong> Resolved bets with actual P&amp;L</li>
            </ul>
            <h3 class="modal-section-title"><span class="modal-dot"></span> Bet Sizing</h3>
            <p>Bets are sized using the <strong>Kelly Criterion</strong> &mdash; a formula that balances risk and reward based on your edge and confidence. The system uses quarter-Kelly by default (conservative). Each bet's amount can be inspected via the ⓘ icon next to the amount.</p>
            <h3 class="modal-section-title"><span class="modal-dot"></span> Closes Column</h3>
            <p>Shows when each market resolves. Color-coded: <span style="color:#e53e3e;font-weight:700">&lt;24h</span> (urgent), <span style="color:#FF4500;font-weight:600">&lt;3 days</span> (soon), <span style="color:#666">later</span>.</p>
          </div>

          <div v-if="activeGuideTab === 'config'" class="guide-body">
            <h3 class="modal-section-title"><span class="modal-dot"></span> Configuration</h3>
            <p>Click <strong>Configure</strong> in the Trading Engine to adjust these settings:</p>
            <ul class="modal-list">
              <li><strong>Max deep per cycle:</strong> How many markets get deep analysis. Each costs ~$4.</li>
              <li><strong>Max cost per cycle:</strong> Budget cap. Won't exceed this per cycle.</li>
              <li><strong>Min edge for deep:</strong> Only spend tokens on deep analysis if quick prediction shows at least this much edge.</li>
              <li><strong>Min edge for bet:</strong> Only place a bet if the confirmed edge exceeds this. Recommended: 3-5%.</li>
              <li><strong>Days ahead:</strong> How far out to look for expiring markets.</li>
              <li><strong>Min volume:</strong> Skip low-volume markets with unreliable odds.</li>
              <li><strong>Niche focus:</strong> Prioritize obscure markets where fewer traders = more edge potential.</li>
              <li><strong>Auto-loop interval:</strong> Run cycles automatically every N hours. Set to 0 for manual only.</li>
            </ul>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Strategy Config -->
    <section class="section collapsible" :class="{ expanded: strategyOpen }">
      <h2 class="section-title clickable" @click="strategyOpen = !strategyOpen">
        <span class="dot"></span> Strategy Config
        <span class="chevron">{{ strategyOpen ? '\u25BC' : '\u25B6' }}</span>
      </h2>
      <div v-if="strategyOpen" class="strategy-grid">
        <div class="config-item" v-for="(val, key) in strategy" :key="key">
          <span class="config-key">{{ key }}</span>
          <span class="config-val">{{ typeof val === 'object' ? JSON.stringify(val) : val }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

// --- State ---
const showInfo = ref(false)
const activeGuideTab = ref('overview')
const guideTabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'modes', label: 'Modes' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'config', label: 'Configuration' },
]
const showConfig = ref(false)
const engineMode = ref('quick')
const perf = ref({})
const openPositions = ref([])
const resolvedPositions = ref([])
const strategy = ref({})
const cycleRunning = ref(false)
const portfolioBalance = ref(10000)
const portfolioValue = ref(10000)
const strategyOpen = ref(false)
const lastCycleResult = ref(null)

// Engine config
const config = ref({
  max_deep_per_cycle: 3,
  max_cost_per_cycle: 15,
  min_edge_for_deep: 0.05,
  min_edge_for_bet: 0.03,
  days_ahead: 7,
  min_volume: 1000,
  niche_focus: true,
  quick_research: false,
  cycle_interval_hours: 6
})

// Tooltip state
const activeTooltip = ref(null)
let tooltipHideTimer = null

let pollInterval = null

// --- Computed ---
const balanceDisplay = computed(() => (portfolioBalance.value || 10000).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
const pnlDisplay = computed(() => {
  const pnl = perf.value.total_pnl || 0
  return (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(2)
})
const pnlClass = computed(() => (perf.value.total_pnl || 0) >= 0 ? 'pnl-pos' : 'pnl-neg')
const winRateDisplay = computed(() => {
  const wr = perf.value.win_rate
  if (wr == null) return '--'
  // Backend returns win_rate already as percentage (e.g., 42.86 means 42.86%)
  return wr.toFixed(1) + '%'
})
const roiDisplay = computed(() => {
  const r = perf.value.roi
  if (r == null) return '--'
  // Backend returns roi already as percentage (e.g., -40.09 means -40.09%)
  return (r >= 0 ? '+' : '') + r.toFixed(1) + '%'
})
const openCount = computed(() => openPositions.value.length)

// --- API ---
const api = async (path, opts = {}) => {
  try {
    const res = await fetch(`/api/polymarket${path}`, opts)
    return await res.json()
  } catch { return { success: false } }
}

const fetchPortfolio = async () => {
  const data = await api('/portfolio')
  if (data.success && data.data) {
    portfolioBalance.value = data.data.balance || 10000
    portfolioValue.value = data.data.total_value || portfolioBalance.value
    openPositions.value = data.data.open_positions || []
    perf.value = data.data.performance || {}
  }
}

const fetchHistory = async () => {
  const data = await api('/portfolio/history')
  if (data.success && data.data) {
    resolvedPositions.value = data.data.resolved || []
  }
}

const fetchStrategy = async () => {
  const data = await api('/strategy')
  if (data.success && data.data) {
    strategy.value = data.data
  }
}

const fetchAll = async () => {
  await Promise.all([fetchPortfolio(), fetchHistory(), fetchStrategy()])
}

// --- Load / Save Config via API ---
const loadConfig = async () => {
  try {
    const data = await api('/autopilot/config')
    if (data.success && data.data) {
      Object.assign(config.value, data.data)
    }
  } catch {
    // Fall back to localStorage
    try {
      const saved = localStorage.getItem('mirofish_autopilot_config')
      if (saved) Object.assign(config.value, JSON.parse(saved))
    } catch { /* ignore */ }
  }
}

const resetPortfolio = async () => {
  if (!confirm('Reset portfolio to $10,000? All open positions will be cleared.')) return
  try {
    await api('/portfolio/reset', { method: 'POST' })
    await refreshData()
  } catch { /* ignore */ }
}

const saveConfig = async () => {
  try {
    await api('/autopilot/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config.value)
    })
  } catch { /* ignore */ }
  // Also persist to localStorage as backup
  try {
    localStorage.setItem('mirofish_autopilot_config', JSON.stringify(config.value))
  } catch { /* ignore */ }
  showConfig.value = false
}

// --- Run Cycle (unified) ---
const runCycle = async () => {
  cycleRunning.value = true
  const quickOnly = engineMode.value === 'quick'
  try {
    const data = await api('/autopilot/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ quick_only: quickOnly })
    })
    if (data.success && data.task_id) {
      const pollStatus = async () => {
        const status = await api(`/autopilot/run/${data.task_id}`)
        if (status.status === 'completed' || status.status === 'failed') {
          cycleRunning.value = false
          lastCycleResult.value = {
            started_at: status.started_at || new Date().toISOString(),
            scanned: status.scanned || 0,
            predicted: status.predicted || 0,
            bets_placed: status.bets_placed || 0,
            mode: quickOnly ? 'quick' : 'autopilot'
          }
          await fetchAll()
          return
        }
        setTimeout(pollStatus, 3000)
      }
      setTimeout(pollStatus, 3000)
    } else {
      // Synchronous response (no task_id)
      cycleRunning.value = false
      lastCycleResult.value = {
        started_at: new Date().toISOString(),
        scanned: data.scanned || 0,
        predicted: data.predicted || 0,
        bets_placed: data.bets_placed || 0,
        mode: quickOnly ? 'quick' : 'autopilot'
      }
      await fetchAll()
    }
  } catch {
    cycleRunning.value = false
  }
}

// --- Tooltip helpers ---
const showTooltip = (id) => {
  if (tooltipHideTimer) {
    clearTimeout(tooltipHideTimer)
    tooltipHideTimer = null
  }
  activeTooltip.value = id
}

const hideTooltipDelay = (id) => {
  tooltipHideTimer = setTimeout(() => {
    if (activeTooltip.value === id) {
      activeTooltip.value = null
    }
  }, 200)
}

const toggleTooltip = (id) => {
  activeTooltip.value = activeTooltip.value === id ? null : id
}

// --- Helpers ---
const formatTs = (ts) => {
  if (!ts) return '--'
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

const formatCloses = (ts) => {
  if (!ts) return '--'
  try {
    const d = new Date(ts)
    const now = new Date()
    const diff = d - now
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(hours / 24)
    if (diff < 0) return 'Closed'
    if (hours < 1) return '<1h'
    if (hours < 24) return hours + 'h'
    if (days < 2) return '1 day'
    return days + ' days'
  } catch { return ts }
}

const closesClass = (ts) => {
  if (!ts) return 'ts-cell'
  try {
    const diff = new Date(ts) - new Date()
    const hours = diff / 3600000
    if (hours < 0) return 'closes-closed'
    if (hours < 24) return 'closes-urgent'
    if (hours < 72) return 'closes-soon'
    return 'closes-normal'
  } catch { return 'ts-cell' }
}

const formatTime = (ts) => {
  if (!ts) return '--'
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString()
  } catch { return ts }
}

// --- Lifecycle ---
onMounted(() => {
  loadConfig()
  fetchAll()
  pollInterval = setInterval(fetchAll, 10000)
})

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval)
  if (tooltipHideTimer) clearTimeout(tooltipHideTimer)
})
</script>

<style scoped>
.paper-trading {
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
.subtitle { color: #999; font-size: 14px; display: block; }

/* "How it works" link */
.learn-more {
  font-size: 12px;
  color: #888;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
  font-family: 'Space Grotesk', sans-serif;
}
.learn-more:hover { color: #333; }

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
.help-icon:hover {
  color: #333;
}

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
  /* Default: appear above */
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
}
/* Bridge the gap between icon and tooltip so hover persists */
.tip-content::before {
  content: '';
  position: absolute;
  bottom: -10px;
  left: 0;
  right: 0;
  height: 10px;
}
.tip-wrap.tip-below .tip-content::before {
  bottom: auto;
  top: -10px;
}
/* For items near left edge */
.tip-wrap.tip-left .tip-content {
  left: 0;
  transform: none;
}
/* For items near right edge */
.tip-wrap.tip-right .tip-content {
  left: auto;
  right: 0;
  transform: none;
}
/* Show below instead of above */
.tip-wrap.tip-below .tip-content {
  bottom: auto;
  top: calc(100% + 8px);
}
.tip-wrap:hover .tip-content {
  display: block;
}

/* ---- Mode badges ---- */
.mode-badge {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 3px 8px;
  border-radius: 3px;
  margin-left: 8px;
  font-family: 'JetBrains Mono', monospace;
}
.mode-badge-info {
  background: #f0f0f0;
  color: #666;
}
.mode-badge-warn {
  background: #fff3e0;
  color: #e65100;
}

.balance-card {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.balance-label { font-size: 12px; color: #999; text-transform: uppercase; letter-spacing: 1px; }
.balance-value { font-family: 'JetBrains Mono', monospace; font-size: 28px; font-weight: 700; }
.reset-portfolio-btn {
  background: none;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 11px;
  font-family: 'Space Grotesk', sans-serif;
  color: #999;
  cursor: pointer;
  padding: 3px 8px;
  margin-left: 10px;
  transition: all 0.15s;
}
.reset-portfolio-btn:hover { border-color: #c00; color: #c00; }

/* ---- TRADING ENGINE ---- */
.engine-section {
  border: 1px solid var(--border, #E5E5E5);
  padding: 20px;
  margin-bottom: 32px;
  background: #fafafa;
}
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.section-header h2 {
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #999;
  margin: 0;
}

.engine-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.mode-toggle {
  display: flex;
  gap: 8px;
  flex: 1;
}
.mode-option {
  display: flex;
  flex-direction: column;
  padding: 10px 16px;
  border: 2px solid var(--border, #E5E5E5);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: all 0.15s;
  background: #fff;
  position: relative;
}
.mode-option .tip-wrap { position: absolute; top: 8px; right: 8px; }
.mode-option.active {
  border-color: var(--black, #1a1a1a);
  background: #f5f5f5;
}
.mode-option input[type="radio"] { display: none; }
.mode-desc {
  font-size: 11px;
  font-weight: 400;
  color: #999;
  margin-top: 2px;
}

/* ---- Configure text button ---- */
.btn-text {
  background: none;
  border: none;
  color: #666;
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  padding: 6px 0;
  text-decoration: underline;
  text-underline-offset: 3px;
}
.btn-text:hover { color: #000; }

.engine-run-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
}
.engine-status {
  font-size: 12px;
  color: #666;
  font-family: 'JetBrains Mono', monospace;
}

/* ---- Config drawer (right slide-out) ---- */
.config-drawer-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.15);
  z-index: 9000;
}
.config-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 400px;
  background: #fff;
  border-left: 1px solid #e5e5e5;
  box-shadow: -4px 0 24px rgba(0,0,0,0.08);
  z-index: 9001;
  padding: 24px;
  overflow-y: auto;
}
.config-drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e5e5e5;
}
.config-drawer-header h3 {
  font-size: 17px;
  font-weight: 700;
  font-family: 'Space Grotesk', sans-serif;
  margin: 0;
}
.config-drawer-close {
  background: none;
  border: none;
  font-size: 22px;
  cursor: pointer;
  color: #666;
  padding: 0 4px;
}
.config-drawer-close:hover { color: #000; }
.btn-configure {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding: 8px 16px;
}
/* Drawer tooltips: appear below the icon, within the field */
.config-drawer .tip-wrap {
  position: relative;
}
.config-drawer .tip-wrap .tip-content {
  position: absolute;
  bottom: auto;
  top: calc(100% + 6px);
  left: -100px;
  right: auto;
  transform: none;
  width: 300px;
  max-width: 300px;
  z-index: 9999;
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
.config-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
  font-family: 'Space Grotesk', sans-serif;
  position: relative;
  overflow: visible;
}
.config-field label {
  font-weight: 600;
  color: #444;
  font-size: 13px;
  display: flex;
  align-items: center;
}
.config-field input,
.config-field select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border, #E5E5E5);
  font-family: 'JetBrains Mono', monospace;
  font-size: 14px;
  border-radius: 4px;
}

/* Stepper */
.stepper {
  display: inline-flex;
  align-items: center;
  gap: 0;
  border: 1px solid var(--border, #E5E5E5);
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}
.stepper-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: #f5f5f5;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  color: #333;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.1s;
  flex-shrink: 0;
}
.stepper-btn:hover { background: #e0e0e0; }
.stepper-btn:active { background: #d0d0d0; }
.stepper-input {
  width: 52px;
  border: none !important;
  border-radius: 0 !important;
  text-align: center;
  font-size: 14px !important;
  font-family: 'JetBrains Mono', monospace;
  padding: 6px 2px !important;
  -moz-appearance: textfield;
}
.stepper-input::-webkit-inner-spin-button,
.stepper-input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.stepper-prefix, .stepper-suffix {
  font-size: 11px;
  color: #888;
  font-family: 'Space Grotesk', sans-serif;
  padding: 0 6px;
  white-space: nowrap;
}
.stepper-prefix { border-right: 1px solid #eee; }

/* Chip selector */
.chip-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.chip-btn {
  padding: 6px 14px;
  border: 1px solid var(--border, #E5E5E5);
  border-radius: 20px;
  background: #fff;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.1s;
}
.chip-btn:hover { border-color: #999; }
.chip-btn.active {
  background: var(--black, #1a1a1a);
  color: #fff;
  border-color: var(--black, #1a1a1a);
}


/* Toggle row */
.toggle-row {
  display: flex;
  gap: 0;
  border: 1px solid var(--border, #E5E5E5);
  border-radius: 6px;
  overflow: hidden;
  width: fit-content;
}
.toggle-btn {
  padding: 8px 20px;
  border: none;
  background: #fff;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.1s;
}
.toggle-btn:first-child { border-right: 1px solid var(--border, #E5E5E5); }
.toggle-btn.active {
  background: var(--black, #1a1a1a);
  color: #fff;
}
.toggle-btn:not(.active):hover { background: #f5f5f5; }

/* Disabled config fields */
.config-disabled {
  opacity: 0.35;
  pointer-events: none;
}
.config-mode-tag {
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #999;
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  margin-left: 6px;
  vertical-align: middle;
}
.config-field input:focus,
.config-field select:focus {
  outline: none;
  border-color: var(--black, #1a1a1a);
}
.config-unit {
  font-size: 11px;
  color: #999;
}
.config-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

/* ---- Buttons ---- */
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
.btn-outline { background: #fff; color: var(--black, #1a1a1a); }
.btn-outline:hover:not(:disabled) { background: #f5f5f5; }
.btn-sm { padding: 6px 14px; font-size: 12px; }

/* ---- Stats ---- */
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
.stat-label {
  font-size: 11px;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-top: 4px;
  display: flex;
  align-items: center;
}

.pnl-pos { color: #28a745; }
.pnl-neg { color: #dc3545; }

/* ---- Sections ---- */
.section { margin-bottom: 32px; }
.section-title {
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.section-title .count {
  background: var(--border, #E5E5E5);
  padding: 2px 8px;
  border-radius: 2px;
  font-size: 12px;
  color: #666;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--black, #1a1a1a);
  flex-shrink: 0;
}
.clickable { cursor: pointer; }
.chevron { margin-left: auto; font-size: 11px; }

.empty {
  color: #999;
  font-size: 14px;
  padding: 24px 0;
  text-align: center;
  border: 1px dashed var(--border, #E5E5E5);
}

/* ---- Tables ---- */
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
.market-link {
  color: var(--black, #1a1a1a);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: border-color 0.15s;
}
.market-link:hover {
  border-bottom-color: var(--black, #1a1a1a);
  color: #FF4500;
}
.ts-cell { font-size: 11px; color: #999; }

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

.closes-urgent {
  color: #e53e3e;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}
.closes-soon {
  color: #FF4500;
  font-weight: 600;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}
.closes-normal {
  color: #666;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}
.closes-closed {
  color: #999;
  font-style: italic;
  font-size: 12px;
}
.outcome-pending {
  color: #999;
  font-size: 11px;
  font-style: italic;
}
.pnl-pending {
  color: #999;
}

/* Amount cell with tooltip */
.amount-cell {
  position: relative;
  white-space: nowrap;
}
.reasoning-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1.5px solid #bbb;
  background: transparent;
  color: #999;
  font-size: 11px;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 600;
  cursor: pointer;
  margin-left: 5px;
  vertical-align: middle;
  line-height: 1;
  padding: 0;
  flex-shrink: 0;
  transition: all 0.15s;
  position: relative;
}
.reasoning-icon:hover {
  border-color: #666;
  color: #666;
}
.reasoning-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--black, #1a1a1a);
  color: #fff;
  padding: 12px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  line-height: 1.7;
  white-space: nowrap;
  z-index: 100;
  min-width: 260px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  border-radius: 6px;
}
.reasoning-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: var(--black, #1a1a1a);
}
.tooltip-row {
  display: flex;
  gap: 6px;
}
.tooltip-key {
  color: #999;
  flex-shrink: 0;
}

/* ---- Strategy Config ---- */
.strategy-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.config-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 12px;
  background: #fafafa;
  border: 1px solid var(--border, #E5E5E5);
  font-size: 12px;
}
.config-key { font-weight: 600; }
.config-val { font-family: 'JetBrains Mono', monospace; color: #666; }

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
.guide-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #e5e5e5;
  margin-bottom: 20px;
}
.guide-tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 8px 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  color: #999;
  cursor: pointer;
  transition: all 0.15s;
}
.guide-tab:hover { color: #333; }
.guide-tab.active {
  color: #1a1a1a;
  border-bottom-color: #1a1a1a;
}
.guide-body {
  font-size: 13px;
  line-height: 1.6;
  color: #333;
}
.guide-body p { margin: 0 0 12px; }
.guide-note {
  background: #f9f9f9;
  border-left: 3px solid #FF4500;
  padding: 10px 14px;
  font-size: 12px;
  color: #666;
  margin: 12px 0;
}
.modal-list-numbered { padding-left: 20px; }
.modal-list-numbered li { margin-bottom: 6px; }
.inline-help {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 1.5px solid #bbb;
  font-size: 10px;
  font-weight: 600;
  color: #999;
  vertical-align: middle;
}
.tip-link {
  color: #fff;
  text-decoration: underline;
  font-weight: 700;
  font-size: 11px;
  pointer-events: none;
  cursor: default;
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
.tip-link-text:hover {
  color: #FF4500;
}
/* Mode comparison table in modal */
.mode-compare-table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0 20px;
  font-size: 13px;
  font-family: 'Space Grotesk', sans-serif;
}
.mode-compare-table th {
  text-align: center;
  font-weight: 700;
  padding: 8px 12px;
  border-bottom: 2px solid #1a1a1a;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.mode-compare-table th:first-child { text-align: left; }
.mode-compare-table td {
  padding: 6px 12px;
  border-bottom: 1px solid #f0f0f0;
  text-align: center;
  color: #2a8c4a;
  font-weight: 600;
}
.mode-compare-table .compare-key {
  text-align: left;
  color: #333;
  font-weight: 400;
}
.mode-compare-table .compare-no {
  color: #ccc;
}
/* Bet reasoning tooltip */
.bet-tip {
  width: 220px !important;
  padding: 10px 14px !important;
  flex-direction: column;
  gap: 4px;
}
.tip-wrap:hover .bet-tip {
  display: flex;
}
.bt-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  line-height: 1.6;
}
.bt-key {
  color: #999;
}
.bt-val {
  color: #fff;
  font-weight: 600;
}
/* Closes tooltip - compact */
.closes-tip {
  width: auto !important;
  min-width: 0 !important;
  white-space: nowrap;
  padding: 6px 10px !important;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
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

/* Paper mode badge */
.paper-mode-badge {
  display: inline-block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 2px 8px;
  background: #FFF3E0;
  color: #E65100;
  border: 1px solid #FFE0B2;
  vertical-align: middle;
  margin-left: 4px;
}
</style>
