<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '#components'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import StatTile from '~/components/kit/StatTile.vue'
import StatusBadge from '~/components/kit/StatusBadge.vue'
import StageBadge from '~/components/kit/StageBadge.vue'
import EmptyState from '~/components/kit/EmptyState.vue'
import { GLOSSARY } from '~/composables/usePipelineVocab'

/**
 * The overview. This route used to be a "Coming soon…" placeholder with two
 * dead buttons, which meant the app had no answer to "what is happening right
 * now" short of opening four other pages.
 */
useHead({ title: 'hn.fm · Overview' })

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

interface Activity {
  running: Array<{ id: number, item_id: number, run: number, stage: string, step_key: string, status: string }>
  recent: Array<{ id: number, item_id: number, stage: string, step_key: string, status: string, seconds: number | null }>
  queues?: Record<string, number>
  pending_total?: number | null
}

const activity = ref<Activity>({ running: [], recent: [] })
// null, not 0 — a real zero and "not loaded yet" look identical otherwise,
// and the tiles would flash 0 on every render before the fetch lands.
const counts = ref<Record<string, number | null>>({
  stories: null, triage: null, segments: null, digests: null,
})
const services = ref<Array<{ name: string, status: string }>>([])
const loading = ref(true)
let poll: ReturnType<typeof setInterval> | null = null

async function refresh() {
  const [act, stories, triage, segments, digests, svc] = await Promise.allSettled([
    $fetch<Activity>(`${apiBase}/api/activity`),
    $fetch<{ pagination: { total: number } }>(`${apiBase}/api/hn/items?offset=0&limit=1`),
    $fetch<{ pagination: { total: number } }>(`${apiBase}/api/triage?offset=0&limit=1`),
    $fetch<{ pagination: { total: number } }>(`${apiBase}/api/segments?offset=0&limit=1`),
    $fetch<{ digests: unknown[] }>(`${apiBase}/api/digests`),
    $fetch<{ services: Array<{ name: string, status: string }> }>(`${apiBase}/api/services/status`),
  ])
  if (act.status === 'fulfilled') activity.value = act.value
  counts.value = {
    stories: stories.status === 'fulfilled' ? stories.value.pagination.total : null,
    triage: triage.status === 'fulfilled' ? triage.value.pagination.total : null,
    segments: segments.status === 'fulfilled' ? segments.value.pagination.total : null,
    digests: digests.status === 'fulfilled' ? digests.value.digests.length : null,
  }
  if (svc.status === 'fulfilled') services.value = svc.value.services || []
  loading.value = false
}

onMounted(() => {
  refresh()
  poll = setInterval(refresh, 5000)
})
onUnmounted(() => { if (poll) clearInterval(poll) })

const offline = computed(() =>
  services.value.filter(s => s.status !== 'online' && s.status !== 'disabled'))
const pending = computed(() => activity.value.pending_total ?? null)
const queueRows = computed(() =>
  Object.entries(activity.value.queues || {})
    .filter(([name, n]) => name !== 'hnfm_tasks' || n > 0)
    .map(([name, depth]) => ({
      name,
      label: ({
        hnfm_ingest: 'Ingest', hnfm_triage: 'Triage',
        hnfm_render: 'Render', hnfm_digest: 'Digest', hnfm_tasks: 'Legacy',
      } as Record<string, string>)[name] || name,
      depth,
    })))

/** Where to go next, with the reason you'd go there. */
const destinations = [
  { to: '/hn/items', icon: 'lucide:newspaper', label: 'Stories', body: 'Everything ingested from Hacker News. Start a run from here.' },
  { to: '/triage', icon: 'lucide:list-checks', label: 'Triage', body: 'The ranked queue. What the pipeline thinks is worth making, and your overrides.' },
  { to: '/segments', icon: 'lucide:layers', label: 'Segments', body: 'Finished pieces — script, audio, images and video for one run.' },
  { to: '/digests', icon: 'lucide:book-open', label: 'Digests', body: 'Reading editions built from Story Briefs, delivered to Kindle.' },
]
</script>

<template>
  <PageShell>
    <PageHeader
      title="Overview"
      subtitle="What the pipeline holds and what it is doing right now."
      hint="hn.fm turns Hacker News stories into narrated video, podcast episodes and reading digests. This page is the status board: corpus size, live work, queue depth and service health, refreshed every five seconds."
    />

    <!-- Corpus -->
    <section class="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile
        label="Stories" :value="counts.stories"
        hint="Hacker News items ingested. Most never become content — triage decides which are worth generating."
      />
      <StatTile
        label="Triaged" :value="counts.triage"
        :hint="GLOSSARY.verdict"
      />
      <StatTile
        label="Segments" :value="counts.segments"
        :hint="GLOSSARY.segment"
      />
      <StatTile
        label="Digests" :value="counts.digests"
        hint="Rendered reading editions on disk. Built from Story Briefs, so they cost no LLM calls of their own."
      />
    </section>

    <!-- Live -->
    <section class="mt-6 grid gap-4 lg:grid-cols-3">
      <div class="lg:col-span-2 rounded-lg border bg-card">
        <div class="flex items-center justify-between border-b px-4 py-2.5">
          <h2 class="text-sm font-semibold">In flight</h2>
          <NuxtLink to="/live" class="text-xs text-primary hover:underline">Live view →</NuxtLink>
        </div>
        <div class="p-4">
          <div v-if="activity.running.length" class="space-y-2">
            <div
              v-for="s in activity.running.slice(0, 6)" :key="s.id"
              class="flex items-center gap-2.5 text-sm"
            >
              <StageBadge :stage="s.stage" :show-label="false" />
              <span class="font-mono text-xs text-muted-foreground">{{ s.item_id }}</span>
              <span class="min-w-0 flex-1 truncate">{{ s.step_key }}</span>
              <StatusBadge status="running" dot />
            </div>
          </div>
          <EmptyState
            v-else
            icon="lucide:moon"
            title="Nothing running"
            body="The workers are idle. Queue stories from the Stories page, or start a generation from Triage."
          />
        </div>
      </div>

      <div class="rounded-lg border bg-card">
        <div class="border-b px-4 py-2.5">
          <h2 class="text-sm font-semibold">Queues</h2>
        </div>
        <div class="space-y-2 p-4">
          <p class="text-xs text-muted-foreground">
            Work is split by cost so a four-second scrape never waits behind a
            three-hour render.
          </p>
          <div v-for="q in queueRows" :key="q.name" class="flex items-center justify-between text-sm">
            <span class="text-muted-foreground">{{ q.label }}</span>
            <span class="font-medium tabular-nums" :class="q.depth ? 'text-running' : ''">{{ q.depth }}</span>
          </div>
          <p v-if="pending === 0" class="pt-1 text-xs text-muted-foreground">All caught up.</p>
        </div>
      </div>
    </section>

    <!-- Services -->
    <section v-if="!loading" class="mt-4 rounded-lg border bg-card px-4 py-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div class="flex items-center gap-2">
          <h2 class="text-sm font-semibold">Inference services</h2>
          <StatusBadge
            :status="offline.length ? 'error' : 'ok'"
            :label="offline.length ? `${offline.length} offline` : `${services.length} online`"
            dot
          />
        </div>
        <NuxtLink to="/services" class="text-xs text-primary hover:underline">Details →</NuxtLink>
      </div>
      <p v-if="offline.length" class="mt-1.5 text-xs text-muted-foreground">
        {{ offline.map(s => s.name).join(', ') }} — the pipeline plans around a
        dead backend rather than queueing work at it, so runs still finish, with
        fewer motion clips.
      </p>
    </section>

    <!-- Where to go -->
    <section class="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <NuxtLink
        v-for="d in destinations" :key="d.to" :to="d.to"
        class="group rounded-lg border bg-card p-4 transition-colors hover:border-primary/50 hover:bg-elevated"
      >
        <Icon :name="d.icon" class="h-4 w-4 text-primary" />
        <p class="mt-2 text-sm font-medium group-hover:text-primary">{{ d.label }}</p>
        <p class="mt-1 text-xs leading-relaxed text-muted-foreground">{{ d.body }}</p>
      </NuxtLink>
    </section>
  </PageShell>
</template>
