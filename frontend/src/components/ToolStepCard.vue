<template>
  <div class="tool-step">
    <div class="step-head" @click="isOpen = !isOpen">
      <div class="step-icon" :class="type === 'call' ? 'call' : 'result'">
        <svg v-if="type === 'call'" width="10" height="10" viewBox="0 0 16 16" fill="none">
          <path d="M8 3v5l3.5 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
          <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.4"/>
        </svg>
        <svg v-else width="10" height="10" viewBox="0 0 16 16" fill="none">
          <path d="M3 8.5l3 3 7-7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <span class="step-label" :class="type === 'call' ? 'call' : 'result'">{{ label }}</span>
      <span class="step-toggle" :class="{ open: isOpen }">▶</span>
    </div>
    <div class="step-body" v-show="isOpen"><pre>{{ content }}</pre></div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  type: { type: String, required: true },
  content: { type: String, default: '' },
})

const isOpen = ref(false)

const label = computed(() =>
  (props.content ?? '').replace(/^\[도구 (호출|결과)\]\s*/, '').slice(0, 120)
)
</script>

<style scoped>
.tool-step {
  background: var(--surface-2); border: 1px solid var(--border);
  border-radius: var(--r-md); overflow: hidden;
}
.step-head {
  display: flex; align-items: center; gap: 7px;
  padding: 6px 10px; cursor: pointer; user-select: none; transition: background .12s;
}
.step-head:hover { background: #EDEEF2; }
.step-icon {
  width: 20px; height: 20px; border-radius: 5px;
  display: grid; place-items: center; flex-shrink: 0;
}
.step-icon.call   { background: #EDE9FE; color: #6D28D9; }
.step-icon.result { background: var(--success-soft); color: var(--success); }
.step-label {
  flex: 1; font-family: var(--mono); font-size: 11px; font-weight: 600;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.step-label.call   { color: #6D28D9; }
.step-label.result { color: var(--success); }
.step-toggle { font-size: 8px; color: var(--text-4); transition: transform .18s; flex-shrink: 0; }
.step-toggle.open { transform: rotate(90deg); }
.step-body { padding: 0 10px 8px 37px; }
.step-body pre {
  font-family: var(--mono); font-size: 11px; color: var(--text-2);
  line-height: 1.6; white-space: pre-wrap; word-break: break-all;
}
</style>