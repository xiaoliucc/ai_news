/* ============================================================
   流式输出模拟器 —— 模拟 POST /api/agent/chat 的流式响应
   逐字追加 + 工具调用标签（calling → done）+ 完成回调
   ============================================================ */

import type { ToolName } from '@/types'

export interface StreamCallbacks {
  onDelta?: (delta: string) => void
  onTool?: (name: ToolName, status: 'calling' | 'done') => void
  onDone?: () => void
}

interface StreamHandle {
  cancel: () => void
}

const MIN_CHUNK_MS = 16
const MAX_CHUNK_MS = 42

/** 将文本切分为流式输出的字符块（中文按字、英文按词，模拟真实节奏） */
function splitChunks(text: string): string[] {
  const chunks: string[] = []
  const tokens = text.match(/\s+|[a-zA-Z0-9]{1,4}|./g) ?? []
  let buf = ''
  for (const tk of tokens) {
    buf += tk
    if (buf.length >= 2) {
      chunks.push(buf)
      buf = ''
    }
  }
  if (buf) chunks.push(buf)
  return chunks
}

/**
 * 启动一次模拟流式输出。
 * 返回句柄，可 cancel() 中止（组件卸载时调用）。
 */
export function startStreaming(
  text: string,
  toolCalls: Array<{ name: ToolName; delay: number }>,
  cb: StreamCallbacks,
): StreamHandle {
  let cancelled = false
  let timer: ReturnType<typeof setTimeout> | null = null
  const chunks = splitChunks(text)

  const schedule = (delay: number) => {
    if (cancelled) return
    timer = setTimeout(() => {
      if (cancelled) return
      const next = chunks.shift()
      if (next !== undefined) {
        cb.onDelta?.(next)
        schedule(MIN_CHUNK_MS + Math.random() * (MAX_CHUNK_MS - MIN_CHUNK_MS))
      } else {
        cb.onDone?.()
      }
    }, delay)
  }

  // 工具调用序列：逐个 calling → done（间隔 350ms），之后开始正文
  let toolTimer: ReturnType<typeof setTimeout> | null = null
  const toolChain = (idx: number) => {
    if (cancelled) return
    if (idx >= toolCalls.length) {
      schedule(120)
      return
    }
    const t = toolCalls[idx]
    cb.onTool?.(t.name, 'calling')
    toolTimer = setTimeout(() => {
      if (cancelled) return
      cb.onTool?.(t.name, 'done')
      toolChain(idx + 1)
    }, t.delay)
  }
  if (toolCalls.length > 0) {
    toolChain(0)
  } else {
    schedule(80)
  }

  return {
    cancel() {
      cancelled = true
      if (timer) clearTimeout(timer)
      if (toolTimer) clearTimeout(toolTimer)
    },
  }
}
