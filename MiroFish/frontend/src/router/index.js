import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Process from '../views/MainView.vue'
import SimulationView from '../views/SimulationView.vue'
import SimulationRunView from '../views/SimulationRunView.vue'
import ReportView from '../views/ReportView.vue'
import InteractionView from '../views/InteractionView.vue'

const routes = [
  {
    path: '/',
    name: 'Polymarket',
    component: () => import('../views/PolymarketView.vue')
  },
  {
    path: '/home',
    name: 'Home',
    component: Home
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: Process,
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: SimulationView,
    props: true
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: SimulationRunView,
    props: true
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: ReportView,
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: InteractionView,
    props: true
  },
  {
    path: '/polymarket',
    name: 'PolymarketLegacy',
    redirect: '/'
  },
  {
    path: '/paper-trading',
    name: 'PaperTrading',
    component: () => import('../views/PaperTradingView.vue')
  },
  {
    path: '/decisions',
    name: 'DecisionLog',
    component: () => import('../views/DecisionLogView.vue')
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('../views/BacktestView.vue')
  },
  {
    path: '/how-it-works',
    name: 'HowItWorks',
    component: () => import('../views/HowItWorksView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
