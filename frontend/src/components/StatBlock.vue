<script setup lang="ts">
defineProps<{
  label: string
  value: string
  /** 关键数据：数字加粗 + 青色 */
  accent?: boolean
  /** 小型状态灯（如总采集次数） */
  dot?: 'accent' | 'warn' | 'off'
}>()
</script>

<template>
  <div class="stat" data-od-id="stat-block">
    <span class="stat__label">{{ label }}</span>
    <span class="stat__value mono" :class="{ 'is-accent': accent }">
      <span
        v-if="dot"
        class="stat__dot"
        :class="`is-${dot}`"
        aria-hidden="true"
      ></span>
      {{ value }}
    </span>
  </div>
</template>

<style scoped>
.stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--surface);
  border-left: 2px solid var(--accent);
  padding: 8px 12px;
  transform: skewX(-10deg);
}
.stat > * {
  transform: skewX(10deg);
}

.stat__label {
  font-family: var(--font-display);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 1.5px;
  color: var(--muted);
  text-transform: uppercase;
  white-space: nowrap;
}

.stat__value {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--fg);
  white-space: nowrap;
}
.stat__value.is-accent {
  color: var(--accent);
  font-weight: 700;
}

.stat__dot {
  width: 6px;
  height: 6px;
  flex: none;
}
.stat__dot.is-accent {
  background: var(--accent);
}
.stat__dot.is-warn {
  background: var(--warn);
}
.stat__dot.is-off {
  background: var(--disabled);
}
</style>
