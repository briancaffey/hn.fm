<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Icon } from '#components'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import StatTile from '~/components/kit/StatTile.vue'
import StatusBadge from '~/components/kit/StatusBadge.vue'
import StageBadge from '~/components/kit/StageBadge.vue'
import EmptyState from '~/components/kit/EmptyState.vue'
import { stageStyle } from '~/composables/usePipelineVocab'

useHead({ title: 'hn.fm · Live' })

interface StepEvent {
  id: number
  item_id: number
  run: number
  seg: number | null
  stage: string
  step_key: string
  status: string
  seconds: number | null
  model: string | null
  error: string | null
  started_at: string | null
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const events = ref<StepEvent[]>([])
const connected = ref(false)
const paused = ref(false)
const error = ref('')
let source: EventSource | null = null

// Keyed by id so a step's running -> ok transition updates in place rather
// than appearing twice. Newest first, because the interesting thing is what is
// happening now.
const upsert = (e: StepEvent) => {
  const i = events.value.findIndex(x => x.id === e.id)
  if (i >= 0) events.value[i] = e
  else events.value.unshift(e)
  // Bounded: an overnight tab would otherwise accumulate every step ever run.
  if (events.value.length > 300) events.value.length = 300
}

const connect = () => {
  if (source) source.close()
  // after=-1: start at the present. Replaying the whole audit trail would take
  // minutes to reach live and bury the work actually running.
  source = new EventSource(`${apiBase}/api/activity/stream?after=-1`)
  source.onopen = () => { connected.value = true; error.value = '' }
  source.onmessage = (m) => {
    if (paused.value) return
    try { upsert(JSON.parse(m.data)) } catch { /* keepalive frames */ }
  }
  source.onerror = () => {
    connected.value = false
    // EventSource reconnects on its own; surfacing the state is enough.
    error.value = 'Reconnecting…'
  }
}

// Queue depth is state, not an event, so it does not arrive on the SSE stream.
// Without it the page showed only what was running: a 30-minute backlog behind
// a video render looked like a normal sequence of steps.
const queues = ref<Record<string, number>>({})
const pendingTotal = ref<number | null>(null)
let poll: ReturnType<typeof setInterval> | null = null

const refreshQueues = async () => {
  try {
    const r = await $fetch<{ queues?: Record<string, number>, pending_total?: number | null }>(
      `${apiBase}/api/activity`
    )
    queues.value = r.queues || {}
    pendingTotal.value = r.pending_total ?? null
  } catch {
    // The stream is the primary signal; a failed depth poll must not disturb it.
  }
}

const QUEUE_LABELS: Record<string, string> = {
  hnfm_ingest: 'Ingest',
  hnfm_triage: 'Triage',
  hnfm_render: 'Render',
  hnfm_digest: 'Digest',
  hnfm_tasks: 'Legacy',
}

// Legacy is only interesting when something is actually stuck in it.
const queueRows = computed(() =>
  Object.entries(queues.value)
    .filter(([name, n]) => name !== 'hnfm_tasks' || n > 0)
    .map(([name, n]) => ({ name, label: QUEUE_LABELS[name] || name, depth: n }))
)

onMounted(() => {
  connect()
  refreshQueues()
  poll = setInterval(refreshQueues, 5000)
})
onUnmounted(() => {
  source?.close()
  if (poll) clearInterval(poll)
})

const running = computed(() => events.value.filter(e => e.status === 'running'))
const failed = computed(() => events.value.filter(e => e.status === 'error'))

// Stage colours come from the shared vocabulary. This page and the
// observability page each used to define their own map, with different
// values, so one stage was two colours depending on where you looked.

const fmt = (e: StepEvent) => e.seconds != null ? `${e.seconds.toFixed(1)}s` : ''
</script>

<template>
  <PageShell>
    <PageHeader
      title="Live activity"
      subtitle="Every pipeline step as it starts and finishes, streamed from the audit trail."
      hint="This is the same record the pipeline keeps for itself — what you see here is exactly what gets stored, not a separate log. Steps update in place as they move from running to done, so a row changing colour means that step just finished."
    >
      <template #actions>
        <StatusBadge
          :status="connected ? 'running' : 'error'"
          :label="connected ? 'Live' : (error || 'Disconnected')"
          dot
        />
        <Button variant="outline" size="sm" @click="paused = !paused">
          <Icon :name="paused ? 'lucide:play' : 'lucide:pause'" class="mr-1.5 h-3.5 w-3.5" />
          {{ paused ? 'Resume' : 'Pause' }}
        </Button>
      </template>
    </PageHeader>

    <section class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <StatTile
        label="In flight" :value="running.length"
        :tone="running.length ? 'running' : 'default'"
        hint="Steps executing right now across all four worker lanes."
      />
      <StatTile
        label="Queued" :value="pendingTotal ?? '—'"
        hint="Messages waiting for a worker. Split by cost so a four-second scrape never queues behind a three-hour render."
      >
        <div v-if="queueRows.length" class="mt-2 flex flex-wrap gap-1">
          <span
            v-for="q in queueRows" :key="q.name"
            class="rounded border px-1.5 py-0.5 text-[11px]"
            :class="q.depth ? 'border-running-border bg-running-bg text-running' : 'border-idle-border bg-idle-bg text-idle'"
          >{{ q.label }} {{ q.depth }}</span>
        </div>
      </StatTile>
      <StatTile
        label="Errors" :value="failed.length"
        :tone="failed.length ? 'danger' : 'default'"
        detail="in this session"
        hint="Failures seen since you opened this page. A soft failure — one motion clip, say — does not stop the run around it."
      />
    </section>

    <section class="mt-4 rounded-lg border bg-card">
      <div class="flex items-center justify-between border-b px-4 py-2.5">
        <h2 class="text-sm font-semibold">Stream</h2>
        <span class="text-xs text-muted-foreground">{{ events.length }} step{{ events.length === 1 ? '' : 's' }} seen</span>
      </div>

      <EmptyState
        v-if="!events.length"
        class="m-4 border-0"
        icon="lucide:radio"
        title="Waiting for activity"
        body="Nothing is running. Queue stories from Stories, start a generation from Triage, or build a digest — steps appear here the moment they begin."
      />

      <div v-else class="divide-y text-xs">
        <div
          v-for="e in events" :key="e.id"
          class="flex items-center gap-3 px-4 py-2 transition-opacity"
          :class="e.status === 'running' ? '' : 'opacity-75'"
        >
          <span class="h-6 w-1.5 flex-none rounded-sm" :style="stageStyle(e.stage)" aria-hidden="true" />
          <StatusBadge :status="e.status" :dot="e.status === 'running'" class="w-[74px] justify-center" />
          <NuxtLink
            :to="`/hn/item/${e.item_id}`"
            class="w-24 flex-none truncate font-mono text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >{{ e.item_id }}</NuxtLink>
          <StageBadge :stage="e.stage" :show-label="false" />
          <span class="min-w-0 flex-1 truncate font-mono">{{ e.step_key }}</span>
          <span class="hidden w-36 flex-none truncate text-muted-foreground md:block">{{ e.model || '' }}</span>
          <span class="w-14 flex-none text-right tabular-nums text-muted-foreground">{{ fmt(e) }}</span>
        </div>
      </div>
    </section>

    <section v-if="failed.length" class="mt-4 rounded-lg border border-danger-border bg-card">
      <div class="border-b border-danger-border px-4 py-2.5">
        <h2 class="text-sm font-semibold text-danger">Failures this session</h2>
      </div>
      <div class="space-y-2 p-4">
        <div v-for="e in failed" :key="`err-${e.id}`" class="text-xs">
          <NuxtLink :to="`/hn/item/${e.item_id}`" class="font-mono hover:underline">
            {{ e.item_id }}
          </NuxtLink>
          <span class="ml-1.5 font-mono text-muted-foreground">{{ e.step_key }}</span>
          <p class="mt-0.5 text-muted-foreground">{{ e.error }}</p>
        </div>
      </div>
    </section>
  </PageShell>
</template>
