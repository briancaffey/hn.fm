<script setup lang="ts">
import InfoHint from './InfoHint.vue'

/** One number with a label that says what it counts and why it matters. */
withDefaults(defineProps<{
  label: string
  value: string | number | null | undefined
  hint?: string
  /** Secondary text under the value — a breakdown or comparison. */
  detail?: string
  tone?: 'default' | 'ok' | 'running' | 'danger' | 'warn'
}>(), { tone: 'default', hint: undefined, detail: undefined })

const toneClass = {
  default: 'text-foreground',
  ok: 'text-ok',
  running: 'text-running',
  danger: 'text-danger',
  warn: 'text-warn',
}
</script>

<template>
  <div class="rounded-lg border bg-card px-3 py-2.5">
    <div class="flex items-center gap-1.5">
      <span class="text-xs font-medium text-muted-foreground">{{ label }}</span>
      <InfoHint v-if="hint" :text="hint" />
    </div>
    <div class="mt-1 text-2xl font-semibold tabular-nums" :class="toneClass[tone]">
      {{ value ?? '—' }}
    </div>
    <div v-if="detail" class="mt-0.5 text-xs text-muted-foreground">{{ detail }}</div>
    <slot />
  </div>
</template>
