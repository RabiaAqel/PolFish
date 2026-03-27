<template>
  <div id="app-shell">
    <!-- Global Navbar -->
    <nav class="global-nav">
      <div class="nav-left">
        <router-link to="/predict" class="brand-logo">POLFISH</router-link>
      </div>

      <!-- Desktop Nav -->
      <div class="nav-center" v-if="isPolFish">
        <router-link to="/predict" class="nav-link" :class="{ active: route.path.startsWith('/predict') }">Predict</router-link>
        <router-link to="/trade" class="nav-link" :class="{ active: route.path === '/trade' }">
          Trade <span class="nav-badge">PAPER</span>
        </router-link>
        <div class="nav-dropdown" @mouseenter="researchOpen = true" @mouseleave="researchOpen = false">
          <button class="nav-link dropdown-trigger" :class="{ active: route.path.startsWith('/research') }">
            Research <span class="dropdown-caret">&#9662;</span>
          </button>
          <div v-show="researchOpen" class="dropdown-menu">
            <router-link to="/research/knowledge" class="dropdown-item" @click="researchOpen = false">Knowledge Base</router-link>
            <router-link to="/research/backtest" class="dropdown-item" @click="researchOpen = false">Backtest Lab</router-link>
            <router-link to="/research/decisions" class="dropdown-item" @click="researchOpen = false">Decision Log</router-link>
          </div>
        </div>
      </div>
      <div class="nav-center" v-else>
        <router-link to="/home" class="nav-link">Home</router-link>
      </div>

      <div class="nav-right">
        <button class="nav-icon-btn" @click="showSettings = true" title="Settings">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </button>
        <div class="nav-dropdown help-dropdown" @mouseenter="helpOpen = true" @mouseleave="helpOpen = false">
          <button class="nav-icon-btn" title="Help">?</button>
          <div v-show="helpOpen" class="dropdown-menu dropdown-right">
            <router-link to="/research/how-it-works" class="dropdown-item" @click="helpOpen = false">How It Works</router-link>
            <a href="https://github.com/mirofish" target="_blank" rel="noopener" class="dropdown-item" @click="helpOpen = false">Documentation</a>
            <div class="dropdown-divider"></div>
            <div class="dropdown-item dropdown-info">Keyboard Shortcuts: coming soon</div>
          </div>
        </div>
        <div class="brand-switcher" @click="toggleMode" title="Switch to MiroFish">
          <span class="brand-arrow">&#8652;</span>
        </div>
      </div>

      <!-- Mobile hamburger -->
      <button class="hamburger" @click="mobileMenuOpen = !mobileMenuOpen" v-if="isPolFish">
        <span></span><span></span><span></span>
      </button>
    </nav>

    <!-- Mobile Menu -->
    <div v-if="mobileMenuOpen && isPolFish" class="mobile-menu">
      <router-link to="/predict" class="mobile-link" @click="mobileMenuOpen = false">Predict</router-link>
      <router-link to="/trade" class="mobile-link" @click="mobileMenuOpen = false">Trade</router-link>
      <div class="mobile-divider"></div>
      <div class="mobile-label">Research</div>
      <router-link to="/research/knowledge" class="mobile-link mobile-sub" @click="mobileMenuOpen = false">Knowledge Base</router-link>
      <router-link to="/research/backtest" class="mobile-link mobile-sub" @click="mobileMenuOpen = false">Backtest Lab</router-link>
      <router-link to="/research/decisions" class="mobile-link mobile-sub" @click="mobileMenuOpen = false">Decision Log</router-link>
      <div class="mobile-divider"></div>
      <button class="mobile-link" @click="showSettings = true; mobileMenuOpen = false">Settings</button>
    </div>

    <!-- Main Content -->
    <div class="main-content" :class="{ 'log-collapsed': logMinimized || !showLogs }">
      <router-view />
    </div>

    <!-- Sticky Live Log Panel (contextual) -->
    <div v-if="showLogs" class="live-log-panel" :class="{ minimized: logMinimized }">
      <div class="log-header" @click="logMinimized = !logMinimized">
        <span class="log-dot" :class="{ active: logEntries.length > 0 }"></span>
        <span>Live Logs</span>
        <span class="log-toggle">{{ logMinimized ? '\u25B2' : '\u25BC' }}</span>
      </div>
      <div v-if="!logMinimized" class="log-body" ref="logBody">
        <div v-if="logEntries.length === 0" class="log-empty">No log entries yet.</div>
        <div v-for="(entry, i) in logEntries" :key="i" class="log-entry" :class="'log-' + entry.level">
          <span class="log-time">{{ formatLogTime(entry.ts) }}</span>
          <span class="log-msg">{{ entry.msg }}</span>
        </div>
      </div>
    </div>

    <!-- Settings Panel -->
    <SettingsPanel v-if="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import SettingsPanel from './components/SettingsPanel.vue'

const router = useRouter()
const route = useRoute()
const isPolFish = ref(true)

const toggleMode = () => {
  isPolFish.value = !isPolFish.value
  if (isPolFish.value) {
    router.push('/predict')
  } else {
    router.push('/home')
  }
}

// Nav state
const researchOpen = ref(false)
const helpOpen = ref(false)
const mobileMenuOpen = ref(false)
const showSettings = ref(false)

// Contextual log visibility
const showLogs = computed(() => {
  const path = route.path
  return path.startsWith('/predict') ||
         path === '/trade' ||
         path === '/research/backtest'
})

const logMinimized = ref(false)
const logEntries = ref([])
const logBody = ref(null)
let logSource = null

const formatLogTime = (ts) => {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const startLogStream = () => {
  if (logSource) return
  try {
    logSource = new EventSource('/api/polymarket/logs/stream')
    logSource.onmessage = (event) => {
      try {
        const entry = JSON.parse(event.data)
        logEntries.value.push(entry)
        if (logEntries.value.length > 500) {
          logEntries.value = logEntries.value.slice(-500)
        }
        nextTick(() => {
          if (logBody.value) {
            logBody.value.scrollTop = logBody.value.scrollHeight
          }
        })
      } catch { /* ignore parse errors */ }
    }
    logSource.onerror = () => { /* Will auto-reconnect */ }
  } catch { /* ignore connection errors */ }
}

const stopLogStream = () => {
  if (logSource) {
    logSource.close()
    logSource = null
  }
}

onMounted(() => {
  startLogStream()
})

onUnmounted(() => {
  stopLogStream()
})
</script>

<style>
/* Global styles reset */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: 'JetBrains Mono', 'Space Grotesk', 'Noto Sans SC', monospace;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #000000;
  background-color: #ffffff;
}

/* Scrollbar styles */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #000000;
}

::-webkit-scrollbar-thumb:hover {
  background: #333333;
}

/* Global button styles */
button {
  font-family: inherit;
}
</style>

<style scoped>
/* ========================================
   Global Navbar
   ======================================== */
.global-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: #000000;
  color: #ffffff;
  display: flex;
  align-items: center;
  padding: 0 24px;
  z-index: 1000;
  font-family: 'JetBrains Mono', monospace;
  gap: 0;
}

.nav-left {
  display: flex;
  align-items: center;
  margin-right: 32px;
}

.brand-logo {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 16px;
  letter-spacing: 2px;
  color: #ffffff;
  text-decoration: none;
  transition: color 0.15s;
}

.brand-logo:hover {
  color: #FF4500;
}

/* Center nav links */
.nav-center {
  display: flex;
  align-items: center;
  gap: 0;
  flex: 1;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  text-decoration: none;
  color: #888888;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
  transition: color 0.15s;
  padding: 16px 16px;
  height: 56px;
  border: none;
  background: none;
  cursor: pointer;
  font-family: 'JetBrains Mono', monospace;
  white-space: nowrap;
}

.nav-link:hover {
  color: #cccccc;
}

.nav-link.active,
.nav-link.router-link-active {
  color: #FF4500;
}

.nav-badge {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 1px 5px;
  background: #FF4500;
  color: #fff;
  border-radius: 2px;
  line-height: 1.2;
}

/* Research dropdown */
.nav-dropdown {
  position: relative;
}

.dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
}

.dropdown-caret {
  font-size: 8px;
  transition: transform 0.15s;
}

.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 200px;
  background: #1a1a1a;
  border: 1px solid #333;
  padding: 4px 0;
  z-index: 1100;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
}

.dropdown-menu.dropdown-right {
  left: auto;
  right: 0;
}

.dropdown-item {
  display: block;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 500;
  color: #ccc;
  text-decoration: none;
  transition: all 0.1s;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
}

.dropdown-item:hover {
  background: #333;
  color: #fff;
}

.dropdown-item.router-link-active {
  color: #FF4500;
}

.dropdown-divider {
  height: 1px;
  background: #333;
  margin: 4px 0;
}

.dropdown-info {
  color: #666;
  font-size: 11px;
  cursor: default;
}

.dropdown-info:hover {
  background: transparent;
  color: #666;
}

/* Right icons */
.nav-right {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.nav-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: none;
  border: none;
  cursor: pointer;
  color: #888;
  font-size: 16px;
  font-weight: 700;
  border-radius: 4px;
  transition: all 0.15s;
  font-family: 'JetBrains Mono', monospace;
}

.nav-icon-btn:hover {
  color: #fff;
  background: #333;
}

.brand-switcher {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.15s;
}

.brand-switcher:hover {
  background: #333;
}

.brand-switcher:hover .brand-arrow {
  color: #FF4500;
}

.brand-arrow {
  font-size: 16px;
  color: #666;
  transition: color 0.15s;
}

/* Hamburger */
.hamburger {
  display: none;
  flex-direction: column;
  gap: 4px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  margin-left: 8px;
}

.hamburger span {
  display: block;
  width: 20px;
  height: 2px;
  background: #fff;
  border-radius: 1px;
}

/* Mobile menu */
.mobile-menu {
  position: fixed;
  top: 56px;
  left: 0;
  right: 0;
  background: #111;
  z-index: 999;
  padding: 8px 0;
  border-bottom: 1px solid #333;
  display: none;
}

.mobile-link {
  display: block;
  padding: 12px 24px;
  color: #ccc;
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 600;
  transition: background 0.1s;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  cursor: pointer;
}

.mobile-link:hover {
  background: #222;
  color: #fff;
}

.mobile-link.router-link-active {
  color: #FF4500;
}

.mobile-sub {
  padding-left: 40px;
  font-size: 12px;
}

.mobile-divider {
  height: 1px;
  background: #333;
  margin: 4px 16px;
}

.mobile-label {
  padding: 8px 24px 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  font-weight: 700;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ========================================
   Main Content Area
   ======================================== */
.main-content {
  padding-top: 56px;
  padding-bottom: 25vh;
  min-height: 100vh;
}

.main-content.log-collapsed {
  padding-bottom: 40px;
}

/* ========================================
   Sticky Live Log Panel
   ======================================== */
.live-log-panel {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 25vh;
  background: #1a1a1a;
  border-top: 2px solid #333;
  z-index: 999;
  display: flex;
  flex-direction: column;
  font-family: 'JetBrains Mono', monospace;
}

.live-log-panel.minimized {
  height: 40px;
}

.log-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  cursor: pointer;
  user-select: none;
  background: #111111;
  color: #999999;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.log-header:hover {
  background: #1a1a1a;
}

.log-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #444444;
  flex-shrink: 0;
}

.log-dot.active {
  background: #00ff00;
  box-shadow: 0 0 6px #00ff00;
  animation: logPulse 1.5s ease-in-out infinite;
}

@keyframes logPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.log-toggle {
  margin-left: auto;
  font-size: 10px;
  color: #666;
}

.log-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 20px;
}

.log-body::-webkit-scrollbar {
  width: 4px;
}

.log-body::-webkit-scrollbar-thumb {
  background: #333;
  border-radius: 2px;
}

.log-entry {
  display: flex;
  gap: 12px;
  padding: 2px 0;
  font-size: 12px;
  line-height: 1.6;
  color: #aaaaaa;
}

.log-time {
  color: #555555;
  flex-shrink: 0;
}

.log-msg {
  word-break: break-word;
}

.log-info .log-msg { color: #aaaaaa; }
.log-success .log-msg { color: #4ade80; }
.log-warn .log-msg { color: #fbbf24; }
.log-error .log-msg { color: #f87171; }

.log-empty {
  color: #555555;
  font-style: italic;
  font-size: 12px;
  padding: 8px 0;
}

/* ========================================
   Responsive
   ======================================== */
@media (max-width: 768px) {
  .nav-center {
    display: none;
  }

  .nav-right .nav-icon-btn,
  .nav-right .brand-switcher,
  .help-dropdown {
    display: none;
  }

  .hamburger {
    display: flex;
  }

  .mobile-menu {
    display: block;
  }
}
</style>
