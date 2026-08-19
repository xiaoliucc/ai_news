/* ============================================================
   Mock 延迟工具 —— 模拟网络延迟（对应后端 API 响应节奏）
   ============================================================ */

export function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
