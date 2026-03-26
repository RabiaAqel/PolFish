<template>
  <div id="app-shell">
    <!-- Global Navbar -->
    <nav class="global-nav">
      <div class="nav-left">
        <div class="brand-switcher" @click="toggleMode">
          <span class="brand-name">{{ isPolFish ? 'POLFISH' : 'MIROFISH' }}</span>
          <span class="brand-arrow">⇄</span>
        </div>
      </div>
      <div class="nav-links">
        <template v-if="isPolFish">
          <router-link to="/">Predictor</router-link>
          <router-link to="/paper-trading">Paper Trading</router-link>
          <router-link to="/decisions">Decision Log</router-link>
          <router-link to="/backtest">Backtest</router-link>
          <router-link to="/how-it-works">How It Works</router-link>
          <router-link to="/settings">Settings</router-link>
        </template>
        <template v-else>
          <router-link to="/home">Home</router-link>
        </template>
      </div>
    </nav>

    <!-- Main Content -->
    <div class="main-content" :class="{ 'log-collapsed': logMinimized }">
      <router-view />
    </div>

    <!-- Sticky Live Log Panel -->
    <div class="live-log-panel" :class="{ minimized: logMinimized }">
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
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isPolFish = ref(true)

const toggleMode = () => {
  isPolFish.value = !isPolFish.value
  if (isPolFish.value) {
    router.push('/')
  } else {
    router.push('/home')
  }
}

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
        // Keep last 500 entries
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
    logSource.onerror = () => {
      // Will auto-reconnect
    }
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
  justify-content: space-between;
  padding: 0 32px;
  z-index: 1000;
  font-family: 'JetBrains Mono', monospace;
}

.nav-left {
  display: flex;
  align-items: center;
}

.brand-switcher {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  transition: opacity 0.15s;
}

.brand-switcher:hover {
  opacity: 0.8;
}

.brand-switcher:hover .brand-arrow {
  opacity: 1;
  color: #FF4500;
}

.brand-name {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 16px;
  letter-spacing: 2px;
  color: #ffffff;
}

.brand-arrow {
  font-size: 14px;
  color: #666;
  opacity: 0.5;
  transition: all 0.15s;
}

.nav-links {
  display: flex;
  gap: 28px;
}

.nav-links a {
  text-decoration: none;
  color: #888888;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
  transition: color 0.15s;
  padding: 4px 0;
}

.nav-links a:hover {
  color: #cccccc;
}

.nav-links a.router-link-active,
.nav-links a.router-link-exact-active {
  color: #FF4500;
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
</style>
