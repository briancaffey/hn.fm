<script setup lang="ts">
import InfoHint from './InfoHint.vue'

/**
 * One header shape for every page: what this is, why it matters, and the
 * actions that belong to it. Headings were four different sizes before, and
 * two pages had no description at all.
 */
withDefaults(defineProps<{
  title: string
  /** One line: what this page shows and why you would look at it. */
  subtitle?: string
  /** Longer "why this matters", behind the info icon. */
  hint?: string
  /** Small facts under the title — counts, freshness, totals. */
  meta?: string[]
  variant?: 'document' | 'board'
}>(), {
  variant: 'document',
  subtitle: undefined,
  hint: undefined,
  meta: undefined,
})
</script>

<template>
  <header
    :class="variant === 'board'
      ? 'shrink-0 border-b bg-card px-[var(--page-gutter)] py-3'
      : 'mb-6'"
  >
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="flex items-center gap-1.5">
          <h1 :class="variant === 'board' ? 'text-base font-semibold' : 'text-xl font-semibold'">
            {{ title }}
          </h1>
          <InfoHint v-if="hint" :text="hint" />
        </div>
        <p v-if="subtitle" class="mt-0.5 text-xs text-muted-foreground">
          {{ subtitle }}
        </p>
        <p v-if="meta?.length" class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <template v-for="(m, i) in meta" :key="m">
            <span v-if="i > 0" aria-hidden="true" class="opacity-40">·</span>
            <span>{{ m }}</span>
          </template>
        </p>
      </div>
      <div v-if="$slots.actions" class="flex shrink-0 flex-wrap items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <slot name="below" />
  </header>
</template>
