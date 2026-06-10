import { defineStore } from 'pinia'

const API_BASE = 'http://localhost:8001'

function generateId() {
  return crypto.randomUUID().replace(/-/g, '').slice(0, 12)
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    threadId: generateId(),
    messages: [],
    isStreaming: false,
    toolCallCount: 0,
    abortController: null,
    inputText: '',
  }),

  getters: {
    userMsgCount: (state) => state.messages.filter((m) => m.role === 'user').length,
  },

  actions: {
    fillInputText(text) {
      this.inputText = text
    },

    addUserMessage(text) {
      this.messages.push({
        id: generateId(),
        role: 'user',
        content: text,
        time: Date.now(),
      })
    },

    addAgentMessage() {
      const msg = {
        id: generateId(),
        role: 'agent',
        answer: '',
        steps: [],
        faultResult: null,
        rulResult: null,
        isLoading: true,
        time: Date.now(),
      }
      this.messages.push(msg)
      return msg
    },

    handleSSEEvent(msgId, event) {
      const msg = this.messages.find((m) => m.id === msgId)
      if (!msg) return

      switch (event.type) {
        case 'tool_call':
          msg.steps.push({ type: 'call', content: event.content })
          this.toolCallCount++
          break
        case 'tool_result':
          msg.steps.push({ type: 'result', content: event.content })
          break
        case 'fault_card':
          msg.faultResult = event.content
          break
        case 'rul_card':
          msg.rulResult = event.content
          break
        case 'answer':
          msg.isLoading = false
          msg.answer += event.content
          break
        case 'error':
          msg.isLoading = false
          msg.answer = `오류: ${event.content}`
          break
        case 'done':
          break
      }
    },

    async submitMessage(text) {
      if (!text || this.isStreaming) return

      this.addUserMessage(text)
      const agentMsg = this.addAgentMessage()

      this.isStreaming = true
      this.abortController = new AbortController()

      try {
        const res = await fetch(`${API_BASE}/chat/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, thread_id: this.threadId }),
          signal: this.abortController.signal,
        })
        if (!res.ok) {
          agentMsg.answer = `HTTP 오류 ${res.status}`
          return
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buf = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const blocks = buf.split('\n\n')
          buf = blocks.pop() ?? ''
          for (const block of blocks) {
            for (const line of block.split('\n')) {
              if (!line.startsWith('data: ')) continue
              const raw = line.slice(6).trim()
              if (!raw) continue
              try {
                const ev = JSON.parse(raw)
                this.handleSSEEvent(agentMsg.id, ev)
                if (ev.type === 'done') return
              } catch {
                /* ignore malformed SSE chunks */
              }
            }
          }
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          agentMsg.answer = `연결 오류: ${err.message}`
        }
      } finally {
        agentMsg.isLoading = false
        this.isStreaming = false
        this.abortController = null
      }
    },

    stopStreaming() {
      this.abortController?.abort()
    },

    resetChat() {
      if (this.isStreaming) this.stopStreaming()
      this.threadId = generateId()
      this.messages = []
      this.toolCallCount = 0
    },
  },
})