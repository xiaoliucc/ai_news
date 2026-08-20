import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/articles', () => ({
  fetchArticles: vi.fn(async () => ({ total: 0, articles: [] })),
}))

import { fetchArticles as apiFetchArticles } from '@/api/articles'
import { useArticlesStore } from '@/stores/articles'
import type { Article } from '@/types'

const mockedApi = vi.mocked(apiFetchArticles)

function makeArticle(over: Partial<Article> = {}): Article {
  return {
    id: 'a1',
    title: 'Test Paper',
    url: 'https://x/1',
    source: 'arxiv',
    summary: 'about LLM',
    author: null,
    published_at: new Date().toISOString(),
    score: 10,
    tags: ['LLM'],
    language: 'en',
    ...over,
  }
}

describe('stores/articles', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApi.mockClear()
    mockedApi.mockResolvedValue({ total: 0, articles: [] })
  })

  it('fetchArticles 用当前 days/sources/limit 调用后端', async () => {
    const store = useArticlesStore()
    store.days = 14
    store.selectedSources = ['hackernews']
    await store.fetchArticles()
    expect(mockedApi).toHaveBeenCalledWith({ days: 14, sources: ['hackernews'], limit: 50 })
  })

  it('summary 为 null 时归一化为空串（视图安全）', async () => {
    const store = useArticlesStore()
    mockedApi.mockResolvedValue({
      total: 2,
      articles: [makeArticle({ id: 'a1', summary: null }), makeArticle({ id: 'a2' })],
    })
    await store.fetchArticles()
    expect(store.articles[0].summary).toBe('')
    expect(store.articles[1].summary).toBe('about LLM')
  })

  it('days 变化自动重新拉取（后端执行窗口筛选）', async () => {
    const store = useArticlesStore()
    await store.fetchArticles()
    expect(mockedApi).toHaveBeenCalledTimes(1)

    store.days = 14
    await vi.waitFor(() => expect(mockedApi).toHaveBeenCalledTimes(2))
    expect(mockedApi).toHaveBeenLastCalledWith({ days: 14, sources: [], limit: 50 })
  })

  it('客户端搜索过滤标题/摘要/标签', async () => {
    const store = useArticlesStore()
    mockedApi.mockResolvedValue({
      total: 2,
      articles: [
        makeArticle({ id: 'a1', title: 'Transformer paper' }),
        makeArticle({ id: 'a2', title: 'Food recipe', tags: ['cooking'] }),
      ],
    })
    await store.fetchArticles()
    store.search = 'transformer'
    expect(store.filteredArticles).toHaveLength(1)
    expect(store.filteredArticles[0].id).toBe('a1')
  })
})
