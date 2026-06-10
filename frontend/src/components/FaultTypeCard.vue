<template>
  <div class="result-card">
    <div class="card-head fault-card-head" :class="faultClass">
      <span>{{ icons[faultClass] || '⚠' }}</span>
      <span>이상 유형 분류 결과</span>
      <span class="fault-type-badge" :class="faultClass">{{ result.fault_type }} · {{ labels[faultClass] || '이상' }}</span>
    </div>
    <div class="card-body">
      <div class="fault-meta">
        <div class="fault-meta-item">
          <div class="fm-label">이상 유형</div>
          <div class="fm-value">{{ result.fault_type }} ({{ labels[faultClass] || '이상' }})</div>
        </div>
        <div class="fault-meta-item">
          <div class="fm-label">신뢰도</div>
          <div class="fm-value">{{ confPercent }}%</div>
        </div>
      </div>
      <div class="conf-bar-wrap">
        <div class="conf-label"><span>분류 신뢰도</span><span>{{ confPercent }}%</span></div>
        <div class="conf-track">
          <div class="conf-fill" :style="{ width: confPercent + '%', background: `var(--${faultClass})` }"></div>
        </div>
      </div>
      <div class="evidence-list" v-if="evidenceList.length">
        <div class="ev-item" v-for="(e, i) in evidenceList" :key="i">
          <div class="ev-dot"></div>
          <span>{{ e }}</span>
        </div>
      </div>
      <div class="fault-action" :class="faultClass">
        권고 조치: {{ actions[faultClass] || result.recommended_action || '현장 점검 필요' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: { type: Object, required: true },
})

const icons = { spike: '⚡', creep: '📈', drift: '🌊' }
const labels = { spike: '급격형', creep: '점진형', drift: '누적형' }
const actions = {
  spike: '즉시 가동 중단 및 이물질·충격 원인 현장 점검',
  creep: '베어링 윤활 상태 확인 및 정밀 진단 예약',
  drift: '구조 이완·열변형 여부 확인, 정밀 측정 실시',
}

const faultClass = computed(() => (props.result.fault_type || '').toLowerCase())
const confPercent = computed(() => Math.round((props.result.confidence || 0) * 100))
const evidenceList = computed(() => (props.result.evidence || []).slice(0, 3))
</script>

<style scoped>
.result-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-lg); border-bottom-left-radius: 3px;
  overflow: hidden; box-shadow: var(--shadow-sm); margin-top: 4px;
}
.card-head {
  display: flex; align-items: center; gap: 7px;
  padding: 8px 13px; border-bottom: 1px solid var(--border);
  font-size: 11.5px; font-weight: 600;
}
.card-body { padding: 12px 14px; }

.fault-card-head { background: linear-gradient(90deg,#FAF0FE,#F8F9FF); color: #6D28D9; }
.fault-card-head.spike { background: linear-gradient(90deg,var(--spike-soft),#FFF5F5); color: var(--spike); }
.fault-card-head.creep { background: linear-gradient(90deg,var(--creep-soft),#FFFBF0); color: var(--creep); }
.fault-card-head.drift { background: linear-gradient(90deg,var(--drift-soft),#F0F5FF); color: var(--drift); }
.fault-type-badge {
  padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 700;
  letter-spacing: .03em;
}
.fault-type-badge.spike { background: var(--spike); color: #fff; }
.fault-type-badge.creep { background: var(--creep); color: #fff; }
.fault-type-badge.drift { background: var(--drift); color: #fff; }
.fault-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
.fault-meta-item { background: var(--bg); border-radius: var(--r-sm); padding: 7px 9px; }
.fm-label { font-size: 10px; color: var(--text-3); font-weight: 500; margin-bottom: 2px; }
.fm-value { font-size: 13px; font-weight: 600; color: var(--text-1); }
.conf-bar-wrap { margin-bottom: 8px; }
.conf-label { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px; }
.conf-label span:first-child { color: var(--text-3); }
.conf-label span:last-child  { font-weight: 600; color: var(--text-1); }
.conf-track { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
.conf-fill  { height: 100%; border-radius: 3px; transition: width .5s ease; }
.evidence-list { display: flex; flex-direction: column; gap: 4px; }
.ev-item {
  display: flex; align-items: flex-start; gap: 6px;
  font-size: 11.5px; color: var(--text-2); line-height: 1.5;
}
.ev-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--text-4); flex-shrink: 0; margin-top: 5px; }
.fault-action {
  margin-top: 10px; padding: 8px 10px; border-radius: var(--r-sm);
  font-size: 11.5px; line-height: 1.5; font-weight: 500;
}
.fault-action.spike { background: var(--spike-soft); color: var(--spike); }
.fault-action.creep { background: var(--creep-soft); color: var(--creep); }
.fault-action.drift { background: var(--drift-soft); color: var(--drift); }
</style>