/* ============================================================
   COLLECT API —— POST /api/collect（手动触发一次全量采集）
   后端 202 立即返回，采集在后台执行；前端随后轮询 stats
   ============================================================ */

import { post } from '@/api/http'

export interface CollectResponse {
  status: 'started'
}

export async function triggerCollection(): Promise<CollectResponse> {
  return post<CollectResponse>('/collect')
}
