/* ============================================================
   AGENT API —— POST /api/agent/chat
   后端返回整段 answer（非流式），toolCalls 由前端本地推断展示
   ============================================================ */

import { post } from '@/api/http'

export interface ChatHistoryItem {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatResponse {
  answer: string
}

export async function chat(
  message: string,
  history: ChatHistoryItem[],
): Promise<ChatResponse> {
  // 后端 history 上限 20 条消息（≈ 最近 10 轮），此处兜底截断
  return post<ChatResponse>('/agent/chat', {
    message,
    history: history.slice(-20),
  })
}
