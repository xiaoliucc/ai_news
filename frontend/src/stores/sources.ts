/* ============================================================
   SOURCES STORE —— 对应 GET /api/sources + PUT /api/sources/{name}
   + GET /api/stats + POST /api/collect（真实 API）
   ============================================================ */

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { fetchSources as apiFetchSources, toggleSource as apiToggleSource } from '@/api/sources'
import { fetchStats as apiFetchStats } from '@/api/stats'
import { triggerCollection as apiTriggerCollection } from '@/api/collect'
import type { CollectionStats, Source } from '@/types'

/** 采集后台执行约十几秒，触发后延迟刷新统计 */
const COLLECT_REFRESH_MS = 12_000

export const useSourcesStore = defineStore('sources', () => {
  /* ---------- state ---------- */
  const sources = ref<Source[]>([])
  const stats = ref<CollectionStats | null>(null)
  const loading = ref(false)
  const togglingName = ref<string | null>(null)
  const collecting = ref(false)
  const warning = ref<string | null>(null)

  /* ---------- getters ---------- */
  const enabledCount = computed(() => sources.value.filter((s) => s.enabled).length)

  /* ---------- actions ---------- */
  /** 拉取源列表与统计（两个请求并行） */
  async function fetchSources(): Promise<void> {
    loading.value = true
    try {
      const [srcRes, statsRes] = await Promise.all([apiFetchSources(), apiFetchStats(10)])
      sources.value = srcRes.sources
      stats.value = statsRes
    } finally {
      loading.value = false
    }
  }

  /** 切换源启用状态（对应 PUT /api/sources/{name}） */
  async function toggleSource(name: string): Promise<boolean> {
    const idx = sources.value.findIndex((s) => s.name === name)
    if (idx === -1) return false

    const target = sources.value[idx]
    const nextEnabled = !target.enabled

    togglingName.value = name
    try {
      await apiToggleSource(name, nextEnabled)
      sources.value = sources.value.map((s) =>
        s.name === name ? { ...s, enabled: nextEnabled } : { ...s },
      )
      warning.value = null
      return true
    } catch (err) {
      // 后端 400（关闭最后一个）/404（未知源）或网络错误：显示本地警告
      const status: unknown = (err as { response?: { status?: number } })?.response?.status
      warning.value = status === 400 ? '至少保留一个数据源' : '切换失败，请稍后重试'
      return false
    } finally {
      togglingName.value = null
    }
  }

  /** 触发一次全量采集（POST /api/collect，202 后台执行） */
  async function triggerCollection(): Promise<boolean> {
    if (collecting.value) return false
    collecting.value = true
    try {
      await apiTriggerCollection()
      // 后台采集完成后刷新统计与源计数
      await new Promise((r) => setTimeout(r, COLLECT_REFRESH_MS))
      const [srcRes, statsRes] = await Promise.all([apiFetchSources(), apiFetchStats(10)])
      sources.value = srcRes.sources
      stats.value = statsRes
      return true
    } catch {
      warning.value = '触发采集失败，请稍后重试'
      return false
    } finally {
      collecting.value = false
    }
  }

  function clearWarning(): void {
    warning.value = null
  }

  return {
    sources,
    stats,
    loading,
    togglingName,
    collecting,
    warning,
    enabledCount,
    fetchSources,
    toggleSource,
    triggerCollection,
    clearWarning,
  }
})
