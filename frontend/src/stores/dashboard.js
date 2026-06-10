import { defineStore } from 'pinia'

const API_BASE = 'http://localhost:8001'

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    kpi: { total: 6, normal: 3, caution: 2, danger: 1 },
    faultDistribution: { spike: 3, creep: 2, drift: 1 },
    apiStatus: 'checking',
    lastUpdated: null,
    _pollTimer: null,
  }),

  actions: {
    async fetchKPI() {
      try {
        const res = await fetch(`${API_BASE}/predict/batch`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        this.kpi = data.kpi
        this.faultDistribution = data.faultDistribution
        this.apiStatus = 'ok'
        this.lastUpdated = Date.now()
      } catch {
        this.apiStatus = 'error'
      }
    },

    startPolling(intervalMs = 30000) {
      this.fetchKPI()
      if (this._pollTimer) clearInterval(this._pollTimer)
      this._pollTimer = setInterval(() => this.fetchKPI(), intervalMs)
    },
  },
})