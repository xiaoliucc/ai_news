<script setup lang="ts">
import { computed } from 'vue'
import type { Source } from '@/types'
import { useSourcesStore } from '@/stores/sources'
import { useI18n } from '@/utils/i18n'

const props = defineProps<{
  source: Source
}>()

const store = useSourcesStore()
const { t } = useI18n()

const toggling = computed(() => store.togglingName === props.source.name)
const label = computed(() => t(`srcLabel.${props.source.name}`))

function onChange(): void {
  // 切换失败（最后一个源被禁用）时回滚开关，警告由 store.warning 提示
  void store.toggleSource(props.source.name)
}
</script>

<template>
  <div class="sitem" data-od-id="source-item">
    <span
      class="sitem__dot"
      :class="source.enabled ? 'is-on' : 'is-off'"
      aria-hidden="true"
    ></span>

    <div class="sitem__info">
      <div class="sitem__row">
        <span class="sitem__label">{{ label }}</span>
        <span class="sitem__count mono">{{ source.article_count }}</span>
      </div>
      <p class="sitem__desc">{{ source.description }}</p>
    </div>

    <el-switch
      :model-value="source.enabled"
      :loading="toggling"
      @change="onChange"
    />
  </div>
</template>

<style scoped>
.sitem {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 48px;
  padding: 0 12px;
  background: var(--surface);
  transition: background var(--dur) var(--ease-endfield);
}
.sitem:hover {
  background: var(--surface-hover);
}
/* 悬停左侧 2px 青色竖条 */
.sitem::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--accent);
  transform: scaleY(0);
  transition: transform var(--dur) var(--ease-endfield);
}
.sitem:hover::before {
  transform: scaleY(1);
}

/* 方形状态灯 */
.sitem__dot {
  width: 6px;
  height: 6px;
  flex: none;
}
.sitem__dot.is-on {
  background: var(--accent);
}
.sitem__dot.is-off {
  background: var(--disabled);
}

.sitem__info {
  flex: 1 1 auto;
  min-width: 0;
}
.sitem__row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.sitem__label {
  font-size: 13px;
  color: var(--fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sitem__count {
  margin-left: auto;
  font-size: 12px;
  color: var(--muted);
  flex: none;
}
.sitem__desc {
  margin: 1px 0 0;
  font-size: 10px;
  color: var(--disabled);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 开关槽位固定宽度，防止布局抖动 */
.sitem :deep(.el-switch) {
  flex: none;
}
</style>
