<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useSourcesStore } from '@/stores/sources'
import { useAgentStore } from '@/stores/agent'
import { useLayoutStore } from '@/stores/layout'
import { useI18n } from '@/utils/i18n'
import { useTheme } from '@/composables/useTheme'

const sourcesStore = useSourcesStore()
const agentStore = useAgentStore()
const layoutStore = useLayoutStore()
const { lang, t, toggleLang } = useI18n()
const { theme, toggleTheme } = useTheme()

const globalSearch = ref('')
const clock = ref('')
let timer: ReturnType<typeof setInterval> | null = null

/** 采集状态：green 正常 / orange 限流（对应机器之心 RSS 429 已知问题） */
const collectionState = computed(() => {
  if (sourcesStore.collecting) return 'running'
  if (sourcesStore.warning) return 'warn'
  return 'ok'
})

const stateLabel = computed(() => {
  if (collectionState.value === 'running') return t('misc.collecting')
  if (collectionState.value === 'warn') return 'RATE LIMITED'
  return t('misc.online')
})

const themeLabel = computed(() => (theme.value === 'yellow' ? 'YELLOW' : 'CYAN'))

function submitGlobalSearch(): void {
  const kw = globalSearch.value.trim()
  if (!kw) return
  // 全局搜索：客户端过滤提示 → 引导至 Agent 面板做语义检索
  agentStore.sendMessage(t('misc.searchPrompt') + kw + t('misc.searchPromptEnd'))
  globalSearch.value = ''
}

onMounted(() => {
  const tick = () => {
    clock.value = new Date().toLocaleTimeString('zh-CN', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }
  tick()
  timer = setInterval(tick, 1000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="topbar" data-od-id="topbar">
    <!-- 品牌 -->
    <div class="topbar__brand">
      <span class="topbar__logo">AI INTEL</span>
      <span class="topbar__sub">RESEARCH PLATFORM</span>
    </div>

    <!-- 全局搜索（客户端过滤提示） -->
    <div class="topbar__search">
      <span class="topbar__search-icon" aria-hidden="true"></span>
      <el-input
        v-model="globalSearch"
        :placeholder="t('placeholder.search')"
        clearable
        @keyup.enter="submitGlobalSearch"
      />
    </div>

    <!-- 右侧状态区 -->
    <div class="topbar__right">
      <!-- 中英文切换 -->
      <button
        class="topbar__lang"
        :class="lang === 'en' ? 'is-en' : 'is-cn'"
        type="button"
        :title="t('misc.themeTitle')"
        data-od-id="lang-toggle"
        @click="toggleLang"
      >
        <span class="topbar__lang-cn">中</span>
        <span class="topbar__lang-sep">/</span>
        <span class="topbar__lang-en">EN</span>
      </button>

      <!-- 视觉主题切换（青 / 黄） -->
      <button
        class="topbar__theme"
        :class="`is-${theme}`"
        type="button"
        :title="t('misc.themeTitle')"
        data-od-id="theme-toggle"
        @click="toggleTheme"
      >
        <span class="topbar__theme-swatch" aria-hidden="true"></span>
        <span class="topbar__theme-label">{{ themeLabel }}</span>
      </button>

      <!-- AI 对话面板 展开/折叠 -->
      <button
        class="topbar__panel"
        :class="{ 'is-collapsed': !layoutStore.panelVisible }"
        type="button"
        :title="layoutStore.panelVisible ? t('misc.panelClose') : t('misc.panelOpen')"
        :aria-label="layoutStore.panelVisible ? t('misc.panelClose') : t('misc.panelOpen')"
        data-od-id="panel-toggle"
        @click="layoutStore.togglePanel()"
      >
        <span class="topbar__panel-icon" aria-hidden="true"></span>
      </button>

      <div class="topbar__clock mono">{{ clock }}</div>

      <div class="topbar__state">
        <span
          class="topbar__state-dot"
          :class="`is-${collectionState}`"
          aria-hidden="true"
        ></span>
        <span class="topbar__state-label">{{ stateLabel }}</span>
      </div>

      <button class="topbar__avatar" type="button" :title="t('misc.zh')" aria-label="用户" data-od-id="user-avatar">
        OD
      </button>
    </div>
  </div>
</template>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  gap: 20px;
  height: 56px;
  padding: 0 16px;
  background: var(--bg);
}

/* 品牌 */
.topbar__brand {
  display: flex;
  flex-direction: column;
  justify-content: center;
  line-height: 1.1;
  flex: none;
}
.topbar__logo {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 17px;
  letter-spacing: 3px;
  color: var(--accent);
}
.topbar__sub {
  font-family: var(--font-display);
  font-size: 9px;
  letter-spacing: 2.5px;
  color: var(--muted);
  margin-top: 2px;
}

/* 搜索 */
.topbar__search {
  flex: 1 1 auto;
  max-width: 480px;
  margin: 0 auto;
  position: relative;
}
.topbar__search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 10px;
  height: 10px;
  border: 1.5px solid var(--disabled);
  z-index: 1;
  pointer-events: none;
}
.topbar__search-icon::after {
  content: '';
  position: absolute;
  right: -3px;
  bottom: -3px;
  width: 4px;
  height: 1.5px;
  background: var(--disabled);
  transform: rotate(45deg);
}
.topbar__search :deep(.el-input__wrapper) {
  padding-left: 30px;
}

/* 右侧 */
.topbar__right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
}
.topbar__clock {
  font-size: 11px;
  color: var(--muted);
}
.topbar__state {
  display: flex;
  align-items: center;
  gap: 6px;
}
.topbar__state-dot {
  width: 8px;
  height: 8px;
  flex: none;
}
.topbar__state-dot.is-ok {
  background: var(--accent);
}
.topbar__state-dot.is-warn {
  background: var(--warn);
}
.topbar__state-dot.is-running {
  background: var(--warn);
  animation: ef-blink 1s steps(2, start) infinite;
}
.topbar__state-label {
  font-family: var(--font-display);
  font-size: 10px;
  letter-spacing: 1.5px;
  color: var(--muted);
}
@keyframes ef-blink {
  50% {
    opacity: 0.25;
  }
}

/* 中英文切换（斜切，与 example.html 一致） */
.topbar__lang {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding: 0 10px;
  background: var(--input-bg);
  border: 1px solid var(--border);
  color: var(--muted);
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  transform: skewX(-10deg);
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield), color var(--dur) var(--ease-endfield);
}
.topbar__lang > * {
  transform: skewX(10deg);
}
.topbar__lang:hover {
  background: var(--surface-hover);
  border-color: var(--accent);
  color: var(--accent);
}
.topbar__lang-sep {
  color: var(--disabled);
  font-size: 9px;
}
.topbar__lang.is-en .topbar__lang-cn {
  color: var(--disabled);
}
.topbar__lang.is-en .topbar__lang-en {
  color: var(--accent);
}
.topbar__lang:not(.is-en) .topbar__lang-cn {
  color: var(--accent);
}
.topbar__lang:not(.is-en) .topbar__lang-en {
  color: var(--disabled);
}

/* 主题切换（斜切 + 发光色块） */
.topbar__theme {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding: 0 10px;
  background: var(--input-bg);
  border: 1px solid var(--border);
  color: var(--muted);
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  cursor: pointer;
  transform: skewX(-10deg);
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield), color var(--dur) var(--ease-endfield);
}
.topbar__theme > * {
  transform: skewX(10deg);
}
.topbar__theme:hover {
  background: var(--surface-hover);
  border-color: var(--accent);
  color: var(--accent);
}
.topbar__theme-swatch {
  width: 8px;
  height: 8px;
  border: 1px solid var(--border-strong);
}
.topbar__theme.is-yellow .topbar__theme-swatch {
  background: var(--accent);
  border-color: var(--accent);
  box-shadow: 0 0 6px var(--accent-40);
}
.topbar__theme.is-cyan .topbar__theme-swatch {
  background: var(--accent);
  border-color: var(--accent);
  box-shadow: 0 0 6px var(--accent-40);
}
.topbar__theme-label {
  color: var(--muted);
}
.topbar__theme.is-yellow .topbar__theme-label {
  color: var(--accent);
}
.topbar__theme.is-cyan .topbar__theme-label {
  color: var(--accent);
}

/* AI 对话面板 展开/折叠 */
.topbar__panel {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 24px;
  padding: 0;
  background: var(--input-bg);
  border: 1px solid var(--border);
  cursor: pointer;
  transform: skewX(-10deg);
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield);
}
.topbar__panel:hover {
  background: var(--surface-hover);
  border-color: var(--accent);
}
.topbar__panel-icon {
  width: 8px;
  height: 8px;
  border-right: 2px solid var(--muted);
  border-top: 2px solid var(--muted);
  transform: rotate(45deg);
  transition: border-color var(--dur) var(--ease-endfield);
}
.topbar__panel.is-collapsed .topbar__panel-icon {
  transform: rotate(225deg);
  border-color: var(--accent);
}
.topbar__panel:hover .topbar__panel-icon {
  border-color: var(--accent);
}

.topbar__avatar {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  color: var(--fg);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  cursor: pointer;
  clip-path: polygon(0 0, 100% 0, calc(100% - 6px) 100%, 0 100%);
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield);
}
.topbar__avatar:hover {
  background: var(--surface-hover);
  border-color: var(--accent);
}
</style>
