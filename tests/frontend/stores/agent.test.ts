import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/agent', () => ({
  chatStream: vi.fn(),
}))

import { chatStream } from '@/api/agent'
import { useAgentStore } from '@/stores/agent'

const mockedStream = vi.mocked(chatStream)

/** 模拟后端 SSE 事件流：工具 → token 增量 → done */
function mockEventStream(events: Array<{ type: string; name?: string; status?: string; text?: string; answer?: string; message?: string }>): void {
  mockedStream.mockImplementation((_msg, _hist, handlers) => {
    for (const ev of events) {
      if (ev.type === 'tool') handlers.onTool?.(ev.name ?? '', (ev.status ?? 'start') as 'start' | 'done')
      else if (ev.type === 'token') handlers.onToken?.(ev.text ?? '')
      else if (ev.type === 'done') handlers.onDone?.(ev.answer ?? '')
      else if (ev.type === 'error') handlers.onError?.(ev.message ?? '')
    }
    return { abort: vi.fn() }
  })
}

describe('stores/agent（SSE 真流式）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedStream.mockClear()
  })

  it('空输入不发送消息、不发起流', async () => {
    const store = useAgentStore()
    await store.sendMessage('   ')
    expect(store.messages).toHaveLength(0)
    expect(mockedStream).not.toHaveBeenCalled()
  })

  it('发送流程：user 入列 → 事件流驱动 → token 实时渲染 → done 落历史', async () => {
    mockEventStream([
      { type: 'tool', name: 'search_articles', status: 'start' },
      { type: 'tool', name: 'search_articles', status: 'done' },
      { type: 'token', text: '这' },
      { type: 'token', text: '是回复内容' },
      { type: 'done', answer: '这是回复内容' },
    ])
    const store = useAgentStore()
    await store.sendMessage('你好')

    // user 消息已入列；事件流同步消费后进入完成态
    expect(store.messages[0].role).toBe('user')
    expect(store.messages[1].role).toBe('assistant')
    expect(store.messages[1].content).toBe('这是回复内容')
    expect(store.isStreaming).toBe(false)
    expect(store.isWaiting).toBe(false)
    expect(store.replyBuffer).toBe('')
    expect(store.history).toHaveLength(2)

    // 请求带 history（不含本条）
    const args = mockedStream.mock.calls[0]
    expect(args[0]).toBe('你好')
    expect(args[1]).toEqual([])
  })

  it('token 增量先于 done：replyBuffer 实时累积（中间态可验证）', async () => {
    let tokenCb: ((t: string) => void) | null = null
    let doneCb: (() => void) | null = null
    mockedStream.mockImplementation((_m, _h, handlers) => {
      tokenCb = handlers.onToken ?? null
      doneCb = () => handlers.onDone?.('完')
      return { abort: vi.fn() }
    })
    const store = useAgentStore()
    void store.sendMessage('hi')

    // 首个 token：占位气泡入列，等待态结束
    tokenCb?.('第')
    expect(store.isWaiting).toBe(false)
    expect(store.isStreaming).toBe(true)
    expect(store.messages).toHaveLength(2)
    expect(store.replyBuffer).toBe('第')

    // 后续 token 继续累积
    tokenCb?.('一句')
    expect(store.replyBuffer).toBe('第' + '一句')

    // done：落历史 + 复位
    doneCb?.()
    expect(store.isStreaming).toBe(false)
    expect(store.history).toHaveLength(2)
    expect(store.messages[1].content).toBe('完')
  })

  it('error 事件：落 assistant 错误气泡并复位状态', async () => {
    mockEventStream([{ type: 'error', message: 'LLM 未配置' }])
    const store = useAgentStore()
    await store.sendMessage('hello')
    expect(store.isStreaming).toBe(false)
    expect(store.isWaiting).toBe(false)
    expect(store.messages).toHaveLength(2)
    expect(store.messages[1].content).toContain('LLM 未配置')
  })

  it('clearHistory 清空消息与历史并复位欢迎语', async () => {
    mockEventStream([{ type: 'done', answer: '好' }])
    const store = useAgentStore()
    await store.sendMessage('hi')
    store.clearHistory()
    expect(store.history).toHaveLength(0)
    expect(store.messages.length).toBeGreaterThan(0)
    expect(store.messages[0].role).toBe('assistant') // 欢迎语
  })
})
