import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api/http', () => ({
  get: vi.fn(),
  post: vi.fn(async () => ({ answer: 'OK' })),
  put: vi.fn(),
}))

import { post } from '@/api/http'
import { chat } from '@/api/agent'

const mockedPost = vi.mocked(post)

describe('api/agent', () => {
  it('请求体包含 message 与 history', async () => {
    const history = [
      { role: 'user' as const, content: '你好' },
      { role: 'assistant' as const, content: '你好！' },
    ]
    await chat('继续说', history)
    expect(mockedPost).toHaveBeenCalledWith('/agent/chat', {
      message: '继续说',
      history,
    })
  })

  it('history 超过 20 条时截断为最近 20 条（后端上限）', async () => {
    const long = Array.from({ length: 30 }, (_, i) => ({
      role: 'user' as const,
      content: `msg${i}`,
    }))
    await chat('hello', long)
    const sent = vi.mocked(post).mock.calls.at(-1)![1] as { history: unknown[] }
    expect(sent.history).toHaveLength(20)
    expect(sent.history[0]).toEqual({ role: 'user', content: 'msg10' })
    expect(sent.history[19]).toEqual({ role: 'user', content: 'msg29' })
  })

  it('返回后端 answer 文本', async () => {
    mockedPost.mockResolvedValueOnce({ answer: '这是回复' })
    const res = await chat('hi', [])
    expect(res.answer).toBe('这是回复')
  })
})
