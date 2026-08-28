/* ============================================================
   AGENT STORE —— POST /api/agent/chat（SSE 真流式）
   后端流式推送：tool 事件（真实工具执行）+ token 事件（LLM 增量）
   + done/error。前端实时渲染，不再本地模拟/猜测工具调用。
   ============================================================ */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { chatStream, type ChatStreamHandle } from '@/api/agent'
import {
  MOCK_MAX_CHARS,
  MOCK_MAX_HISTORY,
  mockHistory,
  mockInitialMessages,
  QUICK_ACTIONS,
} from '@/mock/data'
import type { ChatMessage } from '@/types'

export interface ActiveTool {
  name: string
  status: 'calling' | 'done'
}

export const useAgentStore = defineStore('agent', () => {
  /* ---------- state ---------- */
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  /** 等待后端首帧（工具事件或 token）中 */
  const isWaiting = ref(false)
  const history = ref<ChatMessage[]>([])
  const activeTool = ref<ActiveTool | null>(null)
  const replyBuffer = ref('')
  const maxChars = ref(MOCK_MAX_CHARS)
  const maxHistory = ref(MOCK_MAX_HISTORY)
  const quickActions = ref(QUICK_ACTIONS)
  let streamHandle: ChatStreamHandle | null = null

  /* ---------- getters ---------- */
  const rounds = computed(() => history.value.length)

  /* ---------- actions ---------- */
  function loadInitial(): void {
    if (messages.value.length === 0) {
      messages.value = mockInitialMessages.map((m) => ({ ...m }))
    }
  }

  /** 发送用户消息 → 后端 Agent 流式回复（真实 token / tool 事件渲染） */
  async function sendMessage(text: string): Promise<void> {
    if (isStreaming.value) return
    const trimmed = text.trim()
    if (!trimmed) return

    messages.value.push({
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    })

    isStreaming.value = true
    isWaiting.value = true
    replyBuffer.value = ''
    activeTool.value = null

    // 轮次上限（20 轮），移除最早一轮
    if (history.value.length >= MOCK_MAX_HISTORY) {
      history.value.shift()
    }
    history.value.push({ role: 'user', content: trimmed, timestamp: new Date().toISOString() })

    // assistant 占位气泡：首个事件（工具或 token）到达时创建并结束等待态
    let placeholder: ChatMessage | null = null
    const ensurePlaceholder = (): void => {
      if (!placeholder) {
        placeholder = {
          role: 'assistant',
          content: '',
          timestamp: new Date().toISOString(),
        }
        messages.value.push(placeholder)
        isWaiting.value = false
      }
    }

    const finish = (): void => {
      streamHandle = null
      replyBuffer.value = ''
      activeTool.value = null
      isWaiting.value = false
      isStreaming.value = false
    }

    streamHandle = chatStream(
      trimmed,
      history.value.slice(0, -1).map((m) => ({ role: m.role, content: m.content })),
      {
        // 真实工具事件（后端上报）：start 显示 calling，done 短暂停留后随正文推进
        onTool(name, status) {
          ensurePlaceholder()
          activeTool.value = { name, status: status === 'start' ? 'calling' : 'done' }
        },
        onToken(delta) {
          ensurePlaceholder()
          replyBuffer.value += delta
        },
        onDone(answer) {
          // 空回答（流中无 token）也要落一条 assistant 消息
          if (!placeholder) {
            placeholder = {
              role: 'assistant',
              content: '',
              timestamp: new Date().toISOString(),
            }
            messages.value.push(placeholder)
          }
          placeholder.content = answer || replyBuffer.value
          history.value.push({
            role: 'assistant',
            content: placeholder.content,
            timestamp: new Date().toISOString(),
          })
          finish()
        },
        onError(message) {
          // 无占位（纯错误）时落一条 assistant 错误气泡；有占位则写入错误文本
          if (!placeholder) {
            placeholder = {
              role: 'assistant',
              content: message,
              timestamp: new Date().toISOString(),
            }
            messages.value.push(placeholder)
          } else {
            placeholder.content = `${replyBuffer.value || ''}\n\n> ${message}`
          }
          finish()
        },
      },
    )
  }

  function clearHistory(): void {
    if (isStreaming.value) {
      streamHandle?.abort()
      streamHandle = null
      isStreaming.value = false
    }
    replyBuffer.value = ''
    activeTool.value = null
    isWaiting.value = false
    messages.value = mockInitialMessages.map((m) => ({ ...m }))
    history.value = []
  }

  /** 中止流式输出（保留已发送消息；组件卸载时调用） */
  function stopStreaming(): void {
    if (isStreaming.value) {
      streamHandle?.abort()
      streamHandle = null
      isStreaming.value = false
      replyBuffer.value = ''
      activeTool.value = null
      // 移除未产出内容的占位消息（中止时不留空气泡）
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant' && !last.content) {
        messages.value.pop()
      }
    }
    isWaiting.value = false
  }

  function loadHistory(): void {
    messages.value = mockHistory.map((m) => ({ ...m }))
    history.value = mockHistory.map((m) => ({ ...m }))
  }

  return {
    messages,
    isStreaming,
    isWaiting,
    history,
    activeTool,
    replyBuffer,
    rounds,
    maxChars,
    maxHistory,
    quickActions,
    loadInitial,
    sendMessage,
    clearHistory,
    loadHistory,
    stopStreaming,
  }
})
