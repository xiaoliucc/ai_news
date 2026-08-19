/* ============================================================
   ARTICLES API —— GET /api/articles
   参数：days(1-365) / sources(逗号分隔) / limit(1-200)
   ============================================================ */

import { get } from '@/api/http'
import type { Article, SourceName } from '@/types'

export interface ArticleQuery {
  days?: number
  sources?: SourceName[]
  limit?: number
}

export interface ArticleListResponse {
  total: number
  articles: Article[]
}

export async function fetchArticles(q: ArticleQuery = {}): Promise<ArticleListResponse> {
  return get<ArticleListResponse>('/articles', {
    days: q.days ?? 7,
    sources: q.sources && q.sources.length > 0 ? q.sources.join(',') : undefined,
    limit: q.limit ?? 50,
  })
}
