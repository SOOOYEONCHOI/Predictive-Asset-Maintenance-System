<template>
  <div class="result-card">
    <div class="card-head rul-card-head">
      <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.3"/>
        <path d="M8 5v3.5l2.5 1.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
      </svg>
      잔여 수명(RUL) 예측
    </div>
    <div class="card-body">
      <div class="rul-main">
        <div class="rul-number-wrap">
          <div class="rul-number" :class="urgencyClass">{{ result.rul_days }}</div>
          <div class="rul-days-label">예상 잔여 가동일</div>
        </div>
        <div class="rul-detail">
          <div class="rul-detail-row">
            <span class="rul-dk">권고 정비일</span>
            <span class="rul-dv" :class="urgencyClass">{{ maintDate }} ({{ result.rul_days - 2 }}일 여유)</span>
          </div>
          <div class="rul-detail-row">
            <span class="rul-dk">예측 신뢰도</span>
            <span class="rul-dv">{{ confPercent }}%</span>
          </div>
          <div class="rul-detail-row" v-if="result.historical_reference">
            <span class="rul-dk">과거 이력</span>
            <span class="rul-dv" style="font-size:11px">{{ result.historical_reference }}</span>
          </div>
        </div>
      </div>
      <div class="rul-gauge">
        <div class="rul-gauge-track">
          <div class="rul-gauge-fill" :style="{ width: gaugePct + '%', background: gaugeColor }"></div>
        </div>
      </div>
      <div class="rul-basis">{{ result.basis || 'VEL 증가 추세 기반 UCL 도달 예상일 추정' }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  result: { type: Object, required: true },
})

const urgencyClass = computed(() => {
  const days = props.result.rul_days
  return days <= 3 ? 'danger' : days <= 7 ? 'warn' : 'safe'
})

const gaugeColor = computed(() => {
  if (urgencyClass.value === 'danger') return 'var(--danger)'
  if (urgencyClass.value === 'warn') return 'var(--warning)'
  return 'var(--success)'
})

const gaugePct = computed(() =>
  Math.max(4, Math.min(100, (props.result.rul_days / 30) * 100))
)

const confPercent = computed(() => Math.round((props.result.confidence || 0) * 100))

const maintDate = computed(() => {
  if (props.result.recommended_maintenance_date) return props.result.recommended_maintenance_date
  const date = new Date()
  date.setDate(date.getDate() + (props.result.rul_days - 2))
  return `${date.getMonth() + 1}/${date.getDate()}`
})
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

.rul-card-head { background: linear-gradient(90deg,var(--brand-soft),var(--surface-2)); color: var(--brand); }
.rul-main { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.rul-number-wrap { flex-shrink: 0; text-align: center; }
.rul-number { font-size: 46px; font-weight: 700; line-height: 1; font-family: var(--mono); }
.rul-number.safe   { color: var(--success); }
.rul-number.warn   { color: var(--warning); }
.rul-number.danger { color: var(--danger); }
.rul-days-label  { font-size: 11px; color: var(--text-3); margin-top: 2px; }
.rul-detail { flex: 1; }
.rul-detail-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 4px 0; border-bottom: 1px solid var(--border); font-size: 12px;
}
.rul-detail-row:last-child { border-bottom: none; }
.rul-dk { color: var(--text-3); }
.rul-dv { font-weight: 500; color: var(--text-1); }
.rul-dv.danger { color: var(--danger); }
.rul-dv.warn   { color: var(--warning); }
.rul-gauge { margin-bottom: 10px; }
.rul-gauge-track { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.rul-gauge-fill { height: 100%; border-radius: 4px; transition: width .6s ease; }
.rul-basis {
  font-size: 11.5px; color: var(--text-3); line-height: 1.5;
  background: var(--bg); border-radius: var(--r-sm); padding: 7px 9px;
}
</style>