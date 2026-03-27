import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'

const routes = [
  // Predict
  { path: '/', redirect: '/predict' },
  { path: '/predict', name: 'Predict', component: () => import('../views/PredictView.vue') },
  { path: '/predict/:id', name: 'PredictionDetail', component: () => import('../views/PredictionDetailView.vue'), props: true },

  // Trade
  { path: '/trade', name: 'Trade', component: () => import('../views/TradeView.vue') },

  // Research
  { path: '/research/knowledge', name: 'Knowledge', component: () => import('../views/KnowledgeBaseView.vue') },
  { path: '/research/backtest', name: 'Backtest', component: () => import('../views/BacktestView.vue') },
  { path: '/research/decisions', name: 'DecisionLog', component: () => import('../views/DecisionLogView.vue') },
  { path: '/research/how-it-works', name: 'HowItWorks', component: () => import('../views/HowItWorksView.vue') },

  // Legacy redirects
  { path: '/polymarket', redirect: '/predict' },
  { path: '/paper-trading', redirect: '/trade' },
  { path: '/decisions', redirect: '/research/decisions' },
  { path: '/backtest', redirect: '/research/backtest' },
  { path: '/knowledge', redirect: '/research/knowledge' },
  { path: '/how-it-works', redirect: '/research/how-it-works' },
  { path: '/settings', redirect: '/predict' },

  // MiroFish original routes
  { path: '/home', name: 'Home', component: Home },
  { path: '/process/:projectId', name: 'Process', component: Process, props: true },
  { path: '/simulation/:simulationId', name: 'Simulation', component: SimulationView, props: true },
  { path: '/simulation/:simulationId/start', name: 'SimulationRun', component: SimulationRunView, props: true },
  { path: '/report/:reportId', name: 'Report', component: ReportView, props: true },
  { path: '/interaction/:reportId', name: 'Interaction', component: InteractionView, props: true },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
