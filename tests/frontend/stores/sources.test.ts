import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/sources', () => ({
  fetchSources: vi.fn(),
  toggleSource: vi.fn(),
}))
vi.mock('@/api/stats', () => ({
  fetchStats: vi.fn(),
}))
vi.mock('@/api/collect', () => ({
  triggerCollection: vi.fn(),
}))

import { fetchSources as apiFetchSources, toggleSource as apiToggleSource } from '@/api/sources'
import { fetchStats as apiFetchStats } from '@/api/stats'
import { useSourcesStore } from '@/stores/sources'
import type { Source } from '@/types'

const mockSources = vi.mocked(apiFetchSources)
const mockToggle = vi.mocked(apiToggleSource)
const mockStats = vi.mocked(apiFetchStats)

function makeSource(over: Partial<Source> = {}): Source {
  return {
    name: 'hackernews',
    label: 'Hacker News',
    category: 'tech_community',
    description: 'desc',
    article_count: 10,
    enabled: true,
    ...over,
  }
}

describe('stores/sources', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockSources.mockResolvedValue({ sources: [makeSource()] })
    mockStats.mockResolvedValue({
      total_runs: 3,
      total_articles: 145,
      last_collection_at: '2026-08-19T00:00:00+00:00',
      runs: [],
    })
  })

  it('fetchSources 并行拉取源列表与统计', async () => {
    const store = useSourcesStore()
    await store.fetchSources()
    expect(mockSources).toHaveBeenCalledTimes(1)
    expect(mockStats).toHaveBeenCalledWith(10)
    expect(store.sources).toHaveLength(1)
    expect(store.stats?.total_runs).toBe(3)
  })

  it('toggleSource 成功后本地翻转 enabled', async () => {
    mockToggle.mockResolvedValue({ name: 'hackernews', enabled: false, selected_sources: [] })
    const store = useSourcesStore()
    await store.fetchSources()
    const ok = await store.toggleSource('hackernews')
    expect(ok).toBe(true)
    expect(store.sources[0].enabled).toBe(false)
    expect(store.warning).toBeNull()
  })

  it('toggleSource 后端 400（关闭最后一个源）时警告且状态不变', async () => {
    mockToggle.mockRejectedValue({ response: { status: 400 } })
    const store = useSourcesStore()
    await store.fetchSources()
    const ok = await store.toggleSource('hackernews')
    expect(ok).toBe(false)
    expect(store.sources[0].enabled).toBe(true) // 未翻转
    expect(store.warning).toBe('至少保留一个数据源')
  })

  it('toggleSource 未知源名直接返回 false 不发请求', async () => {
    const store = useSourcesStore()
    await store.fetchSources()
    const ok = await store.toggleSource('nonexistent')
    expect(ok).toBe(false)
    expect(mockToggle).not.toHaveBeenCalled()
  })
})
