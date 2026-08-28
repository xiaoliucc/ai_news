/**
 * 类型定义 —— 与后端 FastAPI dataclass 对齐
 * 后端参考：Article / SOURCE_META / CollectionStats / ChatRequest / ChatResponse
 */

/** 对应后端 Article dataclass */
export interface Article {
  id: string
  title: string
  url: string
  source: SourceName
  summary: string
  author: string | null
  published_at: string | null // ISO 8601
  score: number
  tags: string[]
  language: 'en' | 'zh'
}

/** 对应后端 SOURCE_META */
export interface Source {
  name: string
  label: string
  category: SourceCategory
  description: string
  article_count: number
  enabled: boolean
}

/** 对应后端 GET /api/stats（collection_runs 表字段） */
export interface CollectionStats {
  total_runs: number
  total_articles: number
  last_collection_at: string | null
  runs: Array<{
    id: number
    started_at: string
    finished_at: string
    status: string
    total_articles: number
    deduped_count: number
    source_stats: Array<{
      name: string
      fetched: number
      failed: boolean
      error: string | null
      elapsed_ms: number
    }>
    error: string | null
  }>
}

/** 对应后端 ChatRequest / ChatResponse */
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  toolCalls?: Array<{ name: string; status: 'calling' | 'done' }>
}

export type SourceName = 'hackernews' | 'arxiv' | 'huggingface_papers' | 'rss' | 'github'
export type SourceCategory = 'tech_community' | 'academic' | 'chinese_media'

export type ToolName = 'SEARCH' | 'SUMMARIZE' | 'ANALYZE_TREND' | 'TRIGGER_COLLECTION'

export type SortMode = 'latest' | 'score' | 'relevance'
export type MainView = 'articles' | 'trends' | 'hotlist'

/** 侧栏源的分组展示名（全大写） */
export const SOURCE_GROUP_LABELS: Record<SourceCategory, string> = {
  tech_community: 'TECH COMMUNITY',
  academic: 'ACADEMIC',
  chinese_media: 'CHINESE MEDIA',
}
