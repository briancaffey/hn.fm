<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button } from '~/components/ui/button'
import { Switch } from '~/components/ui/switch'
import { Icon } from '#components'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import StatTile from '~/components/kit/StatTile.vue'
import LoadingRows from '~/components/kit/LoadingRows.vue'
import InfoHint from '~/components/kit/InfoHint.vue'
import EmptyState from '~/components/kit/EmptyState.vue'

useHead({ title: 'hn.fm · Schedule' })

interface LastRun {
  started_at: string
  status: 'dispatched' | 'skipped' | 'error'
  note?: string | null
  task_id?: string | null
  forced?: boolean
}
interface Job {
  name: string
  task: string
  gate: 'scraping' | 'generation' | 'none'
  cadence: string
  every_seconds: number | null
  cron: string | null
  kwargs: Record<string, unknown>
  enabled: boolean
  why: string
  last_run: LastRun | null
  next_run: string | null
}
interface Churn {
  samples: number
  hours_observed: number
  per_hour: number | null
  suggested_every_minutes: number | null
  last: { sampled_at: string, size: number, new_count: number | null, front_changed: number | null } | null
}
interface ScheduleResponse {
  enabled: boolean
  timezone: string
  now: string
  controls: { scraping_paused: boolean, generation_paused: boolean }
  delivery: { ready: boolean, detail: string }
  jobs: Job[]
  churn: { new: Churn, top: Churn }
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const { data, pending, refresh } = await useAsyncData<ScheduleResponse>('schedule', () =>
  $fetch(`${apiBase}/api/schedule`))

onMounted(() => {
  const t = setInterval(refresh, 30000)
  onUnmounted(() => clearInterval(t))
})

const saving = ref(false)
async function setControl(key: 'scraping_paused' | 'generation_paused', value: boolean) {
  saving.value = true
  try {
    await $fetch(`${apiBase}/api/schedule/controls`, { method: 'POST', body: { [key]: value } })
    await refresh()
  }
  finally {
    saving.value = false
  }
}

const running = ref<string | null>(null)
async function runNow(name: string) {
  running.value = name
  try {
    await $fetch(`${apiBase}/api/schedule/jobs/${name}/run`, { method: 'POST' })
    await refresh()
  }
  finally {
    running.value = null
  }
}

const jobs = computed(() => data.value?.jobs ?? [])
const scrapingJobs = computed(() => jobs.value.filter(j => j.gate === 'scraping'))
const generationJobs = computed(() => jobs.value.filter(j => j.gate === 'generation'))
const otherJobs = computed(() => jobs.value.filter(j => j.gate === 'none'))
const fetchJob = (name: string) => jobs.value.find(j => j.name === name)

/** Minutes between fires for the two fetch jobs, so the churn tiles can say
 *  whether the configured cadence is ahead of or behind what was measured. */
const configuredMinutes = (name: string) => {
  const j = fetchJob(name)
  return j?.every_seconds ? Math.round(j.every_seconds / 60) : null
}

function whenLocal(iso?: string | null) {
  if (!iso) return '—'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  return d.toLocaleString(undefined, { weekday: 'short', hour: '2-digit', minute: '2-digit' })
}
function ago(iso?: string | null) {
  if (!iso) return 'never'
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
  const mins = Math.round((Date.now() - d.getTime()) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const h = Math.round(mins / 60)
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} d ago`
}

const GATE_TONE: Record<Job['gate'], string> = {
  scraping: 'bg-running-bg text-running border-running-border',
  generation: 'bg-warn-bg text-warn border-warn-border',
  none: 'bg-idle-bg text-idle border-idle-border',
}
const STATUS_TONE: Record<LastRun['status'], string> = {
  dispatched: 'text-ok',
  skipped: 'text-stale',
  error: 'text-danger',
}

function kwargsText(k: Record<string, unknown>) {
  return Object.entries(k).map(([a, b]) => `${a}=${b}`).join(' · ')
}
</script>

<template>
  <PageShell>
    <PageHeader
      title="Schedule"
      subtitle="What runs on a timer, when it fires next, and the two switches that stop it."
      hint="The table comes from config.yaml (schedule.jobs) — the same list Celery beat runs from, so what you see here is what fires. The pause switches are stored in the database and take effect the next time a job fires: paused jobs are recorded as skipped rather than removed, so the schedule stays visible while paused. Manual actions elsewhere in the app (queueing a story, building a digest) are never blocked by these switches."
      :meta="[
        data?.enabled ? 'beat enabled' : 'beat disabled (SCHEDULE_ENABLED=false)',
        `${jobs.length} jobs`,
        `times shown in your local zone; config is ${data?.timezone ?? 'UTC'}`,
      ]"
    >
      <template #actions>
        <Button variant="outline" size="sm" :disabled="pending" @click="refresh()">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" :class="pending ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <!-- Controls -->
    <section class="grid gap-3 md:grid-cols-2">
      <div class="rounded-lg border bg-card p-4 flex items-start justify-between gap-4">
        <div>
          <div class="flex items-center gap-1.5">
            <span class="text-sm font-medium">Scraping</span>
            <InfoHint text="Fetching /new and /top from Hacker News and scoring the backlog. Pausing stops new stories arriving; nothing already fetched is touched." />
          </div>
          <p class="mt-1 text-xs text-muted-foreground">
            {{ scrapingJobs.length }} jobs ·
            <span :class="data?.controls.scraping_paused ? 'text-warn' : 'text-ok'">
              {{ data?.controls.scraping_paused ? 'paused' : 'running' }}
            </span>
          </p>
        </div>
        <label class="flex items-center gap-2 text-xs text-muted-foreground">
          pause
          <Switch
            :model-value="data?.controls.scraping_paused ?? false"
            :disabled="saving || pending"
            @update:model-value="(v: boolean) => setControl('scraping_paused', v)"
          />
        </label>
      </div>
      <div class="rounded-lg border bg-card p-4 flex items-start justify-between gap-4">
        <div>
          <div class="flex items-center gap-1.5">
            <span class="text-sm font-medium">Generation</span>
            <InfoHint text="Digests, Kindle sends, and audio/video renders. Pausing lets stories keep arriving and being scored while nothing is produced or sent — the manual override for the expensive half." />
          </div>
          <p class="mt-1 text-xs text-muted-foreground">
            {{ generationJobs.length }} jobs ·
            <span :class="data?.controls.generation_paused ? 'text-warn' : 'text-ok'">
              {{ data?.controls.generation_paused ? 'paused' : 'running' }}
            </span>
            · Kindle delivery
            <span :class="data?.delivery.ready ? 'text-ok' : 'text-danger'">{{ data?.delivery.ready ? 'ready' : 'not configured' }}</span>
          </p>
        </div>
        <label class="flex items-center gap-2 text-xs text-muted-foreground">
          pause
          <Switch
            :model-value="data?.controls.generation_paused ?? false"
            :disabled="saving || pending"
            @update:model-value="(v: boolean) => setControl('generation_paused', v)"
          />
        </label>
      </div>
    </section>

    <!-- Churn -->
    <section class="mt-6">
      <h2 class="text-sm font-medium flex items-center gap-1.5">
        How fast Hacker News moves
        <InfoHint text="The probe-churn job samples the /new and /top id lists every few minutes (two GETs, no item fetches) and records what changed. The suggestion is the fetch interval at which a 60-id fetch of /new is about half full, and /top changes about one front-page story per fetch. Compare it with the configured cadence and adjust config.yaml." />
      </h2>
      <div class="mt-2 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="/new submissions per hour"
          :value="data?.churn.new.per_hour ?? '—'"
          :detail="data?.churn.new.samples ? `${data.churn.new.samples} samples over ${data.churn.new.hours_observed} h${data.churn.new.hours_observed < 1 ? ' — suggestion after 1 h' : ''}` : 'no samples yet — the probe fills this in'"
        />
        <StatTile
          label="/new: suggested vs configured"
          :value="data?.churn.new.suggested_every_minutes ? `${data.churn.new.suggested_every_minutes} min` : '—'"
          :detail="configuredMinutes('fetch-new') ? `configured every ${configuredMinutes('fetch-new')} min` : undefined"
          :tone="data?.churn.new.suggested_every_minutes && configuredMinutes('fetch-new') && data.churn.new.suggested_every_minutes < configuredMinutes('fetch-new')! ? 'warn' : 'default'"
        />
        <StatTile
          label="/top front-30 changes per hour"
          :value="data?.churn.top.per_hour ?? '—'"
          :detail="data?.churn.top.samples ? `${data.churn.top.samples} samples over ${data.churn.top.hours_observed} h` : 'no samples yet'"
        />
        <StatTile
          label="/top: suggested vs configured"
          :value="data?.churn.top.suggested_every_minutes ? `${data.churn.top.suggested_every_minutes} min` : '—'"
          :detail="configuredMinutes('fetch-top') ? `configured every ${configuredMinutes('fetch-top')} min` : undefined"
          :tone="data?.churn.top.suggested_every_minutes && configuredMinutes('fetch-top') && data.churn.top.suggested_every_minutes < configuredMinutes('fetch-top')! ? 'warn' : 'default'"
        />
      </div>
    </section>

    <!-- Jobs -->
    <section class="mt-6">
      <h2 class="text-sm font-medium">Jobs</h2>
      <LoadingRows v-if="pending && !jobs.length" class="mt-2" :rows="6" height="h-14" />
      <EmptyState
        v-else-if="!jobs.length"
        title="Nothing scheduled"
        description="config.yaml has no schedule.jobs, so beat has nothing to fire. Add a job there and restart beat."
      />
      <div v-else class="mt-2 overflow-x-auto rounded-lg border bg-card">
        <table class="w-full text-sm">
          <thead class="text-xs text-muted-foreground">
            <tr class="border-b">
              <th class="px-3 py-2 text-left font-medium">Job</th>
              <th class="px-3 py-2 text-left font-medium">Cadence</th>
              <th class="px-3 py-2 text-left font-medium">Gate</th>
              <th class="px-3 py-2 text-left font-medium">Next</th>
              <th class="px-3 py-2 text-left font-medium">Last</th>
              <th class="px-3 py-2 text-right font-medium" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="j in [...scrapingJobs, ...generationJobs, ...otherJobs]" :key="j.name" class="border-b last:border-0 align-top" :class="j.enabled ? '' : 'opacity-60'">
              <td class="px-3 py-2">
                <div class="font-medium">{{ j.name }}</div>
                <div class="text-xs text-muted-foreground max-w-md">{{ j.why }}</div>
                <div class="mt-0.5 text-xs text-muted-foreground font-mono">{{ j.task.replace('hnfm.web.tasks.', '') }}<span v-if="Object.keys(j.kwargs).length"> · {{ kwargsText(j.kwargs) }}</span></div>
              </td>
              <td class="px-3 py-2 whitespace-nowrap">
                {{ j.cadence }}
                <div v-if="!j.enabled" class="text-xs text-muted-foreground">disabled in config</div>
              </td>
              <td class="px-3 py-2">
                <span class="inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs" :class="GATE_TONE[j.gate]">{{ j.gate }}</span>
              </td>
              <td class="px-3 py-2 whitespace-nowrap text-muted-foreground">
                <template v-if="j.next_run">{{ whenLocal(j.next_run) }}</template>
                <template v-else-if="j.enabled && j.every_seconds">within {{ Math.round(j.every_seconds / 60) }} min of beat start</template>
                <template v-else>—</template>
              </td>
              <td class="px-3 py-2 whitespace-nowrap">
                <template v-if="j.last_run">
                  <span :class="STATUS_TONE[j.last_run.status]">{{ j.last_run.status }}</span>
                  <span class="text-muted-foreground"> · {{ ago(j.last_run.started_at) }}</span>
                  <div v-if="j.last_run.note" class="text-xs text-muted-foreground max-w-xs whitespace-normal">{{ j.last_run.note }}</div>
                </template>
                <span v-else class="text-muted-foreground">never</span>
              </td>
              <td class="px-3 py-2 text-right">
                <Button variant="outline" size="sm" :disabled="running === j.name" @click="runNow(j.name)">
                  <Icon name="lucide:play" class="mr-1 h-3 w-3" />
                  Run now
                </Button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="mt-2 text-xs text-muted-foreground">
        "Run now" ignores the pause switches. Cadence and kwargs are edited in config.yaml under <span class="font-mono">schedule:</span>; beat picks changes up on restart.
      </p>
    </section>
  </PageShell>
</template>
