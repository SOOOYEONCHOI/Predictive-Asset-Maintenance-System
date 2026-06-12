<template>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <div class="brand-icon">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M8 1.5A6.5 6.5 0 0 0 1.5 8a6.5 6.5 0 0 0 6.5 6.5A6.5 6.5 0 0 0 14.5 8 6.5 6.5 0 0 0 8 1.5z" stroke="#fff" stroke-width="1.2"/>
            <path d="M5.5 8.5l1.8 1.8 3.2-3.6" stroke="#fff" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <span class="brand-name">LN21 예지보전</span>
        <span class="brand-sub">Predictive Maintenance Agent</span>
      </div>
      <div class="topbar-right">
        <nav class="nav-links">
          <span>대시보드</span>
          <span>설비 진단</span>
          <span>모델 관리</span>
          <span class="active">AI 에이전트</span>
          <span>설정</span>
        </nav>
        <div class="topbar-status">
          <div class="status-dot"></div>
          <span>시스템 정상</span>
        </div>
        <div class="avatar">관</div>
      </div>
    </header>

    <div class="main">
      <SidebarPanel />
      <ChatPanel />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import SidebarPanel from './components/SidebarPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import { useDashboardStore } from './stores/dashboard'

const dashboardStore = useDashboardStore()

onMounted(() => {
  dashboardStore.startPolling()
})
</script>

<style>
:root {
  --bg:            #FAF7F3;
  --surface:       #FFFFFF;
  --surface-2:     #F7F1EC;
  --border:        #E8E1D8;
  --border-strong: #D6CCC0;
  --text-1:        #2B2724;
  --text-2:        #5C5650;
  --text-3:        #8C8479;
  --text-4:        #BDB6AC;
  --brand:         #3D695F;
  --brand-deep:    #294B43;
  --brand-soft:    #E9F0EE;
  --brand-mid:     #B9D0C8;
  --success:       #4F8270;
  --success-soft:  #E5EFE9;
  --warning:       #C57A47;
  --warning-soft:  #F3E4D8;
  --danger:        #B5453A;
  --danger-soft:   #F5E2DD;
  --spike:         #B5453A;
  --spike-soft:    #F5E2DD;
  --creep:         #C57A47;
  --creep-soft:    #F3E4D8;
  --drift:         #3D695F;
  --drift-soft:    #E9F0EE;
  --shadow-sm: 0 1px 3px rgba(43,39,36,.05), 0 1px 2px rgba(43,39,36,.03);
  --shadow-md: 0 4px 16px rgba(43,39,36,.07), 0 1px 3px rgba(43,39,36,.04);
  --r-sm: 6px;
  --r-md: 10px;
  --r-lg: 14px;
  --mono: 'JetBrains Mono','SF Mono',Consolas,monospace;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; overflow: hidden; }
body {
  font-family: -apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',
    'Segoe UI',Roboto,'Noto Sans KR',sans-serif;
  font-size: 13.5px; color: var(--text-1); background: var(--bg);
  -webkit-font-smoothing: antialiased; letter-spacing: -0.01em;
}
button { cursor: pointer; font-family: inherit; border: none; }
a { text-decoration: none; color: inherit; }
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }

#app, .app { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

.topbar {
  height: 56px; background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 24px;
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0; z-index: 50;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-icon {
  width: 28px; height: 28px; border-radius: 7px;
  background: linear-gradient(135deg, var(--brand), var(--brand-deep));
  display: grid; place-items: center; color: #fff; flex-shrink: 0;
}
.brand-name {
  font-weight: 700; font-size: 15px; letter-spacing: -.02em; color: var(--text-1);
}
.brand-sub { font-size: 12px; color: var(--text-3); font-weight: 400; margin-left: 6px; }
.topbar-right { display: flex; align-items: center; gap: 20px; }
.nav-links { display: flex; gap: 20px; font-size: 13px; color: var(--text-3); }
.nav-links span { cursor: pointer; transition: color .15s; }
.nav-links span:hover { color: var(--text-1); }
.nav-links .active { color: var(--brand); font-weight: 600; }
.topbar-status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-3); }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--success); animation: pulse 2.5s ease-in-out infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.45} }
.avatar {
  width: 30px; height: 30px; border-radius: 50%;
  background: linear-gradient(135deg,var(--brand),var(--brand-deep));
  color: #fff; font-size: 12px; font-weight: 700;
  display: grid; place-items: center;
}

.main { display: grid; grid-template-columns: 260px 1fr; flex: 1; height: 100%; overflow: hidden; min-height: 0; }
</style>
