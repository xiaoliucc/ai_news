/* ============================================================
   AGENT STORE —— 对应 POST /api/agent/chat
   真实 API：后端返回整段 answer，前端保留流式播放模拟
   （逐字渲染 + 本地推断的工具调用标签，保持视觉体验）
   ============================================================ */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { chat as apiChat } from '@/api/agent'
import {
  MOCK_MAX_CHARS,
  MOCK_MAX_HISTORY,
  mockHistory,
  mockInitialMessages,
  QUICK_ACTIONS,
} from '@/mock/data'
import { startStreaming } from '@/mock/streamSimulator'
import type { ChatMessage, ToolName } from '@/types'

/** 根据用户输入匹配工具调用序列（本地推断，仅用于展示标签；真实调用由后端 Agent 执行） */
function inferToolCalls(text: string): Array<{ name: ToolName; delay: number }> {
  const calls: Array<{ name: ToolName; delay: number }> = []
  if (/趋势|trend|热点|research/i.test(text)) calls.push({ name: 'ANALYZE_TREND', delay: 500 })
  if (/采集|collect|trigger/i.test(text)) calls.push({ name: 'TRIGGER_COLLECTION', delay: 600 })
  if (/总结|summar|摘要/i.test(text)) calls.push({ name: 'SUMMARIZE', delay: 450 })
  if (calls.length === 0) calls.push({ name: 'SEARCH', delay: 500 })
  if (/推荐|论文|paper/i.test(text)) calls.push({ name: 'SUMMARIZE', delay: 450 })
  return calls
}

export const useAgentStore = defineStore('agent', () => {
  /* ---------- state ---------- */
  const messages = ref<ChatMessage[]>([])
  const isStreaming = ref(false)
  /** 等待后端 LLM 响应中（尚未开始流式播放） */
  const isWaiting = ref(false)
  const history = ref<ChatMessage[]>([])
  const activeTool = ref<{ name: ToolName; status: 'calling' | 'done' } | null>(null)
  const replyBuffer = ref('')
  const maxChars = ref(MOCK_MAX_CHARS)
  const maxHistory = ref(MOCK_MAX_HISTORY)
  const quickActions = ref(QUICK_ACTIONS)
  let streamHandle: { cancel: () => void } | null = null

  /* ---------- getters ---------- */
  const rounds = computed(() => history.value.length)

  /* ---------- actions ---------- */
  function loadInitial(): void {
    if (messages.value.length === 0) {
      messages.value = mockInitialMessages.map((m) => ({ ...m }))
    }
  }

  /** 发送用户消息 → 后端 Agent 回复（真实 API，流式播放模拟渲染） */
  async function sendMessage(text: string): Promise<void> {
    if (isStreaming.value) return
    const trimmed = text.trim()
    if (!trimmed) return

    messages.value.push({
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    })

    // 本地推断工具标签（展示用；真实工具调用由后端 Agent 循环执行）
    const toolCalls = inferToolCalls(trimmed)

    isStreaming.value = true
    isWaiting.value = true
    replyBuffer.value = ''
    activeTool.value = null

    // 轮次上限（20 轮），移除最早一轮
    if (history.value.length >= MOCK_MAX_HISTORY) {
      history.value.shift()
    }
    history.value.push({ role: 'user', content: trimmed, timestamp: new Date().toISOString() })

    try {
      // history 传历史轮次（不含本条），上限由 api 层截断为最近 20 条消息
      const { answer } = await apiChat(
        trimmed,
        history.value.slice(0, -1).map((m) => ({ role: m.role, content: m.content })),
      )

      // 流式播放：首个字符到达前保持等待态（一直转圈）；到达时推入占位
      // assistant 气泡承载增量文本，等待态结束切换为流式渲染
      let placeholder: ChatMessage | null = null
      streamHandle = startStreaming(
        answer,
        toolCalls.map((t) => ({ ...t })),
        {
          onDelta: (d) => {
            if (!placeholder) {
              placeholder = {
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString(),
              }
              messages.value.push(placeholder)
              isWaiting.value = false
            }
            replyBuffer.value += d
          },
          onTool: (name, status) => {
            activeTool.value = { name, status }
          },
          onDone: () => {
            // 空回答（无 delta）时也要落一条 assistant 消息
            if (!placeholder) {
              placeholder = {
                role: 'assistant',
                content: '',
                timestamp: new Date().toISOString(),
              }
              messages.value.push(placeholder)
            }
            placeholder.content = replyBuffer.value
            placeholder.toolCalls = toolCalls.map((t) => ({ name: t.name, status: 'done' as const }))
            history.value.push({
              role: 'assistant',
              content: replyBuffer.value,
              timestamp: new Date().toISOString(),
            })
            replyBuffer.value = ''
            activeTool.value = null
            isWaiting.value = false
            isStreaming.value = false
            streamHandle = null
          },
        },
      )
    } catch {
      // 请求失败（拦截器已 ElMessage 提示）：保留用户消息，复位流式与等待态
      replyBuffer.value = ''
      activeTool.value = null
      isStreaming.value = false
      isWaiting.value = false
      streamHandle = null
    }
  }

  function clearHistory(): void {
    if (isStreaming.value) {
      streamHandle?.cancel()
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
      streamHandle?.cancel()
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
