<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ChatMessage } from '@/types'
import { formatRelativeTime } from '@/composables/useRelativeTime'
import ToolCallBadge from '@/components/ToolCallBadge.vue'
import { useI18n } from '@/utils/i18n'

const props = defineProps<{
  message: ChatMessage
  /** 流式渲染中的增量文本（assistant 正在输出时传入） */
  streamingText?: string
  /** 流式进行中：显示方块光标 */
  streaming?: boolean
  activeTool?: { name: string; status: 'calling' | 'done' } | null
}>()

const { lang } = useI18n()
const isUser = computed(() => props.message.role === 'user')

const time = computed(() =>
  formatRelativeTime(props.message.timestamp, Date.now(), lang.value),
)

/** 允许保留的标签：只覆盖 Markdown 实际产出的结构（段落/代码/列表/表格/标题/引用） */
const ALLOWED_TAGS = [
  'p', 'br', 'hr', 'strong', 'em', 'b', 'i', 'u', 's', 'del',
  'code', 'pre', 'blockquote', 'ul', 'ol', 'li', 'a',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
]

/** 允许保留的属性：不含 src / style / on*，因此图片与内联样式会被剥离 */
const ALLOWED_ATTR = ['href', 'title', 'target', 'rel', 'class']

/** 外链统一新窗口 + noopener，防止被引用页面通过 window.opener 反向操作本页 */
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  const el = node as Element
  if (el.tagName === 'A') {
    el.setAttribute('target', '_blank')
    el.setAttribute('rel', 'noopener noreferrer nofollow')
  }
})

/**
 * Markdown → 安全 HTML。
 *
 * `marked` 只做语法转换、不做安全过滤（v12 起内置 sanitize 已移除），而 Agent 回答
 * 会引用采集到的外部标题/摘要，未经消毒直接交给 `v-html` 会形成存储型 XSS
 * （恶意 RSS 条目 → 入库 → 被 LLM 原样引用 → 在本页执行脚本）。因此渲染结果一律
 * 过 DOMPurify 白名单：非白名单标签与属性（`<script>`、`onerror=`、`src=` 等）被剥离。
 */
function renderSafe(text: string): string {
  const html = marked.parse(text, { async: false, breaks: true }) as string
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    ALLOW_DATA_ATTR: false,
  })
}

/** 流式内容（含 Markdown 渲染，代码块等） */
const rendered = computed(() => renderSafe(props.streamingText ?? props.message.content))

/** 展示用的工具调用序列：静态消息用 message.toolCalls，流式中用 activeTool */
const toolCalls = computed(() => {
  if (props.streaming) {
    return props.activeTool ? [props.activeTool] : []
  }
  return props.message.toolCalls ?? []
})
</script>

<template>
  <div class="bubble" :class="isUser ? 'is-user' : 'is-ai'" data-od-id="message-bubble">
    <div class="bubble__body">
      <!-- 工具调用指示器 -->
      <div v-if="toolCalls.length" class="bubble__tools">
        <ToolCallBadge
          v-for="t in toolCalls"
          :key="t.name"
          :name="t.name"
          :status="t.status"
        />
      </div>

      <!-- 正文：流式中逐字 + 光标 -->
      <div
        class="bubble__content markdown"
        v-html="rendered"
      ></div>
      <span
        v-if="streaming"
        class="bubble__cursor"
        aria-hidden="true"
      ></span>

      <!-- 时间戳 -->
      <div class="bubble__time mono">{{ time }}</div>
    </div>
  </div>
</template>

<style scoped>
.bubble {
  display: flex;
  margin-bottom: 14px;
}
.bubble.is-user {
  justify-content: flex-end;
}
.bubble.is-ai {
  justify-content: flex-start;
}

.bubble__body {
  position: relative;
  max-width: 86%;
  padding: 10px 12px;
}
.bubble.is-user .bubble__body {
  background: var(--surface-hover);
  border-left: 2px solid var(--accent);
}
.bubble.is-ai .bubble__body {
  background: var(--surface);
  border-right: 2px solid var(--disabled);
}

.bubble__tools {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.bubble__content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--fg);
  word-break: break-word;
}
.bubble.is-user .bubble__content {
  color: var(--fg);
}

/* Markdown 细节 */
.bubble__content :deep(p) {
  margin: 0 0 8px;
}
.bubble__content :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble__content :deep(strong) {
  color: var(--accent);
  font-weight: 600;
}
.bubble__content :deep(em) {
  color: var(--muted);
}
.bubble__content :deep(code) {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent);
  background: var(--input-bg);
  padding: 1px 5px;
  border: 1px solid var(--border);
}
.bubble__content :deep(pre) {
  background: var(--bg);
  border: 1px solid var(--border);
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.bubble__content :deep(pre code) {
  background: transparent;
  border: none;
  padding: 0;
  color: var(--fg);
}
.bubble__content :deep(blockquote) {
  margin: 8px 0;
  padding: 4px 10px;
  border-left: 2px solid var(--accent);
  background: var(--input-bg);
  color: var(--muted);
  font-size: 12px;
}
.bubble__content :deep(ul),
.bubble__content :deep(ol) {
  margin: 4px 0 8px;
  padding-left: 18px;
}
.bubble__content :deep(li) {
  margin: 2px 0;
}

/* 流式方块光标 */
.bubble__cursor {
  display: inline-block;
  width: 7px;
  height: 13px;
  background: var(--accent);
  margin-left: 2px;
  vertical-align: -2px;
  animation: cursor-blink 0.9s steps(2, start) infinite;
}
@keyframes cursor-blink {
  50% {
    opacity: 0;
  }
}

.bubble__time {
  margin-top: 6px;
  font-size: 10px;
  color: var(--disabled);
  text-align: right;
}

/* AI 回答中的引用链接：淡蓝色（深/浅底均清晰）。
   注意：<a> 由 v-html（marked 渲染）动态生成，不带 data-v 属性，
   必须用 :deep() 穿透 scoped，否则编译成 a[data-v-xxx] 永不命中 */
.bubble.is-ai :deep(.markdown a) {
  color: #8ab4f8;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.bubble.is-ai :deep(.markdown a:hover) {
  color: #a8c8ff;
}
</style>
