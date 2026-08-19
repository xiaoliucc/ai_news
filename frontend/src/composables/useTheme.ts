/* ============================================================
   THEME —— 视觉主题切换（青 / 黄科幻工业）
   data-theme 挂在 <body> 上；选择持久化到 localStorage
   ============================================================ */

import { ref, watch } from 'vue'

export type Theme = 'cyan' | 'yellow'

const STORAGE_KEY = 'ef-theme'

function readSaved(): Theme {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'yellow' ? 'yellow' : 'cyan'
  } catch {
    return 'cyan'
  }
}

const theme = ref<Theme>(readSaved())

function apply(el: HTMLElement | null): void {
  if (el) el.setAttribute('data-theme', theme.value)
}

function toggleTheme(): void {
  theme.value = theme.value === 'yellow' ? 'cyan' : 'yellow'
  try {
    localStorage.setItem(STORAGE_KEY, theme.value)
  } catch {
    /* localStorage 不可用时静默降级 */
  }
}

/** 挂载监听：body 上同步 data-theme（在 main.ts 或 App 中调用一次） */
export function bindTheme(body: HTMLElement | null): void {
  apply(body)
  watch(theme, () => apply(body))
}

export function useTheme() {
  return { theme, toggleTheme }
}

/** 图表系列色 / 界面色（非组件环境使用） */
export const SERIES_COLORS: Record<Theme, Record<string, string>> = {
  cyan: { hackernews: '#00d4aa', arxiv: '#3b82f6', huggingface_papers: '#a855f7', rss: '#e87a3a' },
  yellow: { hackernews: '#eaff00', arxiv: '#f5f5f2', huggingface_papers: '#c792ea', rss: '#ff8a3d' },
}

export const CHART_UI: Record<Theme, { bg: string; accent: string; axis: string; text: string; ink: string }> = {
  cyan: { bg: '#0a0e17', accent: '#00d4aa', axis: '#334155', text: '#64748b', ink: '#e2e8f0' },
  yellow: { bg: '#0b0b0f', accent: '#eaff00', axis: '#4a4852', text: '#b8b4ab', ink: '#f5f5f2' },
}

export function chartColorsFor(themeValue: Theme) {
  return {
    series: SERIES_COLORS[themeValue],
    ui: CHART_UI[themeValue],
  }
}
