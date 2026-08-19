/* ============================================================
   STATS API —— GET /api/stats（采集运行统计 + 最近 N 次明细）
   ============================================================ */

import { get } from '@/api/http'
import type { CollectionStats } from '@/types'

export async function fetchStats(limit = 10): Promise<CollectionStats> {
  return get<CollectionStats>('/stats', { limit })
}
