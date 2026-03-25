<template>
  <div class="how-it-works">

    <!-- Sticky Section Nav -->
    <nav class="section-nav">
      <a v-for="s in sections" :key="s.id" :href="'#' + s.id"
         :class="{ active: activeSection === s.id }"
         @click.prevent="scrollTo(s.id)">
        {{ s.short }}
      </a>
    </nav>

    <!-- ================================================
         1. HERO
         ================================================ -->
    <section id="hero" class="hero">
      <h1 class="hero-title">How PolFish Thinks</h1>
      <p class="hero-subtitle">
        A swarm intelligence engine that debates the future so you don't have to.
      </p>
    </section>

    <!-- ================================================
         2. THE BIG PICTURE  (pipeline)
         ================================================ -->
    <section id="pipeline" class="section">
      <h2 class="section-title"><span class="dot"></span> The Big Picture</h2>
      <p class="section-intro">
        Every prediction flows through five stages. Click a stage to jump to the deep dive.
      </p>

      <div class="pipeline">
        <template v-for="(step, i) in pipelineSteps" :key="i">
          <a class="pipeline-card"
             :href="'#step-' + (i + 1)"
             @click.prevent="scrollTo('step-' + (i + 1))">
            <span class="pipeline-icon" v-html="step.icon"></span>
            <span class="pipeline-label">{{ step.label }}</span>
            <span class="pipeline-number">{{ i + 1 }}</span>
          </a>
          <div v-if="i < pipelineSteps.length - 1" class="pipeline-arrow">&rarr;</div>
        </template>
      </div>
    </section>

    <!-- ================================================
         3. STEP-BY-STEP DEEP DIVE
         ================================================ -->
    <section id="deep-dive" class="section">
      <h2 class="section-title"><span class="dot"></span> Step-by-Step Deep Dive</h2>
      <p class="section-intro">
        Expand each step to see exactly what happens under the hood.
      </p>

      <!-- Step 1 -->
      <details id="step-1" class="step-details" @toggle="onToggle">
        <summary class="step-summary">
          <span class="step-icon-sm"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>
          <span class="step-name">Seed Document</span>
          <span class="step-chevron"></span>
        </summary>
        <div class="step-body">
          <p><strong>What happens:</strong> You upload a document &mdash; a news article, research paper, or report &mdash; or PolFish auto-fetches news articles about a Polymarket question.</p>
          <p>The seed is the <em>raw material</em> that agents will debate about. Supported formats: <code>PDF</code>, <code>MD</code>, <code>TXT</code>.</p>
          <div class="analogy">
            <span class="analogy-label">Analogy</span>
            Think of it as the briefing packet you'd give to a room full of analysts before they start arguing.
          </div>
        </div>
      </details>

      <!-- Step 2 -->
      <details id="step-2" class="step-details" @toggle="onToggle">
        <summary class="step-summary">
          <span class="step-icon-sm"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><line x1="12" y1="8" x2="5" y2="16"/><line x1="12" y1="8" x2="19" y2="16"/></svg></span>
          <span class="step-name">Knowledge Graph (Zep)</span>
          <span class="step-chevron"></span>
        </summary>
        <div class="step-body">
          <p><strong>What happens:</strong> MiroFish extracts <strong>entities</strong> (people, organizations, events, concepts) and <strong>relationships</strong> from the seed document.</p>
          <p>It uses GPT-4o to read the document and identify key facts. These are stored in <strong>Zep</strong> as a graph database &mdash; nodes are entities, edges are relationships.</p>

          <div class="graph-example">
            <div class="graph-node">Elon Musk</div>
            <div class="graph-edge">&mdash;[CEO of]&rarr;</div>
            <div class="graph-node">Tesla</div>
            <div class="graph-edge">&mdash;[competes with]&rarr;</div>
            <div class="graph-node">BYD</div>
          </div>

          <div class="analogy">
            <span class="analogy-label">Analogy</span>
            Like a detective's conspiracy board, but actually useful.
          </div>
        </div>
      </details>

      <!-- Step 3 -->
      <details id="step-3" class="step-details" @toggle="onToggle">
        <summary class="step-summary">
          <span class="step-icon-sm"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></span>
          <span class="step-name">Agent Profiles</span>
          <span class="step-chevron"></span>
        </summary>
        <div class="step-body">
          <p><strong>What happens:</strong> AI generates diverse agent personas based on the knowledge graph. Each agent is unique:</p>
          <ul class="step-list">
            <li><strong>Supporters</strong> &mdash; argue for a "Yes" outcome</li>
            <li><strong>Opponents</strong> &mdash; argue for a "No" outcome</li>
            <li><strong>Analysts</strong> &mdash; try to be objective, data-driven</li>
            <li><strong>Contrarians</strong> &mdash; challenge the consensus</li>
            <li><strong>Domain experts</strong> &mdash; deep knowledge in a specific area</li>
          </ul>
          <p>Each agent has a name, background, personality, biases, and knowledge extracted from the graph. They simulate real people with real perspectives.</p>
          <div class="analogy">
            <span class="analogy-label">Analogy</span>
            Like casting actors for a debate show, each with their own agenda.
          </div>
        </div>
      </details>

      <!-- Step 4 -->
      <details id="step-4" class="step-details" @toggle="onToggle">
        <summary class="step-summary">
          <span class="step-icon-sm"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span>
          <span class="step-name">Multi-Agent Simulation</span>
          <span class="step-chevron"></span>
        </summary>
        <div class="step-body">
          <p><strong>What happens:</strong> Agents post on simulated <strong>Twitter</strong> and <strong>Reddit</strong> platforms. They react to each other's posts &mdash; agreeing, disagreeing, arguing, and sharing new information.</p>
          <ul class="step-list">
            <li>Runs for <strong>N rounds</strong> (configurable, default 15)</li>
            <li>Each round simulates hours of real-world discourse</li>
            <li>The simulation captures how public opinion evolves over time</li>
            <li>Agents form alliances, change their minds, and dig into data</li>
          </ul>
          <div class="analogy">
            <span class="analogy-label">Analogy</span>
            A miniature social media universe arguing about your question.
          </div>
        </div>
      </details>

      <!-- Step 5 -->
      <details id="step-5" class="step-details" @toggle="onToggle">
        <summary class="step-summary">
          <span class="step-icon-sm"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg></span>
          <span class="step-name">Report &amp; Prediction</span>
          <span class="step-chevron"></span>
        </summary>
        <div class="step-body">
          <p><strong>What happens:</strong> A <strong>Report Agent</strong> analyzes the entire simulation. It uses multiple tools:</p>
          <ul class="step-list">
            <li><strong>InsightForge</strong> &mdash; deep analysis of argument quality</li>
            <li><strong>Panorama</strong> &mdash; high-level overview of sentiment shifts</li>
            <li><strong>Interviews</strong> &mdash; Q&amp;A with key agents post-simulation</li>
            <li><strong>QuickSearch</strong> &mdash; fact-checking against external sources</li>
          </ul>
          <p>The output is a structured report with predictions, key factors, and confidence levels. The prediction probability is extracted and compared to market odds to find an <strong>edge</strong>.</p>
          <div class="analogy">
            <span class="analogy-label">Analogy</span>
            The referee summarizes the debate and declares a winner.
          </div>
        </div>
      </details>
    </section>

    <!-- ================================================
         4. THE TRADING ENGINE
         ================================================ -->
    <section id="trading" class="section">
      <h2 class="section-title"><span class="dot"></span> The Trading Engine</h2>
      <p class="section-intro">
        Once PolFish has a prediction, it decides whether and how much to bet.
      </p>

      <!-- Mode comparison -->
      <h3 class="subsection-title">Quick vs Deep</h3>
      <table class="mode-compare-table">
        <thead>
          <tr><th></th><th>Quick</th><th>Deep (Autopilot)</th></tr>
        </thead>
        <tbody>
          <tr><td class="compare-key">Cost</td><td>Free</td><td>~$4/market</td></tr>
          <tr><td class="compare-key">Speed</td><td>Instant</td><td>5&ndash;10 min</td></tr>
          <tr><td class="compare-key">Method</td><td>Market odds + noise</td><td>Full agent simulation</td></tr>
          <tr><td class="compare-key">Real edge?</td><td class="compare-no">No</td><td>Possible</td></tr>
          <tr><td class="compare-key">Good for</td><td>Testing infrastructure</td><td>Actual predictions</td></tr>
        </tbody>
      </table>

      <!-- Model Providers -->
      <h3 class="subsection-title">Model Providers</h3>
      <p class="section-body">
        PolFish supports mixing models from different providers across pipeline stages.
      </p>
      <table class="mode-compare-table provider-table">
        <thead>
          <tr>
            <th style="text-align: left">Provider</th>
            <th style="text-align: left">Best For</th>
            <th>Free Tier</th>
            <th>Pricing (per 1M)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="compare-key">OpenAI (GPT-4o)</td>
            <td class="compare-key">Simulation, Reports</td>
            <td class="compare-no">No</td>
            <td>$2.50 / $10.00</td>
          </tr>
          <tr>
            <td class="compare-key">DeepSeek V3</td>
            <td class="compare-key">Preprocessing</td>
            <td>Yes</td>
            <td>$0.14 / $0.28</td>
          </tr>
          <tr>
            <td class="compare-key">Gemini Flash</td>
            <td class="compare-key">Agent Profiles</td>
            <td>Yes</td>
            <td>$0.075 / $0.30</td>
          </tr>
          <tr>
            <td class="compare-key">Claude Sonnet</td>
            <td class="compare-key">Premium Reasoning</td>
            <td class="compare-no">No</td>
            <td>$3.00 / $15.00</td>
          </tr>
          <tr>
            <td class="compare-key">Mistral Small</td>
            <td class="compare-key">Budget Alternative</td>
            <td>Yes</td>
            <td>$0.10 / $0.30</td>
          </tr>
          <tr>
            <td class="compare-key">Groq (Llama)</td>
            <td class="compare-key">Fast Inference</td>
            <td>Yes</td>
            <td>$0.05 / $0.08</td>
          </tr>
        </tbody>
      </table>

      <!-- Pipeline Presets -->
      <h3 class="subsection-title">Pipeline Presets</h3>
      <p class="section-body">
        Switch between configurations with one environment variable: <code>PIPELINE_PRESET</code>
      </p>
      <div class="preset-table-wrapper">
        <table class="mode-compare-table preset-table">
          <thead>
            <tr>
              <th style="text-align: left">Preset</th>
              <th>Preprocessing</th>
              <th>Profiles</th>
              <th>Simulation</th>
              <th>Report</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="compare-key"><code>balanced</code></td>
              <td>DeepSeek V3</td>
              <td>Gemini Flash</td>
              <td>GPT-4o</td>
              <td>GPT-4o</td>
              <td>~$0.42</td>
            </tr>
            <tr>
              <td class="compare-key"><code>budget</code></td>
              <td>DeepSeek V3</td>
              <td>DeepSeek V3</td>
              <td>GPT-4o Mini</td>
              <td>GPT-4o Mini</td>
              <td>~$0.03</td>
            </tr>
            <tr>
              <td class="compare-key"><code>premium</code></td>
              <td>DeepSeek V3</td>
              <td>Gemini Flash</td>
              <td>Claude</td>
              <td>GPT-4o</td>
              <td>~$0.54</td>
            </tr>
            <tr>
              <td class="compare-key"><code>cheapest</code></td>
              <td>DeepSeek V3</td>
              <td>DeepSeek V3</td>
              <td>DeepSeek V3</td>
              <td>DeepSeek V3</td>
              <td>~$0.02</td>
            </tr>
            <tr>
              <td class="compare-key"><code>best</code></td>
              <td>GPT-4o</td>
              <td>GPT-4o</td>
              <td>GPT-4o</td>
              <td>GPT-4o</td>
              <td>~$0.58</td>
            </tr>
            <tr>
              <td class="compare-key"><code>gemini</code></td>
              <td>Gemini Flash</td>
              <td>Gemini Flash</td>
              <td>Gemini Flash</td>
              <td>Gemini Flash</td>
              <td>~$0.03</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Autopilot Loop -->
      <h3 class="subsection-title">The Autopilot Loop</h3>
      <p class="section-body">Every 6 hours, PolFish runs a full cycle:</p>
      <div class="code-block">
        <div class="code-line"><span class="code-comment">// The Autopilot Cycle</span></div>
        <div class="code-line"><span class="code-step">1.</span> Scan Polymarket for expiring markets</div>
        <div class="code-line"><span class="code-step">2.</span> Quick-predict all &rarr; rank by edge</div>
        <div class="code-line"><span class="code-step">3.</span> Deep-predict top 3 (budget-capped)</div>
        <div class="code-line"><span class="code-step">4.</span> Confirm edge still exists after deep analysis</div>
        <div class="code-line"><span class="code-step">5.</span> Place paper bet (Kelly criterion sizing)</div>
        <div class="code-line"><span class="code-step">6.</span> Check resolved markets &rarr; update P&amp;L</div>
        <div class="code-line"><span class="code-step">7.</span> Optimizer adjusts strategy based on results</div>
      </div>

      <!-- Kelly Criterion -->
      <h3 class="subsection-title">Kelly Criterion</h3>
      <p class="section-body">
        Kelly tells you the mathematically optimal bet size. The formula is simple:
      </p>
      <div class="formula-block">
        <span class="formula">Bet size = edge &times; confidence / odds</span>
      </div>
      <p class="section-body">
        We use <strong>quarter-Kelly</strong> (conservative) to avoid ruin. If Kelly says bet 20% of your bankroll, we bet 5%. Slow and steady. The goal is to survive long enough for the edge to compound.
      </p>

      <!-- Optimizer -->
      <h3 class="subsection-title">The Self-Improving Optimizer</h3>
      <p class="section-body">
        After every batch of resolved bets, the optimizer reviews the results and adjusts:
      </p>
      <ul class="step-list optimizer-list">
        <li><strong>Calibration</strong> &mdash; learns if PolFish systematically over- or under-predicts</li>
        <li><strong>Category weights</strong> &mdash; learns which market types it's good at (politics, crypto, sports...)</li>
        <li><strong>Edge threshold</strong> &mdash; adjusts the minimum edge required before placing a bet</li>
      </ul>
      <div class="analogy">
        <span class="analogy-label">Analogy</span>
        Like a poker player reviewing their hands after a session and adjusting strategy.
      </div>
    </section>

    <!-- ================================================
         5. COST CALCULATOR
         ================================================ -->
    <section id="cost-calc" class="section">
      <h2 class="section-title"><span class="dot"></span> Cost Calculator</h2>
      <p class="section-intro">
        The hybrid pipeline uses cheap models for preprocessing and GPT-4o only where it matters.
      </p>

      <!-- Loading state -->
      <div v-if="costLoading" class="cost-loading">Loading cost data...</div>

      <template v-if="costData">
        <!-- Preset selector -->
        <h3 class="subsection-title">Pipeline Preset</h3>
        <div class="preset-selector">
          <button v-for="p in presetNames" :key="p"
                  :class="['preset-btn', { active: selectedPreset === p, 'is-active-preset': p === activePresetName }]"
                  @click="selectedPreset = p">
            {{ p }}
            <span v-if="p === activePresetName" class="preset-active-dot"></span>
          </button>
        </div>
        <p class="preset-hint" v-if="selectedPreset !== activePresetName">
          Viewing cost estimate for <code>{{ selectedPreset }}</code> preset. Active preset is <code>{{ activePresetName }}</code>.
        </p>

        <!-- Savings badge -->
        <div class="savings-badge" v-if="displayCost.savings_vs_gpt4o_percent > 0">
          You save {{ displayCost.savings_vs_gpt4o_percent }}% vs all GPT-4o
        </div>

        <!-- Current config table -->
        <h3 class="subsection-title">{{ selectedPreset === activePresetName ? 'Current' : selectedPreset }} Pipeline Config</h3>
        <table class="cost-table">
          <thead>
            <tr>
              <th>Stage</th>
              <th>Model</th>
              <th>Tokens</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in displayCost.stages" :key="s.stage">
              <td class="cost-stage">{{ s.stage }}</td>
              <td class="cost-model"><code>{{ s.model }}</code></td>
              <td class="cost-num">{{ (s.input_tokens + s.output_tokens).toLocaleString() }}</td>
              <td class="cost-num cost-usd">${{ s.cost_usd.toFixed(4) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td colspan="2"><strong>Total</strong></td>
              <td class="cost-num">{{ displayCost.total_tokens.toLocaleString() }}</td>
              <td class="cost-num cost-usd"><strong>${{ displayCost.total_cost_usd.toFixed(4) }}</strong></td>
            </tr>
          </tfoot>
        </table>

        <!-- Comparison bar chart -->
        <h3 class="subsection-title">Cost Comparison</h3>
        <div class="cost-bars">
          <div class="cost-bar-row">
            <span class="cost-bar-label">All GPT-4o</span>
            <div class="cost-bar-track">
              <div class="cost-bar-fill cost-bar-expensive" :style="{ width: barWidth(costData.alternatives.all_gpt4o.cost_usd) }"></div>
            </div>
            <span class="cost-bar-value">${{ costData.alternatives.all_gpt4o.cost_usd.toFixed(2) }}</span>
          </div>
          <div class="cost-bar-row">
            <span class="cost-bar-label">{{ selectedPreset }} preset</span>
            <div class="cost-bar-track">
              <div class="cost-bar-fill cost-bar-hybrid" :style="{ width: barWidth(displayCost.total_cost_usd) }"></div>
            </div>
            <span class="cost-bar-value">${{ displayCost.total_cost_usd.toFixed(2) }}</span>
          </div>
          <div class="cost-bar-row">
            <span class="cost-bar-label">All GPT-4o-mini</span>
            <div class="cost-bar-track">
              <div class="cost-bar-fill cost-bar-mini" :style="{ width: barWidth(costData.alternatives.all_gpt4o_mini.cost_usd) }"></div>
            </div>
            <span class="cost-bar-value">${{ costData.alternatives.all_gpt4o_mini.cost_usd.toFixed(2) }}</span>
          </div>
          <div class="cost-bar-row">
            <span class="cost-bar-label">All DeepSeek</span>
            <div class="cost-bar-track">
              <div class="cost-bar-fill cost-bar-cheap" :style="{ width: barWidth(costData.alternatives.all_deepseek.cost_usd) }"></div>
            </div>
            <span class="cost-bar-value">${{ costData.alternatives.all_deepseek.cost_usd.toFixed(2) }}</span>
          </div>
        </div>

        <!-- Batch estimator -->
        <h3 class="subsection-title">Batch Estimator</h3>
        <div class="batch-estimator">
          <div class="batch-options">
            <button v-for="n in batchOptions" :key="n"
                    :class="['batch-btn', { active: batchCount === n }]"
                    @click="batchCount = n">
              {{ n }}
            </button>
          </div>
          <div class="batch-result">
            <span class="batch-label">{{ batchCount }} predictions</span>
            <span class="batch-cost">${{ (displayCost.total_cost_usd * batchCount).toFixed(2) }}</span>
          </div>
        </div>
      </template>
    </section>

    <!-- ================================================
         6. HONEST LIMITATIONS
         ================================================ -->
    <section id="limitations" class="section">
      <h2 class="section-title"><span class="dot"></span> Honest Limitations</h2>
      <p class="section-intro">
        We believe in building trust through transparency, not hype.
      </p>

      <ul class="limitations-list">
        <li>
          <span class="lim-badge lim-warn"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span>
          <div>
            <strong>Quick mode has NO real edge.</strong>
            It's random noise layered on market odds &mdash; useful only for testing infrastructure.
          </div>
        </li>
        <li>
          <span class="lim-badge lim-cost"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></span>
          <div>
            <strong>Deep mode costs real money.</strong>
            Each deep prediction uses ~$4 in OpenAI API tokens. Budget accordingly.
          </div>
        </li>
        <li>
          <span class="lim-badge lim-neutral"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></span>
          <div>
            <strong>Prediction markets are efficient.</strong>
            Beating them consistently is genuinely hard. The crowd is smart.
          </div>
        </li>
        <li>
          <span class="lim-badge lim-niche"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span>
          <div>
            <strong>Works best on niche markets.</strong>
            Less-traded, information-asymmetric markets are where PolFish has the best shot.
          </div>
        </li>
        <li>
          <span class="lim-badge lim-data"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg></span>
          <div>
            <strong>Calibration needs data.</strong>
            The system needs 50+ resolved bets before the optimizer's adjustments become meaningful.
          </div>
        </li>
      </ul>

      <div class="closing-quote">
        "We built the telescope. Whether it sees stars or noise depends on where you point it."
      </div>
    </section>

    <!-- ================================================
         6. ARCHITECTURE DIAGRAM
         ================================================ -->
    <section id="architecture" class="section">
      <h2 class="section-title"><span class="dot"></span> Architecture</h2>
      <p class="section-intro">
        How the pieces fit together, from data in to decisions out.
      </p>

      <div class="arch-diagram">
        <div class="arch-main-row">
          <div class="arch-node">Polymarket API</div>
          <div class="arch-connector"><span></span></div>
          <div class="arch-node">Scanner</div>
          <div class="arch-connector"><span></span></div>
          <div class="arch-node">Seed Generator</div>
          <div class="arch-connector"><span></span></div>
          <div class="arch-node arch-highlight">MiroFish Engine</div>
          <div class="arch-connector"><span></span></div>
          <div class="arch-node">Prediction</div>
        </div>
        <div class="arch-vertical">
          <div class="arch-vline"></div>
        </div>
        <div class="arch-branch-nodes">
          <div class="arch-node">Paper Trading</div>
          <div class="arch-vertical"><div class="arch-vline"></div></div>
          <div class="arch-node">Decision Ledger</div>
          <div class="arch-vertical"><div class="arch-vline"></div></div>
          <div class="arch-node arch-highlight">Optimizer</div>
          <div class="arch-vertical"><div class="arch-vline"></div></div>
          <div class="arch-feedback-box">Feeds back to Scanner config</div>
        </div>
      </div>
    </section>

    <!-- ================================================
         8. DOCUMENTATION
         ================================================ -->
    <section id="docs" class="section">
      <h2 class="section-title"><span class="dot"></span> Full Documentation</h2>
      <p class="section-intro">
        For detailed technical documentation, API reference, and configuration guides:
      </p>
      <div class="docs-link-box">
        <span class="docs-arrow">&rarr;</span>
        <a href="https://github.com/rabeaabuaqel/MiroFish/blob/main/docs/README.md"
           target="_blank" rel="noopener noreferrer" class="docs-link">
          docs/README.md
        </a>
        <span class="docs-note">(in the repository)</span>
      </div>
    </section>

    <!-- Bottom spacer -->
    <div class="bottom-spacer"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const activeSection = ref('hero')

const sections = [
  { id: 'hero', short: 'Top' },
  { id: 'pipeline', short: 'Pipeline' },
  { id: 'deep-dive', short: 'Deep Dive' },
  { id: 'trading', short: 'Trading' },
  { id: 'cost-calc', short: 'Cost' },
  { id: 'limitations', short: 'Limits' },
  { id: 'architecture', short: 'Architecture' },
  { id: 'docs', short: 'Docs' }
]

const pipelineSteps = [
  { icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>', label: 'Seed' },
  { icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><line x1="12" y1="8" x2="5" y2="16"/><line x1="12" y1="8" x2="19" y2="16"/></svg>', label: 'Graph' },
  { icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>', label: 'Agents' },
  { icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>', label: 'Debate' },
  { icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>', label: 'Prediction' }
]

// Cost calculator data
const costData = ref(null)
const costLoading = ref(false)
const batchCount = ref(50)
const batchOptions = [10, 25, 50, 100]

// Preset selector
const presetNames = ['balanced', 'budget', 'premium', 'cheapest', 'best', 'gemini']
const selectedPreset = ref('balanced')

const activePresetName = computed(() => {
  if (!costData.value) return 'balanced'
  return costData.value.active_preset || 'balanced'
})

// Client-side preset cost estimation (model pricing per 1M tokens)
const presetModels = {
  balanced:  { ontology: 'deepseek-chat', graph: 'deepseek-chat', profiles: 'gemini-2.0-flash', simulation: 'gpt-4o', report: 'gpt-4o' },
  budget:    { ontology: 'deepseek-chat', graph: 'deepseek-chat', profiles: 'deepseek-chat', simulation: 'gpt-4o-mini', report: 'gpt-4o-mini' },
  premium:   { ontology: 'deepseek-chat', graph: 'deepseek-chat', profiles: 'gemini-2.0-flash', simulation: 'claude-sonnet-4-20250514', report: 'gpt-4o' },
  cheapest:  { ontology: 'deepseek-chat', graph: 'deepseek-chat', profiles: 'deepseek-chat', simulation: 'deepseek-chat', report: 'deepseek-chat' },
  best:      { ontology: 'gpt-4o', graph: 'gpt-4o', profiles: 'gpt-4o', simulation: 'gpt-4o', report: 'gpt-4o' },
  gemini:    { ontology: 'gemini-2.5-flash', graph: 'gemini-2.5-flash', profiles: 'gemini-2.0-flash', simulation: 'gemini-2.5-flash', report: 'gemini-2.5-flash' },
}

const modelPricing = {
  'gpt-4o':        { input: 2.50, output: 10.00 },
  'gpt-4o-mini':   { input: 0.15, output: 0.60 },
  'deepseek-chat': { input: 0.14, output: 0.28 },
  'gemini-2.0-flash': { input: 0.075, output: 0.30 },
  'gemini-2.5-flash': { input: 0.15, output: 0.60 },
  'claude-sonnet-4-20250514': { input: 3.00, output: 15.00 },
}

const modelDisplayName = {
  'gpt-4o': 'gpt-4o',
  'gpt-4o-mini': 'gpt-4o-mini',
  'deepseek-chat': 'deepseek-chat',
  'gemini-2.0-flash': 'gemini-2.0-flash',
  'gemini-2.5-flash': 'gemini-2.5-flash',
  'claude-sonnet-4-20250514': 'claude-sonnet-4',
}

// Stage name mapping from internal to display names
const stageDisplayOrder = ['ontology', 'graph', 'profiles', 'simulation', 'report']

const displayCost = computed(() => {
  if (!costData.value) return { stages: [], total_tokens: 0, total_cost_usd: 0, savings_vs_gpt4o_percent: 0 }

  // If the selected preset matches active, use real data
  if (selectedPreset.value === activePresetName.value) {
    return {
      stages: costData.value.current_hybrid.stages,
      total_tokens: costData.value.current_hybrid.total_tokens,
      total_cost_usd: costData.value.current_hybrid.total_cost_usd,
      savings_vs_gpt4o_percent: costData.value.savings_vs_gpt4o_percent,
    }
  }

  // Otherwise, estimate from the real token counts but with different model pricing
  const realStages = costData.value.current_hybrid.stages
  const presetConfig = presetModels[selectedPreset.value] || presetModels.balanced
  const stages = stageDisplayOrder.map((stageName, i) => {
    const realStage = realStages[i] || realStages[0]
    const model = presetConfig[stageName] || 'gpt-4o'
    const pricing = modelPricing[model] || { input: 2.50, output: 10.00 }
    const inputTokens = realStage.input_tokens
    const outputTokens = realStage.output_tokens
    const cost = (inputTokens * pricing.input + outputTokens * pricing.output) / 1_000_000
    return {
      stage: stageName,
      model: modelDisplayName[model] || model,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      cost_usd: cost,
    }
  })
  const totalTokens = stages.reduce((sum, s) => sum + s.input_tokens + s.output_tokens, 0)
  const totalCost = stages.reduce((sum, s) => sum + s.cost_usd, 0)
  const gpt4oCost = costData.value.alternatives.all_gpt4o.cost_usd
  const savings = gpt4oCost > 0 ? Math.round((1 - totalCost / gpt4oCost) * 100) : 0

  return {
    stages,
    total_tokens: totalTokens,
    total_cost_usd: totalCost,
    savings_vs_gpt4o_percent: Math.max(0, savings),
  }
})

const barWidth = (cost) => {
  if (!costData.value) return '0%'
  const max = costData.value.alternatives.all_gpt4o.cost_usd
  return Math.min((cost / max) * 100, 100) + '%'
}

const fetchCostData = async () => {
  costLoading.value = true
  try {
    const res = await fetch('/api/polymarket/cost/compare')
    const json = await res.json()
    if (json.success) {
      costData.value = json.data
      if (json.data.active_preset) {
        selectedPreset.value = json.data.active_preset
      }
    }
  } catch (e) {
    console.warn('Could not load cost data:', e)
  } finally {
    costLoading.value = false
  }
}

const scrollTo = (id) => {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    // If it's a details element, open it
    if (el.tagName === 'DETAILS') {
      el.open = true
    }
  }
}

const onToggle = () => {
  // no-op, just here for reactivity
}

// Intersection observer for active section tracking
let observer = null
onMounted(() => {
  fetchCostData()
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          activeSection.value = entry.target.id
        }
      }
    },
    { rootMargin: '-80px 0px -60% 0px', threshold: 0.1 }
  )
  sections.forEach((s) => {
    const el = document.getElementById(s.id)
    if (el) observer.observe(el)
  })
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
/* ========================================
   Page Layout
   ======================================== */
.how-it-works {
  max-width: 880px;
  margin: 0 auto;
  padding: 40px 32px 0;
  font-family: 'Space Grotesk', sans-serif;
  color: #1a1a1a;
  line-height: 1.7;
}

/* ========================================
   Sticky Section Nav
   ======================================== */
.section-nav {
  position: sticky;
  top: 56px;
  z-index: 100;
  display: flex;
  gap: 4px;
  padding: 12px 0;
  margin-bottom: 24px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid #eee;
}

.section-nav a {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-decoration: none;
  color: #999;
  padding: 4px 12px;
  border-radius: 3px;
  transition: all 0.15s;
}

.section-nav a:hover {
  color: #333;
  background: #f5f5f5;
}

.section-nav a.active {
  color: #FF4500;
  background: rgba(255, 69, 0, 0.06);
}

/* ========================================
   Hero Section
   ======================================== */
.hero {
  text-align: center;
  padding: 80px 0 60px;
}

.hero-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 48px;
  font-weight: 800;
  letter-spacing: -1px;
  color: #000;
  margin-bottom: 16px;
}

.hero-subtitle {
  font-size: 20px;
  color: #666;
  max-width: 560px;
  margin: 0 auto;
  font-weight: 400;
}

/* ========================================
   Section Common
   ======================================== */
.section {
  padding: 48px 0 24px;
}

.section-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: #000;
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #FF4500;
  flex-shrink: 0;
}

.section-intro {
  font-size: 17px;
  color: #555;
  margin-bottom: 32px;
  max-width: 640px;
}

.section-body {
  font-size: 16px;
  color: #333;
  margin-bottom: 16px;
  max-width: 700px;
}

.subsection-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: #000;
  margin: 40px 0 16px;
}

/* ========================================
   Pipeline Cards
   ======================================== */
.pipeline {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  flex-wrap: wrap;
  margin: 24px 0;
}

.pipeline-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 24px;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 8px;
  text-decoration: none;
  color: #1a1a1a;
  transition: all 0.2s;
  position: relative;
  min-width: 100px;
}

.pipeline-card:hover {
  border-color: #FF4500;
  background: #fff;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 69, 0, 0.1);
}

.pipeline-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #111;
  color: #fff;
}

.pipeline-icon svg {
  width: 22px;
  height: 22px;
}

.pipeline-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.pipeline-number {
  position: absolute;
  top: 6px;
  right: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: #ccc;
  font-weight: 700;
}

.pipeline-arrow {
  font-size: 20px;
  color: #ccc;
  padding: 0 8px;
  font-weight: 300;
}

/* ========================================
   Step Details (expandable)
   ======================================== */
.step-details {
  margin-bottom: 8px;
  border-left: 2px solid #eee;
  transition: border-color 0.2s;
}

.step-details[open] {
  border-left-color: #FF4500;
  margin-bottom: 16px;
}

.step-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
  list-style: none;
  transition: background 0.15s;
}

.step-summary::-webkit-details-marker {
  display: none;
}

.step-summary:hover {
  background: #fafafa;
}

.step-icon-sm {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  min-width: 28px;
  border-radius: 50%;
  background: #FF4500;
  color: #fff;
}

.step-icon-sm svg {
  width: 14px;
  height: 14px;
}

.step-name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: #000;
}

.step-chevron {
  margin-left: auto;
  width: 8px;
  height: 8px;
  border-right: 2px solid #999;
  border-bottom: 2px solid #999;
  transform: rotate(45deg);
  transition: transform 0.2s;
}

.step-details[open] .step-chevron {
  transform: rotate(-135deg);
}

.step-body {
  padding: 4px 20px 24px 56px;
  font-size: 15px;
  color: #333;
}

.step-body p {
  margin-bottom: 12px;
}

.step-body code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  color: #FF4500;
}

.step-list {
  margin: 12px 0;
  padding-left: 20px;
}

.step-list li {
  margin-bottom: 6px;
  color: #444;
}

.step-list li strong {
  color: #000;
}

/* ========================================
   Analogy Box
   ======================================== */
.analogy {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 18px;
  background: #fffaf6;
  border: 1px solid #ffe4d4;
  border-radius: 6px;
  margin-top: 16px;
  font-size: 14px;
  color: #8a5a32;
  font-style: italic;
}

.analogy-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #FF4500;
  flex-shrink: 0;
}

/* ========================================
   Knowledge Graph Example
   ======================================== */
.graph-example {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 20px;
  background: #1a1a1a;
  border-radius: 8px;
  margin: 16px 0;
  overflow-x: auto;
  flex-wrap: wrap;
  justify-content: center;
}

.graph-node {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: #333;
  padding: 8px 16px;
  border-radius: 4px;
  border: 1px solid #555;
  white-space: nowrap;
}

.graph-edge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #FF4500;
  white-space: nowrap;
}

/* ========================================
   Mode Compare Table
   ======================================== */
.mode-compare-table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0 20px;
  font-size: 14px;
  font-family: 'Space Grotesk', sans-serif;
}

.mode-compare-table th {
  text-align: center;
  font-weight: 700;
  padding: 10px 14px;
  border-bottom: 2px solid #1a1a1a;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.mode-compare-table th:first-child {
  text-align: left;
}

.mode-compare-table td {
  padding: 8px 14px;
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

/* ========================================
   Code Block
   ======================================== */
.code-block {
  background: #1a1a1a;
  border-radius: 8px;
  padding: 20px 24px;
  margin: 16px 0 24px;
  overflow-x: auto;
}

.code-line {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #ddd;
  line-height: 2;
  white-space: nowrap;
}

.code-comment {
  color: #666;
}

.code-step {
  color: #FF4500;
  font-weight: 700;
  margin-right: 4px;
}

/* ========================================
   Formula Block
   ======================================== */
.formula-block {
  text-align: center;
  padding: 24px;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 8px;
  margin: 16px 0 24px;
}

.formula {
  font-family: 'JetBrains Mono', monospace;
  font-size: 16px;
  font-weight: 700;
  color: #000;
  letter-spacing: 0.5px;
}

/* ========================================
   Optimizer List
   ======================================== */
.optimizer-list {
  margin-bottom: 16px;
}

/* ========================================
   Limitations
   ======================================== */
.limitations-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.limitations-list li {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 15px;
  color: #333;
}

.limitations-list li:last-child {
  border-bottom: none;
}

.lim-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  min-width: 28px;
  border-radius: 50%;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 800;
  flex-shrink: 0;
}

.lim-warn {
  background: #FF4500;
  color: #fff;
}

.lim-cost {
  background: #111;
  color: #fff;
}

.lim-neutral {
  background: #888;
  color: #fff;
}

.lim-niche {
  background: #FF4500;
  color: #fff;
}

.lim-data {
  background: #111;
  color: #fff;
}

.limitations-list li strong {
  color: #000;
}

.closing-quote {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 18px;
  font-weight: 500;
  color: #888;
  font-style: italic;
  text-align: center;
  padding: 40px 24px;
  border-top: 1px solid #eee;
  margin-top: 24px;
}

/* ========================================
   Architecture Diagram
   ======================================== */
.arch-diagram {
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 40px 24px;
  margin: 24px 0;
  overflow-x: auto;
}

.arch-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.arch-main-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  flex-wrap: wrap;
}

.arch-node {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 700;
  padding: 12px 18px;
  background: #fff;
  border: 1.5px solid #ddd;
  border-radius: 6px;
  white-space: nowrap;
  color: #333;
}

.arch-highlight {
  border-color: #FF4500;
  color: #FF4500;
  background: #fff8f5;
}

.arch-connector {
  display: flex;
  align-items: center;
  padding: 0 4px;
}

.arch-connector span {
  display: block;
  width: 24px;
  height: 1.5px;
  background: #ccc;
  position: relative;
}

.arch-connector span::after {
  content: '';
  position: absolute;
  right: 0;
  top: -3px;
  border: 3.5px solid transparent;
  border-left-color: #ccc;
}

.arch-vertical {
  display: flex;
  justify-content: center;
  padding: 4px 0;
}

.arch-vline {
  width: 1.5px;
  height: 20px;
  background: #ccc;
  position: relative;
}

.arch-vline::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: -3px;
  border: 3.5px solid transparent;
  border-top-color: #ccc;
}

.arch-branch-nodes {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.arch-feedback-box {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #999;
  font-style: italic;
  padding: 8px 16px;
  border: 1.5px dashed #ccc;
  border-radius: 4px;
}

/* ========================================
   Bottom Spacer
   ======================================== */
.bottom-spacer {
  height: 80px;
}

/* ========================================
   Responsive
   ======================================== */
/* ========================================
   Cost Calculator
   ======================================== */
.cost-loading {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: #999;
  padding: 24px 0;
}

.savings-badge {
  display: inline-block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  color: #16a34a;
  background: rgba(22, 163, 74, 0.08);
  border: 1px solid rgba(22, 163, 74, 0.2);
  padding: 6px 16px;
  border-radius: 4px;
  margin-bottom: 24px;
}

.cost-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 32px;
  font-size: 14px;
}

.cost-table th {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #999;
  text-align: left;
  padding: 8px 12px;
  border-bottom: 2px solid #eee;
}

.cost-table th:nth-child(3),
.cost-table th:nth-child(4) {
  text-align: right;
}

.cost-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.cost-stage {
  font-weight: 600;
  text-transform: capitalize;
}

.cost-model code {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
}

.cost-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  text-align: right;
}

.cost-usd {
  color: #16a34a;
}

.cost-table tfoot td {
  border-top: 2px solid #eee;
  border-bottom: none;
  padding-top: 10px;
}

/* Bar chart */
.cost-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 32px;
}

.cost-bar-row {
  display: grid;
  grid-template-columns: 140px 1fr 80px;
  align-items: center;
  gap: 12px;
}

.cost-bar-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  color: #666;
  text-align: right;
}

.cost-bar-track {
  height: 24px;
  background: #f5f5f5;
  border-radius: 4px;
  overflow: hidden;
}

.cost-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
}

.cost-bar-expensive { background: #ef4444; }
.cost-bar-hybrid { background: #16a34a; }
.cost-bar-mini { background: #f59e0b; }
.cost-bar-cheap { background: #3b82f6; }

.cost-bar-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 700;
  color: #333;
}

/* Batch estimator */
.batch-estimator {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 20px;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 8px;
  margin-bottom: 16px;
}

.batch-options {
  display: flex;
  gap: 6px;
}

.batch-btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  color: #666;
  cursor: pointer;
  transition: all 0.15s;
}

.batch-btn:hover {
  border-color: #999;
  color: #333;
}

.batch-btn.active {
  background: #000;
  color: #fff;
  border-color: #000;
}

.batch-result {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-left: auto;
}

.batch-label {
  font-size: 14px;
  color: #666;
}

.batch-cost {
  font-family: 'JetBrains Mono', monospace;
  font-size: 24px;
  font-weight: 800;
  color: #16a34a;
}

/* ========================================
   Provider & Preset Tables
   ======================================== */
.provider-table td,
.preset-table td {
  font-size: 13px;
}

.preset-table-wrapper {
  overflow-x: auto;
  margin: 12px 0 20px;
}

/* ========================================
   Preset Selector
   ======================================== */
.preset-selector {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}

.preset-btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: #fff;
  color: #666;
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
}

.preset-btn:hover {
  border-color: #999;
  color: #333;
}

.preset-btn.active {
  background: #000;
  color: #fff;
  border-color: #000;
}

.preset-btn.is-active-preset::after {
  content: '';
  position: absolute;
  top: -2px;
  right: -2px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #16a34a;
}

.preset-btn.active.is-active-preset::after {
  background: #4ade80;
}

.preset-active-dot {
  display: none;
}

.preset-hint {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #999;
  margin-bottom: 16px;
}

.preset-hint code {
  font-size: 12px;
  background: #f5f5f5;
  padding: 1px 5px;
  border-radius: 3px;
  color: #FF4500;
}

/* ========================================
   Documentation Link
   ======================================== */
.docs-link-box {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 24px;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 8px;
  margin: 16px 0;
}

.docs-arrow {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px;
  color: #FF4500;
  font-weight: 700;
}

.docs-link {
  font-family: 'JetBrains Mono', monospace;
  font-size: 15px;
  font-weight: 700;
  color: #FF4500;
  text-decoration: none;
  transition: color 0.15s;
}

.docs-link:hover {
  color: #cc3700;
  text-decoration: underline;
}

.docs-note {
  font-size: 14px;
  color: #999;
}

@media (max-width: 700px) {
  .how-it-works {
    padding: 24px 16px 0;
  }

  .hero-title {
    font-size: 32px;
  }

  .hero-subtitle {
    font-size: 16px;
  }

  .pipeline {
    flex-direction: column;
    gap: 8px;
  }

  .pipeline-arrow {
    transform: rotate(90deg);
    padding: 4px 0;
  }

  .pipeline-card {
    width: 100%;
    flex-direction: row;
    justify-content: flex-start;
    padding: 14px 18px;
    gap: 12px;
  }

  .step-body {
    padding-left: 20px;
  }

  .graph-example {
    flex-direction: column;
    gap: 4px;
  }

  .arch-main-row {
    flex-direction: column;
    gap: 0;
  }

  .arch-connector {
    transform: rotate(90deg);
    padding: 4px 0;
  }

  .section-nav {
    overflow-x: auto;
    flex-wrap: nowrap;
  }

  .section-nav a {
    white-space: nowrap;
    flex-shrink: 0;
  }

  .cost-bar-row {
    grid-template-columns: 100px 1fr 70px;
  }

  .batch-estimator {
    flex-direction: column;
    align-items: flex-start;
  }

  .batch-result {
    margin-left: 0;
  }
}
</style>
