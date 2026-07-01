<script setup lang="ts">
interface ActivityStep {
  id: number
  item_id: number
  run: number | string
  seg: number | string | null
  stage: string | null
  step_key: string
  status: string
  started_at: string | null
  finished_at: string | null
  seconds: number | null
}

interface ActivityResponse {
  running: ActivityStep[]
  recent: ActivityStep[]
}

const config = useRuntimeConfig()

const running = ref<ActivityStep[]>([])
const recent = ref<ActivityStep[]>([])
const expanded = ref(false)

const POLL_MS = 10_000
let timer: ReturnType<typeof setInterval> | undefined

async function poll() {
  // pause polling while the tab is hidden
  if (typeof document !== 'undefined' && document.hidden) return
  try {
    const data = await $fetch<ActivityResponse>(
      `${config.public.apiBase}/api/activity`,
    )
    running.value = data?.running ?? []
    recent.value = data?.recent ?? []
  } catch {
    // transient poll failures are non-fatal; keep last known state
  }
}

function onVisibilityChange() {
  if (!document.hidden) poll()
}

onMounted(() => {
  poll()
  timer = setInterval(poll, POLL_MS)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

const lastFinished = computed(() => recent.value[0] ?? null)

function stepLink(step: ActivityStep): string {
  if (step.seg !== null && step.seg !== undefined && step.seg !== '') {
    return `/hn/item/${step.item_id}/run/${step.run}/segment/${step.seg}`
  }
  return `/hn/item/${step.item_id}`
}

function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const s = Math.max(0, Math.floor((Date.now() - then) / 1000))
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
</script>

<template>
  <div class="text-xs">
    <button
      type="button"
      class="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left transition-colors hover:bg-muted"
      :title="running.length ? 'Show running steps' : 'Pipeline idle'"
      @click="expanded = !expanded"
    >
      <!-- status dot -->
      <span v-if="running.length" class="relative flex h-2 w-2 shrink-0">
        <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-500 opacity-75" />
        <span class="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
      </span>
      <span v-else class="inline-flex h-2 w-2 shrink-0 rounded-full bg-muted-foreground/40" />

      <span v-if="running.length" class="font-medium text-green-600 dark:text-green-400">
        {{ running.length }} running
      </span>
      <span v-else class="flex min-w-0 items-baseline gap-1.5">
        <span class="text-muted-foreground">idle</span>
        <span
          v-if="lastFinished"
          class="truncate text-muted-foreground/70"
          :title="`${lastFinished.step_key} · ${timeAgo(lastFinished.finished_at)}`"
        >
          {{ lastFinished.step_key }} · {{ timeAgo(lastFinished.finished_at) }}
        </span>
      </span>
    </button>

    <!-- expandable list of running steps -->
    <div
      v-if="expanded && running.length"
      class="mt-1 max-h-48 space-y-0.5 overflow-y-auto rounded-md border bg-background p-1"
    >
      <NuxtLink
        v-for="step in running"
        :key="step.id"
        :to="stepLink(step)"
        class="block truncate rounded px-2 py-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        :title="`${step.step_key} · item ${step.item_id}`"
      >
        <span class="font-mono">{{ step.step_key }}</span>
        <span class="text-muted-foreground/70"> · #{{ step.item_id }}</span>
      </NuxtLink>
    </div>
  </div>
</template>
