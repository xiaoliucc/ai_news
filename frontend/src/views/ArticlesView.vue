<script lang="ts">
// keep-alive include 需要组件名
export default { name: 'ArticlesView' }
</script>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useArticlesStore } from '@/stores/articles'
import { useLayoutStore } from '@/stores/layout'
import { useAgentStore } from '@/stores/agent'
import ArticleCard from '@/components/ArticleCard.vue'
import TrendsView from '@/views/TrendsView.vue'
import HotlistView from '@/views/HotlistView.vue'
import { useI18n } from '@/utils/i18n'
import type { MainView } from '@/types'

const articlesStore = useArticlesStore()
const layoutStore = useLayoutStore()
const agentStore = useAgentStore()
const { t, lang } = useI18n()
const { days, selectedSources, search, sort, loading, paginated, total, totalPages, page } =
  storeToRefs(articlesStore)

const VIEWS: Array<{ key: MainView; label: string }> = [
  { key: 'articles', label: 'ARTICLES' },
  { key: 'trends', label: 'TRENDS' },
  { key: 'hotlist', label: 'HOTLIST' },
]

const TIME_RANGES: Array<{ value: 1 | 3 | 7 | 14; label: string }> = [
  { value: 1, label: '1D' },
  { value: 3, label: '3D' },
  { value: 7, label: '7D' },
  { value: 14, label: '14D' },
]

/** 来源筛选选项（与后端 SOURCE_META 一致，按 category 配色） */
const sourceOptions = computed(() => {
  const names: SourceName[] = ['hackernews', 'arxiv', 'huggingface_papers', 'rss', 'github']
  return names.map((n) => ({ value: n, label: t(`srcLabel.${n}`) }))
})

const sortOptions = computed(() => {
  const keys = ['latest', 'score', 'relevance'] as const
  return keys.map((k) => ({ value: k, label: t(`sort.${k}`) }))
})

const viewLabel = computed(() => t(`view.${activeView.value}`))

const activeView = computed({
  get: () => layoutStore.currentMainView,
  set: (v: MainView) => layoutStore.setMainView(v),
})

const isEmpty = computed(() => !loading.value && total.value === 0)

/* ---------- 视图切换：青色滑块滑动指示 ---------- */
const viewsEl = ref<HTMLElement | null>(null)
const indicator = reactive({ left: '0px', width: '0px', visible: false })

/** 把滑块移动到当前激活按钮的位置（相对容器测量） */
function updateIndicator(): void {
  const el = viewsEl.value
  if (!el) return
  const btn = el.querySelector<HTMLElement>('.aview__view-btn.is-active')
  if (!btn) return
  indicator.left = `${btn.offsetLeft}px`
  indicator.width = `${btn.offsetWidth}px`
  indicator.visible = true
}

function onDays(v: number): void {
  articlesStore.setFilter({ days: v as 1 | 3 | 7 | 14 })
}

function onSources(v: string[]): void {
  articlesStore.setFilter({ sources: v as SourceName[] })
}

function onSort(v: string): void {
  articlesStore.setFilter({ sort: v as 'latest' | 'score' | 'relevance' })
}

function onSearch(): void {
  articlesStore.setFilter({ search: search.value })
}

/** 语义搜索引导：跳转 Agent 面板提问 */
function askAgent(): void {
  if (!layoutStore.panelVisible) layoutStore.togglePanel()
  agentStore.sendMessage(
    search.value.trim()
      ? t('misc.searchPrompt') + search.value.trim() + t('misc.searchPromptEnd')
      : t('misc.searchPrompt') + t('misc.searchPromptEnd'),
  )
}

onMounted(() => {
  // 视图组件由 keep-alive 缓存；重新挂载时确保 store 已有数据
  if (articlesStore.articles.length === 0) {
    void articlesStore.fetchArticles()
  }
  // 初始化滑块位置；等 webfont（Rajdhani 等）就绪后重测按钮宽度
  updateIndicator()
  document.fonts?.ready.then(updateIndicator).catch(() => {})
})

// 切换视图 / 切换语言（按钮文案宽度变化）后重算滑块
watch(activeView, () => void nextTick(updateIndicator))
watch(lang, () => void nextTick(updateIndicator))
</script>

<template>
  <div class="aview" data-od-id="articles-view">
    <!-- 顶部工具栏：面包屑 + 视图切换 -->
    <div class="aview__toolbar">
      <nav class="aview__crumb" aria-label="面包屑">
        <span class="aview__crumb-item">{{ lang === 'zh' ? '情报' : 'INTEL' }}</span>
        <span class="aview__crumb-sep">/</span>
        <span class="aview__crumb-item is-current">{{ viewLabel }}</span>
      </nav>

      <div ref="viewsEl" class="aview__views" role="tablist" aria-label="视图切换">
        <span
          class="aview__views-indicator"
          :style="{ left: indicator.left, width: indicator.width, opacity: indicator.visible ? 1 : 0 }"
          aria-hidden="true"
        ></span>
        <button
          v-for="v in VIEWS"
          :key="v.key"
          class="aview__view-btn"
          :class="{ 'is-active': activeView === v.key }"
          role="tab"
          :aria-selected="activeView === v.key"
          data-od-id="view-switch"
          @click="activeView = v.key"
        >
          {{ t(`view.${v.key}`) }}
        </button>
      </div>
    </div>

    <!-- 文章列表视图 -->
    <template v-if="activeView === 'articles'">
      <!-- 筛选栏 -->
      <div class="aview__filters">
        <div class="aview__search">
          <span class="aview__search-icon" aria-hidden="true"></span>
          <el-input
            v-model="search"
            :placeholder="t('placeholder.titleSummary')"
            clearable
            @input="onSearch"
            @keyup.enter="onSearch"
          />
        </div>

        <el-select
          v-model="selectedSources"
          multiple
          collapse-tags
          :max-collapse-tags="1"
          :placeholder="t('placeholder.sources')"
          class="aview__source-select"
          data-od-id="source-filter"
          @change="onSources"
        >
          <el-option
            v-for="o in sourceOptions"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>

        <div class="aview__range" role="group" aria-label="时间范围">
          <button
            v-for="r in TIME_RANGES"
            :key="r.value"
            class="aview__range-btn"
            :class="{ 'is-active': days === r.value }"
            type="button"
            data-od-id="time-range"
            @click="onDays(r.value)"
          >
            {{ r.label }}
          </button>
        </div>

        <el-select
          :model-value="sort"
          :placeholder="t('placeholder.sort')"
          class="aview__sort-select"
          data-od-id="sort-select"
          @change="onSort"
        >
          <el-option
            v-for="o in sortOptions"
            :key="o.value"
            :label="o.label"
            :value="o.value"
          />
        </el-select>
      </div>

      <!-- 语义搜索提示条 -->
      <div v-if="search" class="aview__hint" data-od-id="semantic-hint">
        <span class="aview__hint-icon" aria-hidden="true"></span>
        <span class="aview__hint-text">
          {{ t('misc.hint') }}
          <button type="button" class="aview__hint-link" @click="askAgent">
            {{ t('btn.hintLink') }}
          </button>
        </span>
      </div>

      <!-- 加载骨架屏 -->
      <div v-if="loading" class="aview__list">
        <el-skeleton v-for="n in 5" :key="n" :rows="4" animated class="aview__skeleton" />
      </div>

      <!-- 空状态 -->
      <div v-else-if="isEmpty" class="aview__empty" data-od-id="articles-empty">
        <span class="aview__empty-mark" aria-hidden="true"></span>
        <p class="aview__empty-title">{{ t('misc.emptyTitle') }}</p>
        <p class="aview__empty-sub">
          {{ t('misc.emptySub') }}
        </p>
        <el-button size="small" class="aview__empty-action" @click="articlesStore.setFilter({ search: '', sources: [], days: 14 })">
          {{ t('misc.clearFilters') }}
        </el-button>
      </div>

      <!-- 文章列表 -->
      <div v-else class="aview__list">
        <ArticleCard v-for="a in paginated" :key="a.id" :article="a" />
      </div>

      <!-- 分页 -->
      <div v-if="total > 0" class="aview__pager mono">
        <span class="aview__pager-info">
          {{ total }} {{ t('misc.results') }} · {{ t('misc.page') }} {{ page }}/{{ totalPages }}
        </span>
        <button
          class="aview__pager-btn"
          type="button"
          :disabled="page <= 1"
          @click="articlesStore.setPage(page - 1)"
        >
          {{ t('btn.prev') }}
        </button>
        <button
          class="aview__pager-btn"
          type="button"
          :disabled="page >= totalPages"
          @click="articlesStore.setPage(page + 1)"
        >
          {{ t('btn.next') }}
        </button>
      </div>
    </template>

    <!-- 趋势视图（懒渲染，切到再挂载） -->
    <TrendsView v-else-if="activeView === 'trends'" />

    <!-- 热榜视图 -->
    <HotlistView v-else-if="activeView === 'hotlist'" />
  </div>
</template>

<style scoped>
.aview {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

/* ---------- 顶部工具栏 ---------- */
.aview__toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 44px;
  padding: 0 16px;
  flex: none;
  border-bottom: 1px solid var(--border);
}
.aview__crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}
.aview__crumb-item {
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  color: var(--muted);
}
.aview__crumb-item.is-current {
  color: var(--accent);
}
.aview__crumb-sep {
  color: var(--disabled);
  font-size: 11px;
}

.aview__views {
  display: flex;
  gap: 0;
  margin-left: auto;
  position: relative;
  background: var(--input-bg);
}
/* 青色滑动指示块：绝对定位 + 斜切，随激活按钮在三个 tab 间滑动 */
.aview__views-indicator {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 0;
  background: var(--accent);
  transform: skewX(-10deg);
  transition: left var(--dur) var(--ease-endfield),
    width var(--dur) var(--ease-endfield);
  pointer-events: none;
  z-index: 0;
}
.aview__view-btn {
  position: relative;
  z-index: 1;
  height: 28px;
  padding: 0 14px;
  background: transparent;
  border: 1px solid var(--border);
  border-left: none;
  color: var(--muted);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1.5px;
  cursor: pointer;
  transform: skewX(-10deg);
  transition: background var(--dur) var(--ease-endfield),
    color var(--dur) var(--ease-endfield), border-color var(--dur) var(--ease-endfield);
}
.aview__view-btn:first-child {
  border-left: 1px solid var(--border);
}
.aview__view-btn > * {
  transform: skewX(10deg);
}
.aview__view-btn:hover {
  background: var(--surface-hover);
  color: var(--fg);
}
.aview__view-btn.is-active {
  background: transparent;
  border-color: var(--accent);
  color: var(--accent-ink);
}

/* ---------- 筛选栏 ---------- */
.aview__filters {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  flex: none;
  border-bottom: 1px solid var(--border);
}
.aview__search {
  position: relative;
  flex: 1 1 auto;
  max-width: 320px;
}
.aview__search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 9px;
  height: 9px;
  border: 1.5px solid var(--disabled);
  z-index: 1;
  pointer-events: none;
}
.aview__search-icon::after {
  content: '';
  position: absolute;
  right: -3px;
  bottom: -3px;
  width: 4px;
  height: 1.5px;
  background: var(--disabled);
  transform: rotate(45deg);
}
.aview__search :deep(.el-input__wrapper) {
  padding-left: 30px;
}

.aview__source-select {
  width: 190px;
}
.aview__range {
  display: flex;
  gap: 0;
}
.aview__range-btn {
  height: 32px;
  min-width: 42px;
  padding: 0 10px;
  background: transparent;
  border: 1px solid var(--border);
  border-left: none;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
  cursor: pointer;
  transition: background var(--dur) var(--ease-endfield),
    color var(--dur) var(--ease-endfield), border-color var(--dur) var(--ease-endfield);
}
.aview__range-btn:first-child {
  border-left: 1px solid var(--border);
}
.aview__range-btn:hover {
  background: var(--surface-hover);
  color: var(--fg);
}
.aview__range-btn.is-active {
  background: var(--surface-raised);
  border-color: var(--accent);
  color: var(--accent);
}
.aview__sort-select {
  width: 132px;
}

/* ---------- 语义搜索提示 ---------- */
.aview__hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 16px 0;
  padding: 7px 10px;
  background: var(--accent-06);
  border-left: 2px solid var(--accent);
}
.aview__hint-icon {
  width: 8px;
  height: 8px;
  background: var(--accent);
  flex: none;
}
.aview__hint-text {
  font-size: 12px;
  color: var(--muted);
}
.aview__hint-link {
  background: none;
  border: none;
  padding: 0;
  color: var(--accent);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
}
/* yellow 主题：提示链接 → 暗金黄 */
[data-theme='yellow'] .aview__hint-link {
  color: #e5bd41;
}
.aview__hint-link:hover {
  text-decoration: underline;
}

/* ---------- 列表 ---------- */
.aview__list {
  flex: 1 1 auto;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.aview__skeleton {
  background: var(--surface);
  padding: 14px 16px;
}

/* ---------- 空状态 ---------- */
.aview__empty {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 16px;
}
.aview__empty-mark {
  width: 36px;
  height: 36px;
  border: 2px solid var(--disabled);
  position: relative;
}
.aview__empty-mark::after {
  content: '';
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 8px;
  height: 8px;
  background: var(--accent);
}
.aview__empty-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--fg);
}
.aview__empty-sub {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.aview__empty-action {
  margin-top: 6px;
}

/* ---------- 分页 ---------- */
.aview__pager {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  flex: none;
  border-top: 1px solid var(--border);
}
.aview__pager-info {
  margin-right: auto;
  font-size: 11px;
  color: var(--muted);
}
.aview__pager-btn {
  height: 28px;
  padding: 0 12px;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--fg);
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1.5px;
  cursor: pointer;
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield), color var(--dur) var(--ease-endfield);
}
.aview__pager-btn:hover:not(:disabled) {
  background: var(--surface-hover);
  border-color: var(--accent);
  color: var(--accent);
}
.aview__pager-btn:disabled {
  color: var(--disabled);
  cursor: not-allowed;
  border-color: var(--border);
}
</style>
