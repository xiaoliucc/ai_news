<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useArticlesStore } from '@/stores/articles'
import { useSourcesStore } from '@/stores/sources'
import { hexToRgba } from '@/utils/endfieldChartTheme'
import StatBlock from '@/components/StatBlock.vue'
import { useI18n } from '@/utils/i18n'
import { chartColorsFor, useTheme } from '@/composables/useTheme'

const articlesStore = useArticlesStore()
const sourcesStore = useSourcesStore()
const { sources } = storeToRefs(sourcesStore)
const { t } = useI18n()
const { theme } = useTheme()

const trendRange = ref<7 | 14>(7)

/** 指标卡片 */
const kpiTotal = computed(() => articlesStore.articles.length)
const kpiThisWeek = computed(
  () => articlesStore.articles.filter((a) => {
    const ts = Date.parse(a.published_at ?? '')
    return ts >= Date.now() - 7 * 24 * 3600_000
  }).length,
)
const kpiActiveSources = computed(
  () => sources.value.filter((s) => s.enabled).length,
)
const kpiAvgScore = computed(() => {
  const list = articlesStore.articles
  if (list.length === 0) return 0
  return Math.round(list.reduce((sum, a) => sum + a.score, 0) / list.length)
})

/** 按当前主题取图表系列色与界面色 */
const chartColors = computed(() => chartColorsFor(theme.value))

const SERIES = [
  { name: 'hackernews' },
  { name: 'arxiv' },
  { name: 'huggingface_papers' },
  { name: 'rss' },
  { name: 'github' },
] as const

/** 时间折线图 */
const trendChartOption = computed(() => {
  const n = trendRange.value
  const now = Date.now()
  const colors = chartColors.value.series
  const ui = chartColors.value.ui
  const series = SERIES.map((s) => {
    const data: Array<[string, number]> = []
    for (let i = n - 1; i >= 0; i--) {
      const d = new Date(now - i * 24 * 3600_000)
      // key 必须与 xAxis.data（trendChartDates，M/D 格式）完全一致，
      // 否则 ECharts category 轴无法定位数据点，折线不显示
      const key = `${d.getMonth() + 1}/${d.getDate()}`
      const count = articlesStore.articles.filter((a) => {
        const ts = Date.parse(a.published_at ?? '')
        if (!ts || ts < now - n * 24 * 3600_000) return false
        const dd = new Date(ts)
        const k = `${dd.getMonth() + 1}/${dd.getDate()}`
        return k === key && a.source === s.name
      }).length
      data.push([key, count])
    }
    const color = colors[s.name]
    return {
      name: t(`srcLabel.${s.name}`),
      type: 'line' as const,
      data,
      symbol: 'diamond' as const,
      symbolSize: 6,
      lineStyle: { width: 2, color },
      itemStyle: { color },
      areaStyle: { color: hexToRgba(color, 0.08) },
    }
  })
  return {
    backgroundColor: 'transparent',
    color: [colors.hackernews, colors.arxiv, colors.huggingface_papers, colors.rss, colors.github],
    legend: {
      top: 0,
      right: 0,
      itemWidth: 10,
      itemHeight: 2,
      textStyle: { color: ui.text, fontFamily: 'Rajdhani, sans-serif', fontSize: 10 },
      data: SERIES.map((s) => t(`srcLabel.${s.name}`)),
    },
    grid: { left: 40, right: 16, top: 32, bottom: 24 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: ui.bg,
      borderColor: ui.accent,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: ui.ink, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
    },
    xAxis: {
      type: 'category',
      data: trendChartDates(n, now),
      axisLine: { lineStyle: { color: ui.axis, width: 1 } },
      axisTick: { show: true, length: 4, lineStyle: { color: ui.axis } },
      axisLabel: { color: ui.text, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { color: ui.text, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
    },
    series,
  }
})

function trendChartDates(n: number, now: number): string[] {
  const out: string[] = []
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now - i * 24 * 3600_000)
    out.push(`${d.getMonth() + 1}/${d.getDate()}`)
  }
  return out
}

/** 词频 Top 10 横向柱状图（主题色填充，无圆角） */
const tagChartOption = computed(() => {
  const freq = [...articlesStore.tagFrequency].reverse()
  const colors = chartColors.value.series
  const ui = chartColors.value.ui
  const accent = colors.hackernews
  return {
    backgroundColor: 'transparent',
    grid: { left: 8, right: 32, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'item',
      backgroundColor: ui.bg,
      borderColor: ui.accent,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: ui.ink, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      formatter: '{b} · {c}',
    },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
    },
    yAxis: {
      type: 'category',
      data: freq.map((f) => f.name),
      axisLine: { lineStyle: { color: ui.axis, width: 1 } },
      axisTick: { show: true, length: 4, lineStyle: { color: ui.axis } },
      axisLabel: {
        color: ui.text,
        fontFamily: 'Rajdhani, sans-serif',
        fontSize: 10,
      },
    },
    series: [
      {
        name: 'COUNT',
        type: 'bar',
        data: freq.map((f) => f.count),
        barWidth: 8,
        itemStyle: {
          color: accent,
          borderRadius: 0,
        },
        label: {
          show: true,
          position: 'right',
          color: ui.text,
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 10,
          formatter: '{c}',
        },
      },
    ],
  }
})

/** 来源分布饼图 */
const pieChartOption = computed(() => {
  const dist = articlesStore.sourceDistribution
  const total = dist.reduce((s, d) => s + d.value, 0)
  const colors = chartColors.value.series
  const ui = chartColors.value.ui
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: ui.bg,
      borderColor: ui.accent,
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: ui.ink, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      formatter: '{b} · {c} ({d}%)',
    },
    legend: {
      bottom: 0,
      left: 'center',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: ui.text, fontFamily: 'Rajdhani, sans-serif', fontSize: 10 },
    },
    series: [
      {
        name: 'SOURCE',
        type: 'pie',
        radius: ['52%', '74%'],
        center: ['50%', '42%'],
        padAngle: 2,
        itemStyle: {
          borderRadius: 0,
          borderColor: ui.bg,
          borderWidth: 2,
        },
        label: {
          color: ui.text,
          fontFamily: 'JetBrains Mono, monospace',
          fontSize: 10,
          formatter: '{b}',
        },
        labelLine: { lineStyle: { color: ui.axis } },
        data: dist.map((d) => ({
          name: t(`srcLabel.${d.name}`),
          value: d.value,
          itemStyle: {
            color: colors[d.name],
          },
        })),
      },
    ],
    graphic: {
      type: 'text',
      left: 'center',
      top: '34%',
      style: {
        text: `${total}`,
        fill: ui.ink,
        font: '700 20px JetBrains Mono, monospace',
        textAlign: 'center',
      },
    },
  }
})

function setTrendRange(v: number): void {
  trendRange.value = v as 7 | 14
}

onMounted(() => {
  if (articlesStore.articles.length === 0) {
    void articlesStore.fetchArticles()
  }
})
</script>

<template>
  <div class="tview" data-od-id="trends-view">
    <!-- 指标卡片行 -->
    <div class="tview__kpis">
      <StatBlock :label="t('stat.total')" :value="String(kpiTotal)" accent />
      <StatBlock :label="t('stat.thisWeek')" :value="String(kpiThisWeek)" />
      <StatBlock :label="t('stat.activeSources')" :value="String(kpiActiveSources)" />
      <StatBlock :label="t('stat.avgScore')" :value="String(kpiAvgScore)" />
    </div>

    <!-- 主图：时间折线图 -->
    <section class="tview__card">
      <header class="tview__card-head">
        <h3 class="tview__card-title">{{ t('chart.articleFlow') }} · {{ trendRange }}D</h3>
        <div class="tview__range" role="group" aria-label="趋势时间范围">
          <button
            v-for="r in [7, 14]"
            :key="r"
            type="button"
            class="tview__range-btn mono"
            :class="{ 'is-active': trendRange === r }"
            @click="setTrendRange(r)"
          >
            {{ r }}D
          </button>
        </div>
      </header>
      <div class="tview__chart">
        <v-chart :option="trendChartOption" autoresize />
      </div>
    </section>

    <div class="tview__row">
      <!-- 词频 Top 10 -->
      <section class="tview__card">
        <header class="tview__card-head">
          <h3 class="tview__card-title">{{ t('chart.tagFreq') }}</h3>
        </header>
        <div class="tview__chart tview__chart--half">
          <v-chart :option="tagChartOption" autoresize />
        </div>
      </section>

      <!-- 来源分布饼图 -->
      <section class="tview__card">
        <header class="tview__card-head">
          <h3 class="tview__card-title">{{ t('chart.sourceShare') }}</h3>
        </header>
        <div class="tview__chart tview__chart--half">
          <v-chart :option="pieChartOption" autoresize />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tview {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 14px 16px;
  gap: 12px;
}

/* KPI 行 */
.tview__kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  flex: none;
}

/* 卡片 */
.tview__card {
  background: var(--surface);
  flex: none;
}
.tview__card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}
.tview__card-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--fg);
}
.tview__range {
  display: flex;
  gap: 0;
}
.tview__range-btn {
  height: 24px;
  min-width: 36px;
  padding: 0 8px;
  background: transparent;
  border: 1px solid var(--border);
  border-left: none;
  color: var(--muted);
  font-size: 10px;
  cursor: pointer;
  transition: background var(--dur) var(--ease-endfield),
    color var(--dur) var(--ease-endfield), border-color var(--dur) var(--ease-endfield);
}
.tview__range-btn:first-child {
  border-left: 1px solid var(--border);
}
.tview__range-btn.is-active {
  background: var(--surface-raised);
  border-color: var(--accent);
  color: var(--accent);
}

.tview__chart {
  height: 240px;
  padding: 8px 6px 4px;
}
.tview__chart--half {
  height: 220px;
}

.tview__row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  flex: none;
}
</style>
