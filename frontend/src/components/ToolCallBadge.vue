<script setup lang="ts">
import type { ToolName } from '@/types'
import { useI18n } from '@/utils/i18n'

defineProps<{
  name: ToolName
  status: 'calling' | 'done'
}>()

const { t } = useI18n()
</script>

<template>
  <span
    class="tool-badge"
    :class="`is-${status}`"
    data-od-id="tool-call-badge"
  >
    <span class="tool-badge__pulse" aria-hidden="true"></span>
    <span class="tool-badge__name">{{ name }}</span>
    <span class="tool-badge__status mono">{{ t(status === 'calling' ? 'misc.calling' : 'misc.done') }}</span>
  </span>
</template>

<style scoped>
.tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transform: skewX(-10deg);
  background: var(--input-bg);
  border: 1px solid var(--border-strong);
  padding: 2px 8px;
  font-family: var(--font-display);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 1px;
}
.tool-badge > * {
  transform: skewX(10deg);
}

.tool-badge__pulse {
  width: 6px;
  height: 6px;
  background: var(--accent);
}
.tool-badge.is-calling .tool-badge__pulse {
  background: var(--warn);
  animation: ef-blink 0.8s steps(2, start) infinite;
}

.tool-badge__name {
  color: var(--fg);
}
.tool-badge__status {
  font-size: 9px;
  color: var(--muted);
}
.tool-badge.is-done .tool-badge__status {
  color: var(--accent);
}

@keyframes ef-blink {
  50% {
    opacity: 0.2;
  }
}
</style>
