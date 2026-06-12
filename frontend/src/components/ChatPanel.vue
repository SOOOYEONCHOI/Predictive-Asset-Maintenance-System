<template>
  <div class="chat-panel">

    <!-- 헤더 -->
    <div class="chat-header">
      <div class="agent-info">
        <div class="agent-av">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7H3a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2zM5 18a7.002 7.002 0 0 0 14 0H5z"/>
          </svg>
        </div>
        <div>
          <div class="agent-name">설비 예지보전 진단 에이전트</div>
          <div class="agent-desc">LangGraph ReAct · 13개 도구 · ExtraTrees + 선형 11종 · gpt-4o-mini</div>
        </div>
      </div>
      <div class="hdr-actions">
        <button class="icon-btn" title="대화 초기화" @click="chat.resetChat()">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path d="M3 8a5 5 0 1 0 1.5-3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M3 4.5V8h3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <button
          class="icon-btn stop-btn"
          :class="{ visible: chat.isStreaming }"
          title="응답 중단"
          @click="chat.stopStreaming()"
        >
          <svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor">
            <rect x="2" y="2" width="8" height="8" rx="1"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 스탯바 -->
    <div class="stat-bar">
      <div class="sb-item">스레드 <span class="sb-val sb-mono">{{ chat.threadId }}</span></div>
      <span class="sb-sep">·</span>
      <div class="sb-item">메시지 <span class="sb-val">{{ chat.userMsgCount }}</span>건</div>
      <span class="sb-sep">·</span>
      <div class="sb-item">도구 호출 <span class="sb-val">{{ chat.toolCallCount }}</span>회</div>
    </div>

    <!-- 메시지 목록 -->
    <div class="messages" ref="messagesEl">
      <div class="empty-state" v-if="chat.messages.length === 0">
        <div class="empty-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
            <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7H3a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z" fill="#5B6CF6" opacity=".4"/>
            <path d="M5 18a7.002 7.002 0 0 0 14 0H5z" fill="#5B6CF6" opacity=".2"/>
          </svg>
        </div>
        <p class="empty-title">설비 상태에 대해 자연어로 질문하세요</p>
        <p class="empty-sub">시나리오 버튼을 클릭하거나 직접 입력하세요</p>
        <div class="empty-hints">
          <button class="hint-chip" v-for="h in HINTS" :key="h" @click="chat.fillInputText(h)">{{ h }}</button>
        </div>
      </div>

      <template v-for="msg in chat.messages" :key="msg.id">
        <div class="msg-row user" v-if="msg.role === 'user'">
          <div class="msg-avatar user-av">나</div>
          <div class="msg-body">
            <div class="msg-sender">나 · {{ fmt(msg.time) }}</div>
            <div class="bubble-user">{{ msg.content }}</div>
          </div>
        </div>

        <div class="msg-row agent" v-else>
          <div class="msg-avatar agent-msg-av">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7H3a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2zM5 18a7.002 7.002 0 0 0 14 0H5z"/>
            </svg>
          </div>
          <div class="msg-body" style="min-width:300px;max-width:760px">
            <div class="msg-sender">진단 에이전트 · {{ fmt(msg.time) }}</div>
            <div class="tool-steps" v-if="msg.steps.length">
              <ToolStepCard v-for="(step, i) in msg.steps" :key="i" :type="step.type" :content="step.content" />
            </div>
            <div class="cards-area">
              <FaultTypeCard v-if="msg.faultResult" :result="msg.faultResult" />
              <RULCard v-if="msg.rulResult" :result="msg.rulResult" />
            </div>
            <div class="answer-block">
              <div class="answer-head">
                <div class="answer-head-label">
                  <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                    <path d="M3 8.5l3 3 7-7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  최종 진단 응답
                </div>
                <div class="answer-head-actions">
                  <button
                    class="copy-btn"
                    v-if="msg.workOrder"
                    title="작업 지시서 다운로드"
                    @click="downloadWorkOrder(msg)"
                  >
                    <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                      <path d="M8 2v8m0 0l-3-3m3 3l3-3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                      <path d="M2.5 11.5V13a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-1.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                  <button
                    class="copy-btn"
                    v-if="msg.answer"
                    :title="copiedId === msg.id ? '복사됨' : '복사'"
                    @click="copyAnswer(msg)"
                  >
                    <svg v-if="copiedId !== msg.id" width="12" height="12" viewBox="0 0 16 16" fill="none">
                      <rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
                      <path d="M11 5V3.5A1.5 1.5 0 0 0 9.5 2H3.5A1.5 1.5 0 0 0 2 3.5v6A1.5 1.5 0 0 0 3.5 11H5" stroke="currentColor" stroke-width="1.4"/>
                    </svg>
                    <svg v-else width="12" height="12" viewBox="0 0 16 16" fill="none">
                      <path d="M3 8.5l3 3 7-7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                </div>
              </div>
              <div class="answer-body">
                <div class="typing" v-if="msg.isLoading && !msg.answer">
                  <div class="typing-dots"><span></span><span></span><span></span></div>
                  도구 실행 중...
                </div>
                <div class="md-body" v-if="msg.answer" v-html="renderMarkdown(msg.answer)"></div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 입력 -->
    <div class="input-area">
      <div class="input-wrap" :class="{ focused, streaming: chat.isStreaming }">
        <textarea
          ref="inputEl"
          class="chat-input"
          rows="1"
          v-model="chat.inputText"
          :disabled="chat.isStreaming"
          :placeholder="chat.isStreaming ? '에이전트 응답 중...' : '설비 상태, 이상 원인, 잔여 수명, 작업 지시서 등 자연어로 질문하세요...'"
          @keydown="handleKeydown"
          @input="autoResize"
          @focus="focused = true"
          @blur="focused = false"
        ></textarea>
        <button class="send-btn" :disabled="chat.isStreaming" @click="submit" title="전송 (Enter)">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
            <path d="M13.5 2.5l-12 5 4.5 2 7.5-7zM13.5 2.5l-5 12-2-4.5 7-7.5z"
              stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
      <div class="input-footer">
        <div class="hint-row">
          <button class="hint-chip" v-for="h in HINTS.slice(0, 4)" :key="h" @click="chat.fillInputText(h)">{{ h }}</button>
        </div>
        <span class="input-tip">Enter 전송 · Shift+Enter 줄바꿈</span>
      </div>
    </div>

  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { marked } from 'marked'
import { useChatStore } from '../stores/chat'
import ToolStepCard from './ToolStepCard.vue'
import FaultTypeCard from './FaultTypeCard.vue'
import RULCard from './RULCard.vue'
import { HINTS } from '../constants'

const chat = useChatStore()
const messagesEl = ref(null)
const inputEl = ref(null)
const focused = ref(false)
const copiedId = ref(null)

async function copyAnswer(msg) {
  await navigator.clipboard.writeText(msg.answer)
  copiedId.value = msg.id
  setTimeout(() => {
    if (copiedId.value === msg.id) copiedId.value = null
  }, 1500)
}

function downloadWorkOrder(msg) {
  const blob = new Blob([msg.workOrder], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `작업지시서_${msg.id}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

function fmt(time) {
  return new Intl.DateTimeFormat('ko-KR', { hour: '2-digit', minute: '2-digit' }).format(new Date(time))
}

function renderMarkdown(text) {
  return marked.parse(text, { breaks: true })
}

function scrollBottom() {
  nextTick(() => {
    if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  })
}

function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 110) + 'px'
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}

function submit() {
  const text = chat.inputText.trim()
  if (!text || chat.isStreaming) return
  chat.inputText = ''
  if (inputEl.value) inputEl.value.style.height = 'auto'
  chat.submitMessage(text)
}

watch(() => chat.messages, scrollBottom, { deep: true })
</script>

<style scoped>
.chat-panel {
  display: flex; flex-direction: column; overflow: hidden; background: var(--bg);
}

/* 채팅 헤더 */
.chat-header {
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 11px 22px; display: flex; align-items: center;
  justify-content: space-between; flex-shrink: 0;
}
.agent-info { display: flex; align-items: center; gap: 10px; }
.agent-av {
  width: 34px; height: 34px; border-radius: 9px;
  background: linear-gradient(135deg,#5B6CF6,#8B5CF6);
  display: grid; place-items: center; color: #fff; flex-shrink: 0;
}
.agent-name { font-weight: 700; font-size: 13.5px; }
.agent-desc { font-size: 11.5px; color: var(--text-3); margin-top: 1px; }
.hdr-actions { display: flex; gap: 7px; }
.icon-btn {
  width: 30px; height: 30px; border: 1px solid var(--border-strong);
  border-radius: var(--r-sm); background: var(--surface);
  display: grid; place-items: center; color: var(--text-2); transition: all .13s;
}
.icon-btn:hover { border-color: var(--brand); color: var(--brand); }
.stop-btn { border-color: var(--danger)!important; color: var(--danger)!important; display: none; }
.stop-btn.visible { display: grid; animation: pulse-danger 1.4s ease-in-out infinite; }
@keyframes pulse-danger { 0%,100%{opacity:1} 50%{opacity:.55} }

/* 스탯바 */
.stat-bar {
  padding: 6px 22px; background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 10px;
  font-size: 11px; color: var(--text-3); flex-shrink: 0;
}
.sb-item { display: flex; align-items: center; gap: 4px; }
.sb-val  { color: var(--text-2); font-weight: 500; }
.sb-mono { font-family: var(--mono); font-size: 10.5px; }
.sb-sep  { color: var(--border-strong); }

/* 메시지 목록 */
.messages {
  flex: 1; overflow-y: auto; padding: 20px 22px;
  display: flex; flex-direction: column; gap: 16px;
}

/* 빈 상태 */
.empty-state { margin: auto; text-align: center; max-width: 340px; }
.empty-icon {
  margin: 0 auto 14px; width: 52px; height: 52px; border-radius: 14px;
  background: var(--brand-soft); display: grid; place-items: center;
}
.empty-title { font-weight: 700; font-size: 14.5px; margin-bottom: 5px; }
.empty-sub   { font-size: 12.5px; color: var(--text-3); margin-bottom: 14px; }
.empty-hints { display: flex; flex-wrap: wrap; gap: 5px; justify-content: center; }

/* 메시지 버블 */
.msg-row { display: flex; gap: 10px; align-items: flex-end; }
.msg-row.user { flex-direction: row-reverse; }
.msg-avatar {
  width: 30px; height: 30px; border-radius: 9px; flex-shrink: 0;
  display: grid; place-items: center; font-size: 11.5px; font-weight: 700; color: #fff;
}
.user-av  { background: linear-gradient(135deg,#4A6BB5,#2A3F8F); }
.agent-msg-av { background: linear-gradient(135deg,#5B6CF6,#8B5CF6); }
.msg-body { max-width: 720px; display: flex; flex-direction: column; gap: 4px; }
.msg-row.user .msg-body { align-items: flex-end; }
.msg-sender { font-size: 11px; color: var(--text-3); font-weight: 500; padding: 0 3px; }
.bubble-user {
  background: var(--brand); color: #fff;
  padding: 11px 14px; border-radius: 13px; border-bottom-right-radius: 3px;
  font-size: 13px; line-height: 1.6; max-width: 440px;
  white-space: pre-wrap; word-break: break-word;
}

/* 도구 스텝 */
.tool-steps { display: flex; flex-direction: column; gap: 4px; }

/* 최종 답변 블록 */
.answer-block {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r-lg); border-bottom-left-radius: 3px;
  box-shadow: var(--shadow-sm); overflow: hidden;
}
.answer-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 13px; background: linear-gradient(90deg,#F0F4FF,#F8F9FF);
  border-bottom: 1px solid var(--border);
  font-size: 11.5px; color: var(--brand); font-weight: 600;
}
.answer-head-label { display: flex; align-items: center; gap: 6px; }
.answer-head-actions { display: flex; align-items: center; gap: 2px; }
.copy-btn {
  width: 22px; height: 22px; border: none; background: transparent;
  display: grid; place-items: center; color: var(--text-3);
  border-radius: 5px; transition: all .13s; flex-shrink: 0;
}
.copy-btn:hover { background: var(--brand-soft); color: var(--brand); }
.answer-body { padding: 12px 14px; font-size: 13px; }
.typing { display: flex; align-items: center; gap: 7px; color: var(--text-3); font-size: 12px; }
.typing-dots { display: flex; gap: 3px; }
.typing-dots span {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--text-4); animation: bounce 1.3s ease-in-out infinite;
}
.typing-dots span:nth-child(2) { animation-delay: .18s; }
.typing-dots span:nth-child(3) { animation-delay: .36s; }
@keyframes bounce {
  0%,80%,100%{ transform: translateY(0); background: var(--text-4); }
  40%        { transform: translateY(-4px); background: var(--brand); }
}

/* 마크다운 */
.md-body { line-height: 1.75; color: var(--text-1); }
.md-body :deep(p)  { margin-bottom: 8px; }
.md-body :deep(p:last-child) { margin-bottom: 0; }
.md-body :deep(strong) { font-weight: 700; }
.md-body :deep(em)     { font-style: italic; color: var(--text-2); }
.md-body :deep(code) {
  font-family: var(--mono); font-size: 11.5px;
  background: var(--bg); padding: 1px 5px; border-radius: 4px;
  color: var(--brand-deep);
}
.md-body :deep(ul), .md-body :deep(ol) { padding-left: 18px; margin-bottom: 8px; }
.md-body :deep(li)  { margin-bottom: 3px; }
.md-body :deep(blockquote) {
  border-left: 3px solid var(--border-strong); padding-left: 12px;
  color: var(--text-2); margin: 8px 0;
}
.md-body :deep(h1), .md-body :deep(h2), .md-body :deep(h3) { font-weight: 700; margin-bottom: 6px; color: var(--text-1); }
.md-body :deep(h2) { font-size: 14px; padding-bottom: 4px; border-bottom: 1px solid var(--border); }
.md-body :deep(h3) { font-size: 13px; }
.md-body :deep(table) { width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 12.5px; }
.md-body :deep(th), .md-body :deep(td) { padding: 5px 9px; border: 1px solid var(--border); text-align: left; }
.md-body :deep(th) { background: var(--bg); font-weight: 600; }
.md-body :deep(pre) {
  background: #1E2433; color: #E2E8F0; border-radius: var(--r-md);
  padding: 12px 14px; overflow-x: auto; margin-bottom: 8px;
}
.md-body :deep(pre code) { background: transparent; color: inherit; padding: 0; }

/* ── 입력 영역 ── */
.input-area {
  border-top: 1px solid var(--border); background: var(--surface);
  padding: 12px 22px; flex-shrink: 0;
}
.input-wrap {
  display: flex; gap: 9px; background: var(--surface-2);
  border: 1px solid var(--border-strong); border-radius: 12px;
  padding: 8px 12px; transition: border-color .14s, box-shadow .14s;
}
.input-wrap.focused { border-color: var(--brand); box-shadow: 0 0 0 3px rgba(26,86,214,.09); }
.input-wrap.streaming { opacity: .7; }
.chat-input {
  flex: 1; border: none; outline: none; background: transparent;
  font-family: inherit; font-size: 13px; color: var(--text-1);
  resize: none; line-height: 1.5; max-height: 110px; min-height: 22px;
}
.chat-input::placeholder { color: var(--text-4); }
.chat-input:disabled { cursor: not-allowed; }
.send-btn {
  width: 32px; height: 32px; background: var(--brand); color: #fff;
  border: none; border-radius: 7px; display: grid; place-items: center;
  flex-shrink: 0; align-self: flex-end; transition: background .13s, transform .1s;
}
.send-btn:hover:not(:disabled) { background: var(--brand-deep); }
.send-btn:active:not(:disabled){ transform: scale(0.94); }
.send-btn:disabled { background: var(--text-4); cursor: not-allowed; }
.input-footer {
  display: flex; align-items: center; justify-content: space-between; margin-top: 6px;
}
.hint-row { display: flex; gap: 5px; flex-wrap: wrap; }
.hint-chip {
  padding: 3px 9px; border: 1px solid var(--border); border-radius: 999px;
  background: var(--surface); font-size: 11px; color: var(--text-3); transition: all .13s;
}
.hint-chip:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }
.input-tip { font-size: 11px; color: var(--text-4); flex-shrink: 0; }
</style>