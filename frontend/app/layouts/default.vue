<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Icon } from '#components'
import ActivityIndicator from '~/components/ActivityIndicator.vue'

const colorMode = useColorMode()
const route = useRoute()

interface NavItem {
  label: string
  to: string
  icon: string
  /** path prefix used for active-route highlighting */
  match: string
  /** Shown on hover. A flat list of seven nouns said nothing about what each
   *  page is for, or in what order you would use them. */
  hint: string
}

/**
 * Grouped by what you are doing, in pipeline order: choose material, look at
 * what came out, watch the machine.
 */
const navGroups: Array<{ label: string, items: NavItem[] }> = [
  {
    label: 'Content',
    items: [
      { label: 'Stories', to: '/hn/items', icon: 'lucide:newspaper', match: '/hn',
        hint: 'Everything ingested from Hacker News. Queue more from here.' },
      { label: 'Triage', to: '/triage', icon: 'lucide:list-checks', match: '/triage',
        hint: 'The ranked queue — what is worth making, and your overrides.' },
    ],
  },
  {
    label: 'Output',
    items: [
      { label: 'Segments', to: '/segments', icon: 'lucide:layers', match: '/segments',
        hint: 'Finished pieces: script, audio, images and video for one run.' },
      { label: 'Digests', to: '/digests', icon: 'lucide:book-open', match: '/digests',
        hint: 'Reading editions built from Story Briefs, sent to Kindle.' },
    ],
  },
  {
    label: 'Pipeline',
    items: [
      { label: 'Live', to: '/live', icon: 'lucide:radio', match: '/live',
        hint: 'Every step as it happens, streamed from the audit trail.' },
      { label: 'Observability', to: '/observability', icon: 'lucide:activity', match: '/observability',
        hint: 'Where a render spends its time and tokens.' },
      { label: 'Services', to: '/services', icon: 'lucide:server', match: '/services',
        hint: 'Inference backend health, and what breaks without each one.' },
    ],
  },
]

function isActive(item: NavItem): boolean {
  return route.path === item.match || route.path.startsWith(`${item.match}/`)
}
</script>

<template>
  <div class="h-screen bg-background flex overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-52 shrink-0 border-r bg-card flex flex-col">
      <!-- Wordmark -->
      <div class="px-4 py-3.5 border-b">
        <NuxtLink to="/" class="text-lg font-bold text-foreground">
          <span class="text-primary">hn</span>.fm
        </NuxtLink>
      </div>

      <!-- Nav -->
      <nav class="flex-1 space-y-4 overflow-y-auto px-2 py-3">
        <NuxtLink
          to="/"
          class="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors"
          :class="route.path === '/'
            ? 'bg-primary/10 text-primary'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'"
          title="Corpus, live work, queue depth and service health at a glance."
        >
          <Icon name="lucide:layout-dashboard" class="h-4 w-4 shrink-0" />
          <span class="truncate">Overview</span>
        </NuxtLink>

        <div v-for="group in navGroups" :key="group.label" class="space-y-1">
          <p class="px-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
            {{ group.label }}
          </p>
          <NuxtLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            :title="item.hint"
            class="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors"
            :class="isActive(item)
              ? 'bg-primary/10 text-primary'
              : 'text-muted-foreground hover:bg-muted hover:text-foreground'"
          >
            <Icon :name="item.icon" class="h-4 w-4 shrink-0" />
            <span class="truncate">{{ item.label }}</span>
          </NuxtLink>
        </div>
      </nav>

      <!-- Bottom: theme toggle + activity -->
      <div class="shrink-0 border-t px-2 py-2 space-y-1">
        <Button
          variant="ghost"
          size="sm"
          class="w-full justify-start gap-2.5 px-2.5 text-muted-foreground"
          @click="colorMode.preference = colorMode.preference === 'dark' ? 'light' : 'dark'"
        >
          <Icon
            :name="colorMode.value === 'dark' ? 'lucide:sun' : 'lucide:moon'"
            class="h-4 w-4"
          />
          <span class="text-xs">{{ colorMode.value === 'dark' ? 'Light mode' : 'Dark mode' }}</span>
        </Button>
        <ActivityIndicator />
      </div>
    </aside>

    <!-- Main content: full remaining viewport width -->
    <main class="flex-1 min-w-0 overflow-y-auto">
      <slot />
    </main>
  </div>
</template>
