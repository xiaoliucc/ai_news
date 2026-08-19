/* ============================================================
   SOURCES API —— GET /api/sources + PUT /api/sources/{name}
   ============================================================ */

import { get, put } from '@/api/http'
import type { Source } from '@/types'

export interface SourceListResponse {
  sources: Source[]
}

export async function fetchSources(): Promise<SourceListResponse> {
  return get<SourceListResponse>('/sources')
}

export interface ToggleResponse {
  name: string
  enabled: boolean
  selected_sources: string[]
}

/** 切换源启用状态；后端 404（未知源）/ 400（关闭最后一个）时抛错 */
export async function toggleSource(name: string, enabled: boolean): Promise<ToggleResponse> {
  return put<ToggleResponse>(`/sources/${name}`, { enabled })
}
