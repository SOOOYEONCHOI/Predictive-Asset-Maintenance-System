<template>
  <aside class="sidebar">

    <!-- KPI -->
    <div class="sidebar-kpi">
      <div class="kpi-header">
        <div class="status-dot"></div>
        실시간 설비 현황 · LN21
      </div>
      <div class="kpi-grid">
        <div class="kpi-card total">
          <div class="kpi-label">전체</div>
          <div class="kpi-value">{{ dashboard.kpi.total }}<span class="kpi-unit">대</span></div>
        </div>
        <div class="kpi-card ok">
          <div class="kpi-label">정상</div>
          <div class="kpi-value">{{ dashboard.kpi.normal }}<span class="kpi-unit">대</span></div>
        </div>
        <div class="kpi-card warn">
          <div class="kpi-label">주의</div>
          <div class="kpi-value">{{ dashboard.kpi.caution }}<span class="kpi-unit">대</span></div>
        </div>
        <div class="kpi-card crit">
          <div class="kpi-label">경고</div>
          <div class="kpi-value">{{ dashboard.kpi.danger }}<span class="kpi-unit">대</span></div>
        </div>
      </div>

      <!-- 이상 유형 분포 -->
      <div class="fault-dist">
        <div class="fault-dist-label">이상 유형 분포</div>
        <div class="fault-row" v-for="type in ['spike', 'creep', 'drift']" :key="type">
          <span class="fault-tag" :class="type">{{ type.charAt(0).toUpperCase() + type.slice(1) }}</span>
          <div class="fault-bar-track">
            <div class="fault-bar-fill" :class="type" :style="{ width: faultBarWidth(type) + '%' }"></div>
          </div>
          <span class="fault-count">{{ dashboard.faultDistribution[type] }}</span>
        </div>
      </div>
    </div>

    <!-- 설비 미니 현황 -->
    <div class="equip-section">
      <div class="sec-label">설비 현황</div>
      <div class="equip-list">
        <div
          class="equip-row"
          v-for="e in EQUIPMENTS"
          :key="e.id"
          @click="chat.fillInputText(`${e.id} 현재 상태 분석해줘`)"
        >
          <div class="equip-dot" :class="e.status"></div>
          <span class="equip-id">{{ e.id.replace('-CNV01', '') }}</span>
          <span class="equip-val">{{ e.val.toFixed(2) }}</span>
          <span class="equip-badge" :class="e.status">{{ e.badge }}</span>
        </div>
      </div>
    </div>

    <!-- 시나리오 -->
    <div class="scenario-section">
      <div class="sec-label">대표 시나리오</div>
      <div class="scenario-list">
        <button
          class="scenario-btn"
          v-for="s in SCENARIOS"
          :key="s.id"
          @click="chat.fillInputText(s.query)"
        >
          <span class="s-num">{{ s.id }}</span>
          {{ s.label }}
          <span class="s-tag new" v-if="s.id === 4 || s.id === 8">신규</span>
        </button>
      </div>
    </div>

    <!-- 모니터링 -->
    <div class="monitor-section">
      <div class="sec-label" style="margin-bottom:7px">모니터링</div>
      <div class="monitor-row">
        <span class="m-label">추적 백엔드</span>
        <span class="badge badge-ls">LangSmith</span>
      </div>
      <div class="monitor-row">
        <span class="m-label">pm-api</span>
        <span class="badge" :class="dashboard.apiStatus === 'ok' ? 'badge-ok' : 'badge-err'">
          <svg width="5" height="5" viewBox="0 0 6 6"><circle cx="3" cy="3" r="3" fill="currentColor"/></svg>
          {{ dashboard.apiStatus === 'ok' ? '정상' : '오류' }}
        </span>
      </div>
      <div class="monitor-row">
        <span class="m-label">예측 모델</span>
        <span class="mono">ExtraTrees</span>
      </div>
      <div class="monitor-row">
        <span class="m-label">스레드</span>
        <span class="mono">{{ chat.threadId }}</span>
      </div>
    </div>

  </aside>
</template>

<script setup>
import { useChatStore } from '../stores/chat'
import { useDashboardStore } from '../stores/dashboard'
import { EQUIPMENTS, SCENARIOS } from '../constants'

const chat = useChatStore()
const dashboard = useDashboardStore()

function faultBarWidth(type) {
  const dist = dashboard.faultDistribution
  const max = Math.max(dist.spike, dist.creep, dist.drift, 1)
  return (dist[type] / max) * 100
}
</script>

<style scoped>
.sidebar {
  background: var(--surface); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; overflow: hidden;
}

/* KPI 섹션 */
.sidebar-kpi {
  padding: 10px 14px 8px; border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.kpi-header {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; font-weight: 600; color: var(--text-3);
  letter-spacing: .05em; text-transform: uppercase; margin-bottom: 7px;
}
.kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-bottom: 8px; }
.kpi-card {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--r-md); padding: 6px 9px;
}
.kpi-label { font-size: 10.5px; color: var(--text-3); font-weight: 500; margin-bottom: 2px; }
.kpi-value { font-size: 19px; font-weight: 700; line-height: 1; }
.kpi-unit  { font-size: 10.5px; color: var(--text-3); font-weight: 500; margin-left: 2px; }
.kpi-card.total .kpi-value { color: var(--brand); }
.kpi-card.ok    .kpi-value { color: var(--success); }
.kpi-card.warn  .kpi-value { color: var(--warning); }
.kpi-card.crit  .kpi-value { color: var(--danger); }

/* 이상 유형 분포 */
.fault-dist { margin-top: 1px; }
.fault-dist-label { font-size: 10.5px; color: var(--text-4); margin-bottom: 5px; }
.fault-row { display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }
.fault-tag {
  font-size: 10px; font-weight: 600; letter-spacing: .03em;
  padding: 2px 6px; border-radius: 4px; flex-shrink: 0; width: 44px; text-align: center;
}
.fault-tag.spike { background: var(--spike-soft); color: var(--spike); }
.fault-tag.creep { background: var(--creep-soft); color: var(--creep); }
.fault-tag.drift { background: var(--drift-soft); color: var(--drift); }
.fault-bar-track { flex: 1; height: 5px; background: var(--border); border-radius: 3px; overflow: hidden; }
.fault-bar-fill  { height: 100%; border-radius: 3px; transition: width .5s ease; }
.fault-bar-fill.spike { background: var(--spike); }
.fault-bar-fill.creep { background: var(--creep); }
.fault-bar-fill.drift { background: var(--drift); }
.fault-count { font-size: 11px; color: var(--text-3); font-family: var(--mono); min-width: 16px; text-align: right; }

/* 설비 미니 현황 */
.equip-section {
  padding: 8px 14px 6px; border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.sec-label {
  font-size: 10px; font-weight: 600; color: var(--text-4);
  letter-spacing: .05em; text-transform: uppercase; margin-bottom: 5px;
}
.equip-list { display: flex; flex-direction: column; gap: 2px; }
.equip-row {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 7px; border-radius: var(--r-sm);
  background: transparent; transition: background .12s;
  cursor: pointer; border: 1px solid transparent;
}
.equip-row:hover { background: var(--brand-soft); border-color: var(--brand-mid); }
.equip-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.equip-dot.ok   { background: var(--success); }
.equip-dot.warn { background: var(--warning); }
.equip-dot.crit { background: var(--danger); box-shadow: 0 0 0 2px var(--danger-soft); }
.equip-id { font-size: 11px; font-family: var(--mono); color: var(--text-2); flex: 1; }
.equip-val { font-size: 11px; font-family: var(--mono); color: var(--text-3); }
.equip-badge {
  font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; flex-shrink: 0;
}
.equip-badge.ok   { background: var(--success-soft); color: var(--success); }
.equip-badge.warn { background: var(--warning-soft); color: var(--warning); }
.equip-badge.crit { background: var(--danger-soft);  color: var(--danger); }

/* 시나리오 목록 */
.scenario-section {
  padding: 10px 14px 8px; flex: 1; overflow-y: auto; min-height: 0;
}
.scenario-list { display: flex; flex-direction: column; gap: 2px; }
.scenario-btn {
  text-align: left; width: 100%; padding: 8px 10px;
  border: 1px solid transparent; border-radius: var(--r-md);
  background: transparent; font-size: 12px; color: var(--text-2);
  display: flex; align-items: flex-start; gap: 7px;
  line-height: 1.45; transition: all .13s;
}
.scenario-btn:hover { background: var(--brand-soft); color: var(--brand); border-color: var(--brand-mid); }
.s-num {
  flex-shrink: 0; width: 17px; height: 17px; border-radius: 50%;
  background: var(--border); color: var(--text-3);
  font-size: 9px; font-weight: 700; display: grid; place-items: center; margin-top: 1px;
}
.scenario-btn:hover .s-num { background: var(--brand); color: #fff; }
.s-tag {
  flex-shrink: 0; font-size: 9px; padding: 1px 5px; border-radius: 3px; margin-top: 2px; font-weight: 600;
}
.s-tag.new { background: var(--success-soft); color: var(--success); }

/* 모니터링 */
.monitor-section {
  padding: 8px 14px 10px; border-top: 1px solid var(--border); flex-shrink: 0;
}
.monitor-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 3px 0; font-size: 12px; color: var(--text-2);
}
.m-label { color: var(--text-3); font-size: 11px; font-weight: 500; }
.badge {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 7px; border-radius: 999px; font-size: 10px; font-weight: 600;
}
.badge-ok { background: var(--success-soft); color: var(--success); }
.badge-err { background: var(--danger-soft); color: var(--danger); }
.badge-ls { background: #EEF2FF; color: #4338CA; }
.mono { font-family: var(--mono); font-size: 11px; color: var(--text-2); }
</style>