<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useArticlesStore } from '@/stores/articles'
import { formatRelativeTime } from '@/composables/useRelativeTime'
import { useI18n } from '@/utils/i18n'

const articlesStore = useArticlesStore()
const { t, lang } = useI18n()

const todayTop10 = computed(() => articlesStore.todayTop10)
const weekTop10 = computed(() => articlesStore.weekTop10)

const isEmpty = computed(() => todayTop10.value.length === 0 && weekTop10.value.length === 0)

function rankClass(i: number): string {
  return i < 3 ? 'is-top' : ''
}

function relTime(iso: string | null): string {
  return formatRelativeTime(iso, Date.now(), lang.value)
}

onMounted(() => {
  if (articlesStore.articles.length === 0) {
    void articlesStore.fetchArticles()
  }
})
</script>

<template>
  <div class="hview" data-od-id="hotlist-view">
    <!-- 空状态 -->
    <div v-if="isEmpty" class="hview__empty">
      <span class="hview__empty-mark" aria-hidden="true"></span>
      <p class="hview__empty-title">NO DATA YET</p>
      <p class="hview__empty-sub">资料库暂无文章，请先触发一次采集</p>
    </div>

    <!-- 双列布局 -->
    <div v-else class="hview__cols">
      <!-- 今日 Top 10 -->
      <section class="hview__col" data-od-id="hotlist-today">
        <header class="hview__col-head">
          <h3 class="hview__col-title">{{ t('hotlist.today') }}</h3>
          <span class="hview__col-count mono">{{ todayTop10.length }}</span>
        </header>
        <ol class="hview__list">
          <li v-for="(a, i) in todayTop10" :key="a.id" class="hview__item">
            <span class="hview__rank mono" :class="rankClass(i)">
              {{ String(i + 1).padStart(2, '0') }}
            </span>
            <div class="hview__item-body">
              <a
                class="hview__item-title"
                :href="a.url"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ a.title }}
              </a>
              <div class="hview__item-meta">
                <span class="hview__item-src" :class="`is-${a.source}`">
                  {{ a.source }}
                </span>
                <span class="hview__score mono">{{ a.score }}</span>
                <span class="hview__time mono">
                  {{ relTime(a.published_at) }}
                </span>
              </div>
            </div>
          </li>
        </ol>
      </section>

      <!-- 列间分割线 -->
      <span class="hview__divider" aria-hidden="true"></span>

      <!-- 近 7 天 Top 10 -->
      <section class="hview__col" data-od-id="hotlist-week">
        <header class="hview__col-head">
          <h3 class="hview__col-title">{{ t('hotlist.week') }}</h3>
          <span class="hview__col-count mono">{{ weekTop10.length }}</span>
        </header>
        <ol class="hview__list">
          <li v-for="(a, i) in weekTop10" :key="a.id" class="hview__item">
            <span class="hview__rank mono" :class="rankClass(i)">
              {{ String(i + 1).padStart(2, '0') }}
            </span>
            <div class="hview__item-body">
              <a
                class="hview__item-title"
                :href="a.url"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ a.title }}
              </a>
              <div class="hview__item-meta">
                <span class="hview__item-src" :class="`is-${a.source}`">
                  {{ a.source }}
                </span>
                <span class="hview__score mono">{{ a.score }}</span>
                <span class="hview__time mono">
                  {{ relTime(a.published_at) }}
                </span>
              </div>
            </div>
          </li>
        </ol>
      </section>
    </div>
  </div>
</template>

<style scoped>
.hview {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
}

.hview__cols {
  display: grid;
  grid-template-columns: 1fr 1px 1fr;
  min-height: 100%;
}
.hview__col {
  min-width: 0;
  padding-bottom: 16px;
}

/* 列间 1px 分割线 */
.hview__divider {
  background: var(--border);
}

.hview__col-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.hview__col-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--fg);
}
.hview__col-count {
  font-size: 10px;
  color: var(--muted);
}

.hview__list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.hview__item {
  display: flex;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
  transition: background var(--dur) var(--ease-endfield);
}
.hview__item:hover {
  background: var(--surface-hover);
}

.hview__rank {
  font-size: 20px;
  font-weight: 700;
  color: var(--muted);
  line-height: 1.2;
  flex: none;
  width: 24px;
}
.hview__rank.is-top {
  color: var(--accent);
}

.hview__item-body {
  min-width: 0;
  flex: 1 1 auto;
}
.hview__item-title {
  display: block;
  font-size: 13px;
  line-height: 1.4;
  color: var(--fg);
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color var(--dur) var(--ease-endfield);
}
.hview__item-title:hover {
  color: var(--accent);
}

.hview__item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.hview__item-src {
  font-family: var(--font-display);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  padding: 0 6px;
  background: var(--input-bg);
  border: 1px solid var(--border);
  transform: skewX(-10deg);
}
.hview__item-src.is-hackernews {
  color: var(--accent);
}
.hview__item-src.is-arxiv {
  color: var(--blue);
}
.hview__item-src.is-huggingface_papers {
  color: var(--purple);
}
.hview__item-src.is-rss {
  color: var(--warn);
}
.hview__item-src.is-github {
  color: var(--green);
}
.hview__score {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
}
.hview__time {
  font-size: 10px;
  color: var(--disabled);
  margin-left: auto;
}

/* 空状态 */
.hview__empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.hview__empty-mark {
  width: 36px;
  height: 36px;
  border: 2px solid var(--disabled);
  position: relative;
}
.hview__empty-mark::after {
  content: '';
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 8px;
  height: 8px;
  background: var(--accent);
}
.hview__empty-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--fg);
}
.hview__empty-sub {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
</style>
