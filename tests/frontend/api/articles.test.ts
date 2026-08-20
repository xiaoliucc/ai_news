import { describe, expect, it, vi } from 'vitest'

// mock http 层：验证参数构造，不触发真实请求
vi.mock('@/api/http', () => ({
  get: vi.fn(async () => ({ total: 0, articles: [] })),
  post: vi.fn(),
  put: vi.fn(),
}))

import { get } from '@/api/http'
import { fetchArticles } from '@/api/articles'

const mockedGet = vi.mocked(get)

describe('api/articles', () => {
  it('默认参数：days=7, limit=50，无 sources 时不上传该参数', async () => {
    await fetchArticles()
    expect(mockedGet).toHaveBeenCalledWith('/articles', {
      days: 7,
      sources: undefined,
      limit: 50,
    })
  })

  it('sources 空数组时不上传 sources（后端空=全选）', async () => {
    await fetchArticles({ sources: [] })
    expect(mockedGet).toHaveBeenCalledWith('/articles', {
      days: 7,
      sources: undefined,
      limit: 50,
    })
  })

  it('sources 有值时拼接为逗号分隔字符串（后端 Query 格式）', async () => {
    await fetchArticles({ sources: ['hackernews', 'arxiv'], days: 14, limit: 100 })
    expect(mockedGet).toHaveBeenCalledWith('/articles', {
      days: 14,
      sources: 'hackernews,arxiv',
      limit: 100,
    })
  })
})
