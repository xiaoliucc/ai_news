import { afterEach, describe, expect, it, vi } from 'vitest'

import { chatStream } from '@/api/agent'

function sseResponse(frames: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(new TextEncoder().encode(f))
      controller.close()
    },
  })
  return new Response(body, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

function readFetchBody(): { message: string; history: unknown[] } {
  const call = vi.mocked(fetch).mock.calls[0]
  const body = (call[1] as { body: string }).body
  return JSON.parse(body) as { message: string; history: unknown[] }
}

describe('api/agent (SSE 真流式)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POST /agent/chat 携带 message 与最近 20 条 history，事件按类型分发', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse([
          'data: {"type":"tool","name":"search_articles","status":"start"}\n\n',
          'data: {"type":"tool","name":"search_articles","status":"done"}\n\n',
          'data: {"type":"token","text":"你"}\n\n',
          'data: {"type":"token","text":"好"}\n\n',
          'data: {"type":"done","answer":"你好"}\n\n',
        ]),
      ),
    )
    const onTool = vi.fn()
    const onToken = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    const long = Array.from({ length: 30 }, (_, i) => ({
      role: 'user' as const,
      content: `msg${i}`,
    }))
    await new Promise<void>((resolve) => {
      chatStream('hi', long, {
        onTool,
        onToken,
        onDone: (answer: string) => {
          onDone(answer)
          resolve()
        },
        onError,
      })
    })

    const sent = readFetchBody()
    expect(sent.message).toBe('hi')
    expect(sent.history).toHaveLength(20)
    expect(sent.history[0]).toEqual({ role: 'user', content: 'msg10' })

    expect(onTool).toHaveBeenNthCalledWith(1, 'search_articles', 'start')
    expect(onTool).toHaveBeenNthCalledWith(2, 'search_articles', 'done')
    expect(onToken).toHaveBeenNthCalledWith(1, '你')
    expect(onToken).toHaveBeenNthCalledWith(2, '好')
    expect(onDone).toHaveBeenCalledWith('你好')
    expect(onError).not.toHaveBeenCalled()
  })

  it('error 事件触发 onError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse(['data: {"type":"error","message":"LLM 未配置"}\n\n']),
      ),
    )
    const onError = vi.fn()
    await new Promise<void>((resolve) => {
      chatStream('x', [], { onError: (m) => (onError(m), resolve()) })
    })
    expect(onError).toHaveBeenCalledWith('LLM 未配置')
  })

  it('HTTP 非 2xx 触发 onError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('bad', { status: 500 })))
    const onError = vi.fn()
    await new Promise<void>((resolve) => {
      chatStream('x', [], { onError: (m) => (onError(m), resolve()) })
    })
    expect(onError).toHaveBeenCalledWith('请求失败（HTTP 500），请检查后端服务')
  })
})
