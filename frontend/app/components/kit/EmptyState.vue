<script setup lang="ts">
import { Icon } from '#components'

/**
 * An empty list should say what would fill it and how to make that happen.
 * "No segments found." told the reader nothing actionable.
 */
withDefaults(defineProps<{
  icon?: string
  title: string
  /** What would appear here, and what to do to get it. */
  body?: string
}>(), { icon: 'lucide:inbox', body: undefined })
</script>

<template>
  <div class="flex flex-col items-center justify-center rounded-lg border border-dashed px-6 py-12 text-center">
    <Icon :name="icon" class="h-8 w-8 text-muted-foreground/50" />
    <p class="mt-3 text-sm font-medium">{{ title }}</p>
    <p v-if="body" class="mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">{{ body }}</p>
    <div v-if="$slots.action" class="mt-4"><slot name="action" /></div>
  </div>
</template>
