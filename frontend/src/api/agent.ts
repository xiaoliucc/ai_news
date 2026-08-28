/* ============================================================
   AGENT API —— POST /api/agent/chat（SSE 真流式）
   后端返回 text/event-stream：
     data: {"type":"tool","name":"...","status":"start"|"done"}
     data: {"type":"token","text":"..."}
     data: {"type":"done","answer":"..."}
     data: {"type":"error","message":"..."}
   用 fetch + ReadableStream 增量读取（axios 无法消费 SSE），
   返回 handle 可 abort() 中断（组件卸载/清空时调用）。
   ============================================================ */

export interface ChatHistoryItem {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatStreamHandlers {
  /** 真实工具执行事件（后端上报，非前端猜测） */
  onTool?: (name: string, status: 'start' | 'done') => void
  /** LLM 流式增量（token 级） */
  onToken?: (text: string) => void
  /** 完成：携带完整答案 */
  onDone?: (answer: string) => void
  /** 错误事件或网络失败 */
  onError?: (message: string) => void
}

export interface ChatStreamHandle {
  abort: () => void
}

interface SseEvent {
  type: 'tool' | 'token' | 'done' | 'error'
  name?: string
  status?: 'start' | 'done'
  text?: string
  answer?: string
  message?: string
}

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

/** 发起 SSE 流式对话请求；回调由事件驱动，返回 abort 句柄 */
export function chatStream(
  message: string,
  history: ChatHistoryItem[],
  handlers: ChatStreamHandlers,
): ChatStreamHandle {
  const controller = new AbortController()

  void (async () => {
    try {
      const res = await fetch(`${API_BASE}/agent/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        // 后端 history 上限 20 条消息（≈ 最近 10 轮），此处兜底截断
        body: JSON.stringify({ message, history: history.slice(-20) }),
        signal: controller.signal,
      })
      if (!res.ok) {
        handlers.onError?.(`请求失败（HTTP ${res.status}），请检查后端服务`)
        return
      }
      if (!res.body) {
        handlers.onError?.('浏览器不支持流式响应')
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        // 按空行切分 SSE 帧；一帧内可能有多个 data: 行，取第一个
        let sep: number
        while ((sep = buf.indexOf('\n\n')) >= 0) {
          const raw = buf.slice(0, sep)
          buf = buf.slice(sep + 2)
          const line = raw.split('\n').find((l) => l.startsWith('data:'))
          if (!line) continue
          const payload = line.slice(5).trim()
          if (!payload) continue
          let ev: SseEvent
          try {
            ev = JSON.parse(payload) as SseEvent
          } catch {
            continue // 忽略坏帧（半包/脏数据）
          }
          switch (ev.type) {
            case 'tool':
              handlers.onTool?.(ev.name ?? '', ev.status ?? 'start')
              break
            case 'token':
              handlers.onToken?.(ev.text ?? '')
              break
            case 'done':
              handlers.onDone?.(ev.answer ?? '')
              break
            case 'error':
              handlers.onError?.(ev.message ?? '未知错误')
              break
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        handlers.onError?.('请求失败，请检查后端服务')
      }
    }
  })()

  return { abort: () => controller.abort() }
}
