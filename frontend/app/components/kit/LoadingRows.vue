<script setup lang="ts">
/** Skeleton rows, so a loading page has shape instead of being blank. */
withDefaults(defineProps<{ rows?: number, height?: string }>(), {
  rows: 6,
  height: 'h-12',
})
</script>

<template>
  <div class="space-y-2" role="status" aria-label="Loading">
    <div
      v-for="i in rows"
      :key="i"
      class="animate-pulse rounded-md border bg-card"
      :class="height"
      :style="{ animationDelay: `${i * 60}ms` }"
    />
  </div>
</template>
