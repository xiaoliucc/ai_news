/* ============================================================
   ENDFIELD ECHARTS THEME —— 终末地 HUD 图表规范
   - 背景透明，坐标轴细线 + 4px 刻度，无网格线
   - 折线 2px + 6px 菱形端点 + 8% 填充
   - tooltip 锐利直角，深底青边；图例全大写右对齐
   ============================================================ */

import type { EChartsOption } from 'echarts'

/** 终端地风格图表系列配色（与全局令牌一致） */
export const ENDFIELD_SERIES_COLORS = {
  hackernews: '#00d4aa',
  arxiv: '#3b82f6',
  huggingface_papers: '#a855f7',
  rss: '#e87a3a',
  github: '#22c55e',
} as const

export type EndfieldSeriesKey = keyof typeof ENDFIELD_SERIES_COLORS

/** 将颜色转为 8% 透明度填充 */
export function hexToRgba(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** 基础坐标轴：细线 + 4px 刻度，无网格 */
export const endfieldAxis = {
  axisLine: { lineStyle: { color: '#334155', width: 1 } },
  axisTick: {
    show: true,
    length: 4,
    lineStyle: { color: '#334155' },
  },
  axisLabel: {
    color: '#64748b',
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: 10,
  },
} as const

/** 终末地图表主题常量 */
export const endfieldChartTheme = {
  bg: 'transparent',
  textStyle: {
    color: '#64748b',
    fontFamily: 'Inter, "Noto Sans SC", sans-serif',
    fontSize: 12,
  },
  color: Object.values(ENDFIELD_SERIES_COLORS),
  title: {
    textStyle: {
      color: '#e2e8f0',
      fontFamily: 'Rajdhani, sans-serif',
      fontSize: 14,
      fontWeight: 700,
    },
  },
  legend: {
    textStyle: {
      color: '#64748b',
      fontFamily: 'Rajdhani, sans-serif',
      fontSize: 10,
      fontWeight: 600,
    },
    pageTextStyle: { color: '#64748b' },
  },
  categoryAxis: endfieldAxis,
  valueAxis: endfieldAxis,
  tooltip: {
    backgroundColor: '#0a0e17',
    borderColor: '#00d4aa',
    borderWidth: 1,
    padding: [8, 12],
    textStyle: {
      color: '#e2e8f0',
      fontFamily: 'JetBrains Mono, monospace',
      fontSize: 11,
    },
  },
  /* 折线默认：2px 实线 + 6px 菱形端点 + 8% 填充 */
  line: {
    lineStyle: { width: 2 },
    itemStyle: { borderWidth: 1 },
    symbol: 'diamond',
    symbolSize: 6,
  },
  bar: {
    itemStyle: { borderRadius: 0 },
  },
} satisfies EChartsOption

export default endfieldChartTheme
