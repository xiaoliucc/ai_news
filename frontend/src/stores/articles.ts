/* ============================================================
   ARTICLES STORE —— 对应 GET /api/articles（days/sources/limit 参数）
   客户端过滤/排序/分页 + 聚合 getters（tagFrequency / sourceDistribution / top10）
   趋势折线图数据由 TrendsView 自己按 7/14 天窗口算，store 不再重复聚合。
   ============================================================ */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { fetchArticles as apiFetchArticles } from '@/api/articles'
import type { Article, SortMode, SourceName } from '@/types'

const DAY_MS = 24 * 60 * 60 * 1000

export interface TagFreq {
  name: string
  count: number
}

export const useArticlesStore = defineStore('articles', () => {
  /* ---------- state ---------- */
  const articles = ref<Article[]>([])
  const loading = ref(false)
  const days = ref<1 | 3 | 7 | 14>(7)
  const selectedSources = ref<SourceName[]>([])
  const search = ref('')
  const sort = ref<SortMode>('latest')
  const limit = ref(50)
  const page = ref(1)
  const pageSize = ref(10)
  const favorites = ref<Set<string>>(new Set())

  /* ---------- actions ---------- */
  /** 拉取文章（真实 API：后端执行 days/sources 窗口筛选；search/sort 走客户端过滤） */
  async function fetchArticles(): Promise<void> {
    loading.value = true
    try {
      const res = await apiFetchArticles({
        days: days.value,
        sources: selectedSources.value,
        limit: limit.value,
      })
      // summary 后端可能为 null（如 RSS 源），归一化为空串避免视图报错
      articles.value = res.articles.map((a) => ({ ...a, summary: a.summary ?? '' }))
    } finally {
      loading.value = false
    }
  }

  // days/sources 是**后端**筛选条件：变化后必须重新拉取。
  // 曾用 watch([days, selectedSources]) 隐式触发（H-4-2），但那样"点一下会不会发请求"
  // 要跨 4 处才能确认；改为 setFilter 里显式调用（2026-11-01）。
  // 注意：直接写 store.days/store.selectedSources 不会重拉，组件请走 setFilter。

  function setFilter(patch: {
    days?: 1 | 3 | 7 | 14
    sources?: SourceName[]
    search?: string
    sort?: SortMode
  }): void {
    const serverSideChanged = patch.days !== undefined || patch.sources !== undefined
    if (patch.days !== undefined) days.value = patch.days
    if (patch.sources !== undefined) selectedSources.value = patch.sources
    if (patch.search !== undefined) search.value = patch.search
    if (patch.sort !== undefined) sort.value = patch.sort
    page.value = 1
    if (serverSideChanged) void fetchArticles()
  }

  function setPage(p: number): void {
    page.value = p
  }

  function toggleFavorite(id: string): void {
    const next = new Set(favorites.value)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    favorites.value = next
  }

  /* ---------- getters ---------- */
  // 口径说明（H-2-4）：days/sources 由后端按 collected_at 过滤，前端**不再重复筛**——
  // 否则后端用入库时间、前端用发布时间，边界日会出现"请求回来了列表却空一截"。
  // 这里只做 search / sort 这类纯客户端操作。
  const filteredArticles = computed<Article[]>(() => {
    const kw = search.value.trim().toLowerCase()
    let list = articles.value.filter((a) => {
      if (kw) {
        const hit =
          a.title.toLowerCase().includes(kw) ||
          a.summary.toLowerCase().includes(kw) ||
          a.tags.some((t) => t.toLowerCase().includes(kw))
        if (!hit) return false
      }
      return true
    })
    switch (sort.value) {
      case 'score':
        list = [...list].sort((a, b) => b.score - a.score)
        break
      case 'relevance':
        list = [...list].sort((a, b) => {
          // 相关度 = score + 时间衰减（近 24h 加分）
          const ta = Date.parse(a.published_at ?? '') || 0
          const tb = Date.parse(b.published_at ?? '') || 0
          const now = Date.now()
          const decayA = ta > now - DAY_MS ? 120 : 0
          const decayB = tb > now - DAY_MS ? 120 : 0
          return b.score + decayB - (a.score + decayA)
        })
        break
      case 'latest':
      default:
        list = [...list].sort(
          (a, b) => (Date.parse(b.published_at ?? '') || 0) - (Date.parse(a.published_at ?? '') || 0),
        )
    }
    return list
  })

  const paginated = computed<Article[]>(() => {
    const start = (page.value - 1) * pageSize.value
    return filteredArticles.value.slice(start, start + pageSize.value)
  })

  const total = computed(() => filteredArticles.value.length)
  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

  /** 今日 Top 10（按 score 降序） */
  const todayTop10 = computed<Article[]>(() => {
    const dayStart = new Date()
    dayStart.setHours(0, 0, 0, 0)
    const cutoff = dayStart.getTime() - 8 * 3600_000 // UTC 偏移补偿
    return articles.value
      .filter((a) => (Date.parse(a.published_at ?? '') || 0) >= cutoff)
      .sort((a, b) => b.score - a.score)
      .slice(0, 10)
  })

  /** 近 7 天 Top 10（按 score 降序） */
  const weekTop10 = computed<Article[]>(() => {
    const cutoff = Date.now() - 7 * DAY_MS
    return articles.value
      .filter((a) => (Date.parse(a.published_at ?? '') || 0) >= cutoff)
      .sort((a, b) => b.score - a.score)
      .slice(0, 10)
  })

  /** 词频 Top 10（从 tags 字段聚合） */
  const tagFrequency = computed<TagFreq[]>(() => {
    const freq = new Map<string, number>()
    for (const a of articles.value) {
      for (const t of a.tags) {
        freq.set(t, (freq.get(t) ?? 0) + 1)
      }
    }
    return [...freq.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)
  })

  /** 来源分布（按 article_count 占比） */
  const sourceDistribution = computed(() => {
    const counts = new Map<SourceName, number>()
    for (const a of articles.value) {
      counts.set(a.source, (counts.get(a.source) ?? 0) + 1)
    }
    return [...counts.entries()].map(([name, value]) => ({ name, value }))
  })

  return {
    articles,
    loading,
    days,
    selectedSources,
    search,
    sort,
    limit,
    page,
    pageSize,
    favorites,
    fetchArticles,
    setFilter,
    setPage,
    toggleFavorite,
    filteredArticles,
    paginated,
    total,
    totalPages,
    todayTop10,
    weekTop10,
    tagFrequency,
    sourceDistribution,
  }
})
