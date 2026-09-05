<script setup lang="ts">
/**
 * The only two page layouts in the app.
 *
 * `document` — centred, max-width, scrolls as a whole. For reading: Digests,
 *   Services, Observability, Live, and the detail routes.
 * `board` — full-bleed, header pinned, body scrolls underneath. For dense
 *   lists where horizontal room matters: Stories, Triage, Segments.
 *
 * There were seven different container patterns before this; gutters and max
 * widths disagreed from page to page.
 */
withDefaults(defineProps<{ variant?: 'document' | 'board' }>(), {
  variant: 'document',
})
</script>

<template>
  <div v-if="variant === 'board'" class="flex h-full flex-col overflow-hidden">
    <slot name="header" />
    <div class="min-h-0 flex-1 overflow-y-auto">
      <slot />
    </div>
  </div>

  <div v-else class="mx-auto w-full max-w-[var(--page-max)] px-[var(--page-gutter)] py-8">
    <slot name="header" />
    <slot />
  </div>
</template>
