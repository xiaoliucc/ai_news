/* ============================================================
   ARTICLES STORE —— 对应 GET /api/articles（days/sources/limit 参数）
   客户端过滤 + 聚合 getters（trendData / tagFrequency / top10）
   Mock 实现：setTimeout 模拟网络延迟
   ============================================================ */

import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { fetchArticles as apiFetchArticles } from '@/api/articles'
import type { Article, SortMode, SourceName } from '@/types'

const DAY_MS = 24 * 60 * 60 * 1000

export const SORT_OPTIONS: Array<{ value: SortMode; label: string }> = [
  { value: 'latest', label: 'LATEST' },
  { value: 'score', label: 'HOT' },
  { value: 'relevance', label: 'RELEVANCE' },
]

export interface TrendPoint {
  date: string // YYYY-MM-DD
  hackernews: number
  arxiv: number
  huggingface_papers: number
  rss: number
  github: number
}

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

  // days/sources 变化时重新拉取（时间窗口与源筛选由后端执行）
  watch([days, selectedSources], () => {
    void fetchArticles()
  })

  function setFilter(patch: {
    days?: 1 | 3 | 7 | 14
    sources?: SourceName[]
    search?: string
    sort?: SortMode
  }): void {
    if (patch.days !== undefined) days.value = patch.days
    if (patch.sources !== undefined) selectedSources.value = patch.sources
    if (patch.search !== undefined) search.value = patch.search
    if (patch.sort !== undefined) sort.value = patch.sort
    page.value = 1
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
  const timeCutoff = computed(() => Date.now() - days.value * DAY_MS)

  const filteredArticles = computed<Article[]>(() => {
    const kw = search.value.trim().toLowerCase()
    let list = articles.value.filter((a) => {
      if (a.published_at && Date.parse(a.published_at) < timeCutoff.value) return false
      if (selectedSources.value.length > 0 && !selectedSources.value.includes(a.source)) return false
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

  /** 时间折线图数据：按日聚合文章数，多系列按 source 分色 */
  const trendData = computed<TrendPoint[]>(() => {
    const n = days.value
    const points: TrendPoint[] = []
    const now = Date.now()
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date(now - i * DAY_MS)
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      points.push({ date: key, hackernews: 0, arxiv: 0, huggingface_papers: 0, rss: 0, github: 0 })
    }
    const map = new Map(points.map((p) => [p.date, p]))
    for (const a of articles.value) {
      const ts = Date.parse(a.published_at ?? '')
      if (!ts || ts < now - n * DAY_MS) continue
      const d = new Date(ts)
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      const p = map.get(key)
      if (p) p[a.source] += 1
    }
    return points
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

  /** 趋势摘要（Agent 回复使用） */
  const trendSummary = computed(() => {
    const top = tagFrequency.value.slice(0, 3)
    const hotSource = [...sourceDistribution.value].sort((a, b) => b.value - a.value)[0]
    const weekCount = weekTop10.value.length
    return {
      topTags: top.map((t) => t.name),
      hotSource: hotSource?.name ?? 'hackernews',
      hotSourceCount: hotSource?.value ?? 0,
      weekArticles: articles.value.filter(
        (a) => (Date.parse(a.published_at ?? '') || 0) >= Date.now() - 7 * DAY_MS,
      ).length,
      weekTopCount: weekCount,
    }
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
    trendData,
    tagFrequency,
    sourceDistribution,
    trendSummary,
  }
})
