<script setup lang="ts">
import { computed } from 'vue'
import type { Article } from '@/types'
import { useArticlesStore } from '@/stores/articles'
import { useAgentStore } from '@/stores/agent'
import { useLayoutStore } from '@/stores/layout'
import { formatRelativeTime } from '@/composables/useRelativeTime'
import { useI18n } from '@/utils/i18n'

const props = defineProps<{
  article: Article
}>()

const articlesStore = useArticlesStore()
const agentStore = useAgentStore()
const layoutStore = useLayoutStore()
const { t } = useI18n()

const isFav = computed(() => articlesStore.favorites.has(props.article.id))

const relTime = computed(() =>
  formatRelativeTime(props.article.published_at, Date.now()),
)

const langLabel = computed(() =>
  props.article.language === 'zh' ? t('misc.zh') : t('misc.en'),
)

const sourceLabel = computed(() => t(`srcLabel.${props.article.source}`))

/** 点击 AI 解读 → 打开右侧 Agent 面板并预填问题 */
function askAi(): void {
  if (!layoutStore.panelVisible) layoutStore.togglePanel()
  agentStore.sendMessage(t('misc.digestPrompt') + props.article.title)
}
</script>

<template>
  <article class="acard" data-od-id="article-card">
    <span class="acard__corner" aria-hidden="true"></span>

    <h3 class="acard__title">
      <a :href="article.url" target="_blank" rel="noopener noreferrer" data-od-id="article-title">
        {{ article.title }}
      </a>
    </h3>

    <div class="acard__meta">
      <span class="acard__src" :class="`is-${article.source}`">{{ sourceLabel }}</span>
      <span class="acard__time mono">{{ relTime }}</span>
      <span class="acard__score mono">{{ article.score }}</span>
      <span class="acard__lang mono">{{ langLabel }}</span>
    </div>

    <p class="acard__summary">{{ article.summary }}</p>

    <div class="acard__tags">
      <span v-for="t in article.tags" :key="t" class="acard__tag">{{ t }}</span>
    </div>

    <div class="acard__actions">
      <button
        class="acard__fav"
        type="button"
        :class="{ 'is-active': isFav }"
        :aria-label="isFav ? t('misc.favOn') : t('misc.favOff')"
        @click="articlesStore.toggleFavorite(article.id)"
      >
        <span class="acard__fav-icon" aria-hidden="true"></span>
      </button>
      <button class="acard__ai" type="button" data-od-id="article-ai-btn" @click="askAi">
        {{ t('btn.ai') }}
      </button>
    </div>
  </article>
</template>

<style scoped>
.acard {
  position: relative;
  background: var(--surface);
  padding: 12px 14px 12px 16px;
  border: 1px solid transparent;
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield);
}
.acard:hover {
  background: var(--surface-hover);
}
.acard:hover .acard__corner {
  opacity: 1;
}

/* 左上角 4px×4px L 形青色角标 */
.acard__corner {
  position: absolute;
  top: -1px;
  left: -1px;
  width: 9px;
  height: 9px;
  border-top: 2px solid var(--accent);
  border-left: 2px solid var(--accent);
  opacity: 0.45;
  transition: opacity var(--dur) var(--ease-endfield);
}

.acard__title {
  margin: 0 0 6px;
  font-family: var(--font-body);
  font-weight: 500;
  font-size: 15px;
  line-height: 1.35;
}
.acard__title a {
  color: var(--fg);
  text-decoration: none;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color var(--dur) var(--ease-endfield);
}
.acard__title a:hover {
  color: var(--accent);
}

/* 元信息行 */
.acard__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.acard__src {
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 1px 8px;
  background: var(--input-bg);
  border: 1px solid var(--border);
  transform: skewX(-10deg);
}
.acard__src > * {
  transform: skewX(10deg);
}
.acard__src.is-hackernews {
  color: var(--accent);
  border-color: var(--accent-35);
}
.acard__src.is-arxiv {
  color: var(--blue);
  border-color: rgba(59, 130, 246, 0.35);
}
.acard__src.is-huggingface_papers {
  color: var(--purple);
  border-color: rgba(168, 85, 247, 0.35);
}
.acard__src.is-rss {
  color: var(--warn);
  border-color: rgba(232, 122, 58, 0.35);
}
.acard__time,
.acard__lang {
  font-size: 10px;
  color: var(--muted);
}
.acard__score {
  font-size: 11px;
  font-weight: 600;
  color: var(--fg);
}
.acard__score::before {
  content: '▴';
  color: var(--accent);
  margin-right: 3px;
  font-size: 9px;
}

.acard__summary {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 标签行 */
.acard__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.acard__tag {
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: var(--accent);
  background: var(--accent-10);
  border: 1px solid var(--accent-18);
  padding: 1px 8px;
  transform: skewX(-10deg);
  white-space: nowrap;
}

/* 操作区 */
.acard__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.acard__fav {
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
.acard__fav:hover {
  border-color: var(--accent);
  background: var(--surface-raised);
}
.acard__fav-icon {
  width: 11px;
  height: 11px;
  border: 1.5px solid var(--muted);
  clip-path: polygon(50% 100%, 0 65%, 8% 15%, 50% 30%, 92% 15%, 100% 65%);
  background: transparent;
  transition: border-color var(--dur) var(--ease-endfield),
    background var(--dur) var(--ease-endfield);
}
.acard__fav.is-active .acard__fav-icon {
  border-color: var(--accent);
  background: var(--accent);
}
.acard__ai {
  height: 26px;
  padding: 0 12px;
  background: var(--accent-10);
  border: 1px solid var(--accent-40);
  color: var(--accent);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  clip-path: polygon(0 0, 100% 0, calc(100% - 6px) 100%, 0 100%);
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield);
}
.acard__ai:hover {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-ink);
}
</style>
