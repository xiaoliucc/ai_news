/* ============================================================
   数据源唯一清单
   - 展示顺序 = 侧栏 / 文章页筛选 / 趋势图系列 的顺序
   - 每源两套主题色（cyan / yellow）只在这里定义
   新增源：改本文件 + 后端 src/sources/__init__.py 的 SOURCE_REGISTRY
   + i18n 的 srcLabel 文案（三处）。
   ============================================================ */

import type { SourceName } from '@/types'

export interface SourceDef {
  /** 与后端 SOURCE_REGISTRY 的 key 完全一致 */
  name: SourceName
  /** 青色主题下的系列色 */
  cyan: string
  /** 黄色主题下的系列色 */
  yellow: string
}

export const SOURCES: readonly SourceDef[] = [
  { name: 'hackernews', cyan: '#00d4aa', yellow: '#E8E237' },
  // arxiv 原为近白 #E8E8E6，在浅底卡片上不可见，黄色主题改用低饱和蓝
  { name: 'arxiv', cyan: '#3b82f6', yellow: '#5B8DD9' },
  { name: 'huggingface_papers', cyan: '#a855f7', yellow: '#9B8FD6' },
  { name: 'rss', cyan: '#e87a3a', yellow: '#E8A06C' },
  { name: 'github', cyan: '#22c55e', yellow: '#3D9E50' },
  { name: 'csdn', cyan: '#E6452A', yellow: '#B34A3C' },
]

/** 有序的源名列表（筛选器 / 图表系列直接遍历它） */
export const SOURCE_NAMES: readonly SourceName[] = SOURCES.map((s) => s.name)

export type ThemeName = 'cyan' | 'yellow'

/** { cyan|yellow: { 源名: 颜色 } } */
export const SERIES_COLORS: Record<ThemeName, Record<SourceName, string>> = {
  cyan: Object.fromEntries(SOURCES.map((s) => [s.name, s.cyan])) as Record<SourceName, string>,
  yellow: Object.fromEntries(SOURCES.map((s) => [s.name, s.yellow])) as Record<SourceName, string>,
}
