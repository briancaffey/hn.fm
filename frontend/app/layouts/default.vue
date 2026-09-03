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
}

const navItems: NavItem[] = [
  { label: 'Stories', to: '/hn/items', icon: 'lucide:newspaper', match: '/hn' },
  { label: 'Triage', to: '/triage', icon: 'lucide:list-checks', match: '/triage' },
  { label: 'Segments', to: '/segments', icon: 'lucide:layers', match: '/segments' },
  { label: 'Digests', to: '/digests', icon: 'lucide:book-open', match: '/digests' },
  { label: 'Live', to: '/live', icon: 'lucide:radio', match: '/live' },
  { label: 'Observability', to: '/observability', icon: 'lucide:activity', match: '/observability' },
  { label: 'Services', to: '/services', icon: 'lucide:server', match: '/services' },
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
        <NuxtLink to="/hn/items" class="text-lg font-bold text-foreground">
          <span class="text-orange-600">hn</span>.fm
        </NuxtLink>
      </div>

      <!-- Nav -->
      <nav class="flex-1 overflow-y-auto px-2 py-3 space-y-1">
        <NuxtLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors"
          :class="isActive(item)
            ? 'bg-orange-100 text-orange-700 dark:bg-orange-950/40 dark:text-orange-300'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'"
        >
          <Icon :name="item.icon" class="h-4 w-4 shrink-0" />
          <span class="truncate">{{ item.label }}</span>
        </NuxtLink>
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
