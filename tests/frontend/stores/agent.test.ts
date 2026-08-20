import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/agent', () => ({
  chat: vi.fn(),
}))

import { chat as apiChat } from '@/api/agent'
import { useAgentStore } from '@/stores/agent'

const mockedChat = vi.mocked(apiChat)

describe('stores/agent', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    mockedChat.mockClear()
    mockedChat.mockResolvedValue({ answer: '这是回复内容' })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('空输入不发送消息、不调用 API', async () => {
    const store = useAgentStore()
    await store.sendMessage('   ')
    expect(store.messages).toHaveLength(0)
    expect(mockedChat).not.toHaveBeenCalled()
  })

  it('发送流程：user 消息入列 → 调 API（带历史）→ 流式播放后 assistant 消息入列', async () => {
    const store = useAgentStore()
    await store.sendMessage('你好')

    // user 消息立即入列，API 已调用（history 不含本条）
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].role).toBe('user')
    expect(mockedChat).toHaveBeenCalledWith('你好', [])

    // 推进流式定时器（工具链 + 正文逐字）
    await vi.advanceTimersByTimeAsync(5000)
    expect(store.isStreaming).toBe(false)
    expect(store.messages).toHaveLength(2)
    expect(store.messages[1].role).toBe('assistant')
    expect(store.messages[1].content).toBe('这是回复内容')
    expect(store.messages[1].toolCalls).toBeDefined()
    // history 已记录完整轮次
    expect(store.history).toHaveLength(2)
  })

  it('API 失败时状态复位，不产生 assistant 消息', async () => {
    mockedChat.mockRejectedValueOnce(new Error('network'))
    const store = useAgentStore()
    await store.sendMessage('hello')
    expect(store.isStreaming).toBe(false)
    expect(store.messages).toHaveLength(1) // 仅 user 消息
    expect(store.messages[0].role).toBe('user')
  })

  it('clearHistory 清空消息与历史并复位欢迎语', async () => {
    const store = useAgentStore()
    await store.sendMessage('hi')
    await vi.advanceTimersByTimeAsync(5000)
    store.clearHistory()
    expect(store.history).toHaveLength(0)
    expect(store.messages.length).toBeGreaterThan(0)
    expect(store.messages[0].role).toBe('assistant') // 欢迎语
  })
})
