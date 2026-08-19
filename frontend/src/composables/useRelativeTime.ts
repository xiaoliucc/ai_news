/* ============================================================
   相对时间格式化（composable）
   输入 ISO 8601，输出中文/英文相对时间，如 "2h ago" / "2h 前"
   ============================================================ */

export type RelTimeLang = 'zh' | 'en'

export function formatRelativeTime(
  iso: string | null | undefined,
  now: number = Date.now(),
  lang: RelTimeLang = 'zh',
): string {
  if (!iso) return lang === 'en' ? 'NEVER' : '从未'
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return '--'
  const diffMs = now - ts
  const minutes = Math.floor(diffMs / 60_000)

  if (minutes < 1) return lang === 'en' ? 'JUST NOW' : '刚刚'
  if (minutes < 60) return lang === 'en' ? `${minutes}m ago` : `${minutes}m 前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return lang === 'en' ? `${hours}h ago` : `${hours}h 前`
  const days = Math.floor(hours / 24)
  if (days < 7) return lang === 'en' ? `${days}d ago` : `${days}d 前`
  const weeks = Math.floor(days / 7)
  if (weeks < 5) return lang === 'en' ? `${weeks}w ago` : `${weeks}w 前`
  return new Date(ts).toISOString().slice(0, 10)
}

export function useRelativeTime() {
  return { formatRelativeTime }
}
