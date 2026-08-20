<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
// ElMessage 手动 deep import（包入口导入会拉全量 element-plus）
import { ElMessage } from 'element-plus/es/components/message/index'
import 'element-plus/es/components/message/style/css'
import { useSourcesStore } from '@/stores/sources'
import { useLayoutStore } from '@/stores/layout'
import SourceItem from '@/components/SourceItem.vue'
import StatBlock from '@/components/StatBlock.vue'
import { formatRelativeTime } from '@/composables/useRelativeTime'
import { useI18n } from '@/utils/i18n'

const store = useSourcesStore()
const layout = useLayoutStore()
const { t, lang } = useI18n()
const { sources, stats, loading, collecting, warning } = storeToRefs(store)
const { sidebarCollapsed } = storeToRefs(layout)

const groups = computed(() => {
  const cats: Array<'tech_community' | 'academic' | 'chinese_media'> = [
    'tech_community',
    'academic',
    'chinese_media',
  ]
  return cats.map((cat) => ({
    cat,
    label: t(`group.${cat}`),
    items: sources.value.filter((s) => s.category === cat),
  }))
})

const lastCollection = computed(() =>
  formatRelativeTime(stats.value?.last_collection_at ?? null, Date.now()),
)

async function onCollect(): Promise<void> {
  const ok = await store.triggerCollection()
  if (ok) {
    ElMessage.success(t('misc.collected'))
  }
}
</script>

<template>
  <div class="spanel" data-od-id="sources-panel">
    <!-- 顶部标题区 -->
    <div class="spanel__head">
      <template v-if="!sidebarCollapsed">
        <h2 class="spanel__title">{{ lang === 'zh' ? '信息源' : 'SOURCES' }}</h2>
        <el-button
          size="small"
          :loading="collecting"
          class="spanel__collect"
          data-od-id="collect-btn"
          @click="onCollect"
        >
          {{ t('btn.collect') }}
        </el-button>
        <button
          class="spanel__icon"
          type="button"
          title="折叠侧栏"
          aria-label="折叠侧栏"
          data-od-id="sidebar-collapse"
          @click="layout.toggleSidebar()"
        >
          <span class="spanel__icon-fold" aria-hidden="true"></span>
        </button>
      </template>
      <template v-else>
        <button
          class="spanel__icon"
          type="button"
          title="展开侧栏"
          aria-label="展开侧栏"
          data-od-id="sidebar-expand"
          @click="layout.toggleSidebar()"
        >
          <span class="spanel__icon-fold is-rev" aria-hidden="true"></span>
        </button>
      </template>
    </div>

    <!-- 源列表（独立滚动） -->
    <div class="spanel__list" :class="{ 'is-collapsed': sidebarCollapsed }">
      <el-skeleton v-if="loading" :rows="6" animated />

      <template v-else>
        <div v-for="g in groups" :key="g.cat" class="spanel__group">
          <h3 class="spanel__group-title">{{ g.label }}</h3>

          <!-- 折叠态：仅指示灯 -->
          <div v-if="sidebarCollapsed" class="spanel__group-dots">
            <el-tooltip
              v-for="s in g.items"
              :key="s.name"
              :content="`${s.label} · ${s.enabled ? 'ENABLED' : 'DISABLED'}`"
              placement="right"
            >
              <span
                class="spanel__dot"
                :class="s.enabled ? 'is-on' : 'is-off'"
              ></span>
            </el-tooltip>
          </div>

          <SourceItem v-else v-for="s in g.items" :key="s.name" :source="s" />
        </div>
      </template>
    </div>

    <!-- 警告（最后一个源被禁用，对应后端 400） -->
    <div v-if="warning" class="spanel__warn" role="alert" data-od-id="sources-warning">
      <span class="spanel__warn-icon" aria-hidden="true"></span>
      <span class="spanel__warn-text">{{ t('misc.warn') }}</span>
    </div>

    <!-- 底部统计区 -->
    <div v-if="stats" class="spanel__stats" :class="{ 'is-collapsed': sidebarCollapsed }">
      <template v-if="!sidebarCollapsed">
        <StatBlock :label="t('stat.totalRuns')" :value="String(stats.total_runs)" :dot="'accent'" />
        <StatBlock :label="t('stat.totalArticles')" :value="String(stats.total_articles)" />
        <StatBlock
          :label="t('stat.lastCollection')"
          :value="collecting ? t('stat.running') : lastCollection"
        />
      </template>
      <template v-else>
        <el-tooltip content="TOTAL RUNS" placement="right">
          <span class="spanel__mini-dot is-accent"></span>
        </el-tooltip>
        <el-tooltip content="TOTAL ARTICLES" placement="right">
          <span class="spanel__mini-dot"></span>
        </el-tooltip>
      </template>
    </div>
  </div>
</template>

<style scoped>
.spanel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
}

/* 顶部标题区 */
.spanel__head {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 12px;
  flex: none;
  border-bottom: 1px solid var(--border);
}
.spanel__title {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 2px;
  color: var(--fg);
  white-space: nowrap;
}
.spanel__collect {
  margin-left: auto;
}
/* 采集按钮：主题色填充背景（cyan=青 / yellow=黄），斜切轮廓，文字用深墨色
   注意：必须用长写属性覆盖 endfield-theme.css 的 .el-button 全局简写（background: transparent） */
.spanel__collect.el-button {
  --el-button-bg-color: var(--accent);
  --el-button-border-color: var(--accent);
  --el-button-text-color: var(--bg);
  background-color: var(--accent);
  border-color: var(--accent);
  color: var(--bg);
  clip-path: polygon(0 0, 100% 0, calc(100% - 8px) 100%, 0 100%);
}
.spanel__collect.el-button:hover,
.spanel__collect.el-button:focus-visible {
  --el-button-hover-bg-color: var(--accent-dim);
  --el-button-hover-border-color: var(--accent-dim);
  --el-button-hover-text-color: var(--bg);
  background-color: var(--accent-dim);
  border-color: var(--accent-dim);
  color: var(--bg);
}
.spanel__collect.el-button:active {
  background-color: var(--accent-dim);
  border-color: var(--accent-dim);
  color: var(--bg);
}
.spanel__collect.el-button.is-loading,
.spanel__collect.el-button.is-loading:hover {
  background-color: var(--accent-dim);
  border-color: var(--accent-dim);
  color: var(--bg);
  opacity: 0.85;
}
.spanel__icon {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  background: transparent;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield);
}
.spanel__icon:hover {
  background: var(--surface-hover);
  border-color: var(--accent);
}
.spanel__icon-fold {
  width: 10px;
  height: 10px;
  border-left: 2px solid var(--muted);
  border-bottom: 2px solid var(--muted);
  transform: rotate(45deg);
  margin-left: 2px;
  transition: border-color var(--dur) var(--ease-endfield);
}
.spanel__icon-fold.is-rev {
  transform: rotate(225deg);
  margin-left: 0;
  margin-right: 2px;
}
.spanel__icon:hover .spanel__icon-fold {
  border-color: var(--accent);
}

/* 列表滚动区 */
.spanel__list {
  flex: 1 1 auto;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 0;
}
.spanel__list.is-collapsed {
  padding: 8px 0;
}

.spanel__group {
  margin-bottom: 6px;
}
.spanel__group-title {
  margin: 0;
  padding: 10px 12px 6px;
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 3px;
  color: var(--muted);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.spanel__group-dots {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 12px 0;
}
.spanel__dot {
  width: 6px;
  height: 6px;
  cursor: default;
}
.spanel__dot.is-on {
  background: var(--accent);
}
.spanel__dot.is-off {
  background: var(--disabled);
}

/* 警告条 */
.spanel__warn {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0 12px 10px;
  padding: 8px 10px;
  background: rgba(232, 122, 58, 0.08);
  border-left: 2px solid var(--warn);
  flex: none;
}
.spanel__warn-icon {
  width: 8px;
  height: 8px;
  margin-top: 3px;
  background: var(--warn);
  flex: none;
  clip-path: polygon(0 0, 100% 0, 100% 70%, 50% 100%, 0 70%);
}
.spanel__warn-text {
  font-size: 11px;
  line-height: 1.5;
  color: var(--warn);
}

/* 底部统计 */
.spanel__stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px 12px;
  border-top: 1px solid var(--border);
  flex: none;
}
.spanel__stats.is-collapsed {
  align-items: center;
  gap: 14px;
  padding: 12px 0;
}
.spanel__mini-dot {
  width: 6px;
  height: 6px;
  background: var(--muted);
}
.spanel__mini-dot.is-accent {
  background: var(--accent);
}
</style>
