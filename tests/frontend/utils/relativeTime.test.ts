import { describe, expect, it } from 'vitest'
import { formatRelativeTime } from '@/composables/useRelativeTime'

const NOW = Date.parse('2026-08-19T12:00:00Z')

describe('utils/formatRelativeTime', () => {
  it('空值：zh 返回"从未"，en 返回 NEVER', () => {
    expect(formatRelativeTime(null, NOW)).toBe('从未')
    expect(formatRelativeTime(undefined, NOW, 'en')).toBe('NEVER')
  })

  it('无效时间戳返回 --', () => {
    expect(formatRelativeTime('not-a-date', NOW)).toBe('--')
  })

  it('分钟/小时/天/周分级输出（zh）', () => {
    const iso = (offsetMin: number) => new Date(NOW - offsetMin * 60_000).toISOString()
    expect(formatRelativeTime(iso(0.5), NOW)).toBe('刚刚')
    expect(formatRelativeTime(iso(30), NOW)).toBe('30m 前')
    expect(formatRelativeTime(iso(2 * 60), NOW)).toBe('2h 前')
    expect(formatRelativeTime(iso(3 * 24 * 60), NOW)).toBe('3d 前')
    expect(formatRelativeTime(iso(2 * 7 * 24 * 60), NOW)).toBe('2w 前')
  })

  it('超过 5 周返回日期（zh）', () => {
    const old = new Date(NOW - 40 * 24 * 60 * 60_000).toISOString()
    expect(formatRelativeTime(old, NOW)).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('英文格式（en）', () => {
    const iso = (offsetMin: number) => new Date(NOW - offsetMin * 60_000).toISOString()
    expect(formatRelativeTime(iso(30), NOW, 'en')).toBe('30m ago')
    expect(formatRelativeTime(iso(5 * 60), NOW, 'en')).toBe('5h ago')
  })
})
