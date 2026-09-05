<script setup lang="ts">
import { Icon } from '#components'

/**
 * Where you are in the story → run → segment hierarchy, and the way back up.
 *
 * The detail routes are three levels deep and previously offered only a single
 * "← Back to Run N" link, so there was no way to see the whole path or jump
 * two levels at once. The segment page went further and rendered its own full
 * navigation bar and footer inside the sidebar layout — a second set of app
 * chrome, complete with a link to a page that no longer exists.
 */
defineProps<{ items: Array<{ label: string, to?: string }> }>()
</script>

<template>
  <nav aria-label="Breadcrumb" class="mb-3 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
    <template v-for="(c, i) in items" :key="c.label">
      <Icon v-if="i > 0" name="lucide:chevron-right" class="h-3 w-3 shrink-0 opacity-50" />
      <NuxtLink
        v-if="c.to"
        :to="c.to"
        class="truncate rounded px-1 py-0.5 hover:bg-muted hover:text-foreground"
      >{{ c.label }}</NuxtLink>
      <span v-else class="truncate px-1 py-0.5 font-medium text-foreground" aria-current="page">
        {{ c.label }}
      </span>
    </template>
  </nav>
</template>
