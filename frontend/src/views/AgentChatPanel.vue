<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
// ElMessage 手动 deep import（包入口导入会拉全量 element-plus）
import { ElMessage } from 'element-plus/es/components/message/index'
import 'element-plus/es/components/message/style/css'
import { useAgentStore } from '@/stores/agent'
import MessageBubble from '@/components/MessageBubble.vue'
import { useI18n } from '@/utils/i18n'

const agentStore = useAgentStore()
const { t, lang } = useI18n()
const { messages, isStreaming, isWaiting, activeTool, rounds, maxChars, maxHistory, quickActions } =
  storeToRefs(agentStore)

const input = ref('')
const listEl = ref<HTMLElement | null>(null)

const charCount = computed(() => input.value.length)
const overLimit = computed(() => input.value.length > maxChars.value)

const historyLabel = computed(
  () => `${t('misc.history')}: ${rounds.value}/${maxHistory.value} ${t('misc.rounds')}`,
)

/** 流式消息视图：最后一条 assistant 消息在流式中时，实时渲染增量文本 */
const streamView = computed(() => {
  if (!isStreaming.value) return null
  const last = messages.value[messages.value.length - 1]
  if (last && last.role === 'assistant') return last
  return null
})

function scrollToBottom(): void {
  void nextTick(() => {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  })
}

function send(): void {
  const text = input.value.trim()
  if (!text || overLimit.value || isStreaming.value) return
  agentStore.sendMessage(text)
  input.value = ''
  scrollToBottom()
}

function onKeydown(e: Event): void {
  const evt = e as KeyboardEvent
  if (evt.key === 'Enter' && !evt.shiftKey) {
    evt.preventDefault()
    send()
  }
}

function useQuick(prompt: string): void {
  input.value = prompt
  send()
}

function stop(): void {
  // 中断流式输出：按钮回到 SEND 态即反馈（保留已产出的气泡）
  agentStore.stopStreaming()
}

function onClear(): void {
  agentStore.clearHistory()
  ElMessage.info(t('misc.history') + ' CLEARED')
}

function onHistory(): void {
  agentStore.loadHistory()
  scrollToBottom()
}

watch(
  () => [messages.value.length, agentStore.replyBuffer],
  () => scrollToBottom(),
)

onMounted(() => {
  agentStore.loadInitial()
  scrollToBottom()
})

onBeforeUnmount(() => {
  // 卸载时中止流式输出（保留消息；keep-alive 缓存复用时不破坏对话）
  agentStore.stopStreaming()
})
</script>

<template>
  <div class="apanel" data-od-id="agent-panel">
    <!-- 顶部标题栏 -->
    <div class="apanel__head">
      <h2 class="apanel__title">{{ lang === 'zh' ? '智能体终端' : 'AGENT TERMINAL' }}</h2>
      <div class="apanel__head-actions">
        <button
          class="apanel__btn"
          type="button"
          :title="t('btn.history')"
          :aria-label="t('btn.history')"
          data-od-id="agent-history"
          @click="onHistory"
        >
          {{ t('btn.history') }}
        </button>
        <button
          class="apanel__btn"
          type="button"
          :title="t('btn.clear')"
          :aria-label="t('btn.clear')"
          data-od-id="agent-clear"
          @click="onClear"
        >
          {{ t('btn.clear') }}
        </button>
      </div>
    </div>

    <!-- 对话消息区（独立滚动） -->
    <div ref="listEl" class="apanel__list">
      <MessageBubble
        v-for="(m, i) in messages"
        :key="i"
        :message="m"
        :streaming-text="streamView && m === streamView ? agentStore.replyBuffer : undefined"
        :streaming="streamView === m"
        :active-tool="streamView === m ? activeTool : undefined"
      />

      <!-- LLM 等待中：转圈 + 正在搜索中（响应返回后切换为流式输出） -->
      <div v-if="isWaiting" class="apanel__waiting" data-od-id="agent-waiting">
        <span class="apanel__waiting-spinner" aria-hidden="true"></span>
        <span class="apanel__waiting-text">{{ t('misc.searching') }}</span>
      </div>
    </div>

    <!-- 快捷操作区 -->
    <div class="apanel__quick">
      <button
        v-for="q in quickActions"
        :key="q.key"
        type="button"
        class="apanel__quick-btn"
        :disabled="isStreaming"
        data-od-id="quick-action"
        @click="useQuick(q.prompt)"
      >
        {{ t(`quick.${q.key}`) }}
      </button>
    </div>

    <!-- 底部输入区 -->
    <div class="apanel__input">
      <el-input
        v-model="input"
        type="textarea"
        :rows="2"
        :maxlength="maxChars"
        resize="none"
        :placeholder="t('placeholder.agent')"
        :autosize="{ minRows: 2, maxRows: 4 }"
        @keydown="onKeydown"
      />
      <div class="apanel__input-bar">
        <span class="apanel__count mono" :class="{ 'is-over': overLimit }">
          {{ charCount }}/{{ maxChars }}
        </span>
        <button
          type="button"
          class="apanel__send"
          :class="{ 'is-stop': isStreaming }"
          :disabled="isStreaming ? false : !input.trim() || overLimit"
          data-od-id="agent-send"
          @click="isStreaming ? stop() : send()"
        >
          {{ isStreaming ? t('btn.stop') : t('btn.send') }}
        </button>
      </div>
      <div class="apanel__hint mono">{{ historyLabel }}</div>
    </div>
  </div>
</template>

<style scoped>
.apanel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  min-width: 0;
}

/* ---------- 顶部标题栏 ---------- */
.apanel__head {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 44px;
  padding: 0 12px;
  flex: none;
  border-bottom: 1px solid var(--border);
}
.apanel__title {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 2px;
  color: var(--fg);
  white-space: nowrap;
}
.apanel__head-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}
.apanel__btn {
  height: 26px;
  padding: 0 8px;
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  font-family: var(--font-display);
  font-size: 10px;
  letter-spacing: 1px;
  cursor: pointer;
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield), color var(--dur) var(--ease-endfield);
}
.apanel__btn:hover {
  background: var(--surface-hover);
  border-color: var(--accent);
  color: var(--accent);
}
/* ---------- 消息区 ---------- */
.apanel__list {
  flex: 1 1 auto;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 14px 12px;
}

/* ---------- LLM 等待中指示 ---------- */
.apanel__waiting {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 2px;
  color: var(--muted);
}
.apanel__waiting-spinner {
  width: 12px;
  height: 12px;
  flex: none;
  border: 2px solid var(--accent-18);
  border-top-color: var(--accent);
  animation: apanel-spin 0.8s linear infinite;
}
.apanel__waiting-text {
  font-family: var(--font-display);
  font-size: 11px;
  letter-spacing: 1.5px;
}
@keyframes apanel-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ---------- 快捷操作区 ---------- */
.apanel__quick {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  padding: 0 12px 10px;
  flex: none;
  border-bottom: 1px solid var(--border);
}
.apanel__quick-btn {
  height: 30px;
  background: var(--input-bg);
  border: 1px solid var(--border);
  color: var(--muted);
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1px;
  transform: skewX(-10deg);
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background var(--dur) var(--ease-endfield),
    border-color var(--dur) var(--ease-endfield), color var(--dur) var(--ease-endfield);
}
.apanel__quick-btn > * {
  transform: skewX(10deg);
}
.apanel__quick-btn:hover:not(:disabled) {
  background: var(--surface-hover);
  border-color: var(--accent);
  color: var(--accent);
}
.apanel__quick-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

/* ---------- 底部输入区 ---------- */
.apanel__input {
  flex: none;
  padding: 10px 12px 12px;
  border-top: 1px solid var(--border);
}
.apanel__input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}
.apanel__count {
  font-size: 10px;
  color: var(--disabled);
}
.apanel__count.is-over {
  color: var(--warn);
}
.apanel__send {
  margin-left: auto;
  height: 30px;
  padding: 0 18px;
  background: var(--accent);
  border: none;
  color: var(--accent-ink);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  cursor: pointer;
  clip-path: polygon(0 0, 100% 0, calc(100% - 8px) 100%, 0 100%);
  transition: background var(--dur) var(--ease-endfield),
    transform 80ms var(--ease-endfield);
}
.apanel__send:hover:not(:disabled) {
  background: var(--accent-dim);
}
.apanel__send:active:not(:disabled) {
  transform: scale(0.98);
}
.apanel__send:disabled {
  background: var(--surface-raised);
  color: var(--disabled);
  cursor: not-allowed;
}
/* 停止生成态：流式中按钮变为 STOP（警示色），点击中断输出 */
.apanel__send.is-stop {
  background: var(--warn);
  color: #fff;
}
.apanel__send.is-stop:hover {
  background: var(--warn);
  filter: brightness(0.9);
}
.apanel__send.is-stop:active {
  transform: scale(0.98);
}
.apanel__hint {
  margin-top: 6px;
  font-size: 9px;
  letter-spacing: 1px;
  color: var(--disabled);
}
</style>
