<script setup lang="ts">
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'

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

onMounted(connect)
onUnmounted(() => source?.close())

const running = computed(() => events.value.filter(e => e.status === 'running'))
const failed = computed(() => events.value.filter(e => e.status === 'error'))

const stageColor = (stage: string) => ({
  scrape: 'bg-sky-500', summary: 'bg-sky-500', enrich: 'bg-sky-500',
  triage: 'bg-violet-500', brief: 'bg-violet-500',
  script: 'bg-amber-500', audio: 'bg-emerald-500',
  images: 'bg-pink-500', media_plan: 'bg-pink-500', video: 'bg-orange-500',
}[stage] || 'bg-gray-400')

const statusVariant = (s: string): 'default' | 'destructive' | 'secondary' | 'outline' =>
  s === 'error' ? 'destructive' : s === 'running' ? 'default' : 'secondary'

const fmt = (e: StepEvent) => e.seconds != null ? `${e.seconds.toFixed(1)}s` : ''
</script>

<template>
  <div class="container mx-auto p-6 space-y-6">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold">Live Activity</h1>
        <p class="text-muted-foreground mt-1">
          Every pipeline step as it starts and finishes — scraping, prompts,
          images, video. Streamed from the audit trail, so what you see here is
          what gets recorded.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Badge :variant="connected ? 'default' : 'destructive'">
          {{ connected ? 'Live' : (error || 'Disconnected') }}
        </Badge>
        <Button variant="outline" size="sm" @click="paused = !paused">
          {{ paused ? 'Resume' : 'Pause' }}
        </Button>
      </div>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <Card>
        <CardHeader class="pb-2"><CardTitle class="text-sm font-medium text-muted-foreground">In flight</CardTitle></CardHeader>
        <CardContent><span class="text-3xl font-bold">{{ running.length }}</span></CardContent>
      </Card>
      <Card>
        <CardHeader class="pb-2"><CardTitle class="text-sm font-medium text-muted-foreground">Steps seen</CardTitle></CardHeader>
        <CardContent><span class="text-3xl font-bold">{{ events.length }}</span></CardContent>
      </Card>
      <Card>
        <CardHeader class="pb-2"><CardTitle class="text-sm font-medium text-muted-foreground">Errors</CardTitle></CardHeader>
        <CardContent>
          <span class="text-3xl font-bold" :class="failed.length ? 'text-destructive' : ''">{{ failed.length }}</span>
        </CardContent>
      </Card>
    </div>

    <Card>
      <CardHeader><CardTitle class="text-base">Stream</CardTitle></CardHeader>
      <CardContent>
        <p v-if="!events.length" class="text-sm text-muted-foreground">
          Waiting for activity. Start a pipeline or build a digest and steps will
          appear here as they run.
        </p>
        <div v-else class="divide-y font-mono text-xs">
          <div
            v-for="e in events"
            :key="e.id"
            class="flex items-center gap-3 py-2"
            :class="e.status === 'running' ? 'opacity-100' : 'opacity-80'"
          >
            <span class="w-1.5 h-6 rounded-sm flex-none" :class="stageColor(e.stage)" />
            <Badge :variant="statusVariant(e.status)" class="w-20 justify-center flex-none">
              {{ e.status }}
            </Badge>
            <NuxtLink
              :to="`/hn/item/${e.item_id}`"
              class="w-28 flex-none underline underline-offset-2 truncate"
            >{{ e.item_id }}</NuxtLink>
            <span class="flex-1 truncate">{{ e.stage }} / {{ e.step_key }}</span>
            <span class="w-32 flex-none truncate text-muted-foreground">{{ e.model || '' }}</span>
            <span class="w-14 flex-none text-right text-muted-foreground">{{ fmt(e) }}</span>
          </div>
        </div>
      </CardContent>
    </Card>

    <Card v-if="failed.length">
      <CardHeader><CardTitle class="text-base text-destructive">Failures</CardTitle></CardHeader>
      <CardContent class="space-y-2">
        <div v-for="e in failed" :key="`err-${e.id}`" class="text-xs">
          <span class="font-mono">{{ e.stage }}/{{ e.step_key }}</span>
          <span class="text-muted-foreground"> — {{ e.error }}</span>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
