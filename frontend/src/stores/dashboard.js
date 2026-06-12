import { defineStore } from 'pinia'

const PM_API_BASE = import.meta.env.VITE_PM_API_BASE || 'http://localhost:8000'

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
        const res = await fetch(`${PM_API_BASE}/health`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        await res.json()
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
