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
  cyan: { hackernews: '#00d4aa', arxiv: '#3b82f6', huggingface_papers: '#a855f7', rss: '#e87a3a', github: '#22c55e' },
  // 高饱和亮黄（hackernews 主色）/ 低饱和蓝（arxiv，浅底可见）/ 低饱和紫（HF）/ 低饱和橙（rss）/ 低饱和绿（github，浅底可见）
  // 注：arxiv 原为近白 #E8E8E6，在浅色卡片背景（#ECEEED/白）上不可见，改为 #5B8DD9
  yellow: { hackernews: '#E8E237', arxiv: '#5B8DD9', huggingface_papers: '#9B8FD6', rss: '#E8A06C', github: '#3D9E50' },
}

export const CHART_UI: Record<Theme, { bg: string; accent: string; axis: string; text: string; ink: string }> = {
  cyan: { bg: '#0a0e17', accent: '#00d4aa', axis: '#334155', text: '#64748b', ink: '#e2e8f0' },
  // tooltip 深炭灰底 / 亮黄强调 / 浅区坐标轴灰 / 浅区刻度深灰 / tooltip 内白字
  yellow: { bg: '#323539', accent: '#E8E237', axis: '#9FA2A6', text: '#55585D', ink: '#E0E2E5' },
}

export function chartColorsFor(themeValue: Theme) {
  return {
    series: SERIES_COLORS[themeValue],
    ui: CHART_UI[themeValue],
  }
}
