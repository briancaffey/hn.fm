<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { TresCanvas } from '@tresjs/core'
import { Icon } from '#components'
import { Button } from '~/components/ui/button'
import StudioScene from '~/components/studio/StudioScene.vue'
import type { Bubble, SheetItem } from '~/components/studio/StudioScene.vue'

/**
 * The Studio (plans/21): the station as a place, in real time. One SSE
 * connection feeds the commentary; a snapshot every few seconds feeds the
 * state. Everything else is the scene animating the difference.
 */
useHead({ title: 'hn.fm · Studio' })

interface LogLine { id: number, at: string, component: string, message: string, meta: Record<string, string | number | null> }
interface Snapshot {
  enabled: boolean
  now: { kind: string, title: string | null, meta: Record<string, string> } | null
  queue: string[]
  sheet: { sheet_id: string, title: string | null, source: string | null, cursor: number, items: number } | null
  sheet_items: SheetItem[]
  sheet_cursor: number
  bank: Record<string, number>
  episodes: number
  icecast: { up: boolean, mounts?: { listeners: number }[] }
  log?: LogLine[]
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const snap = ref<Snapshot | null>(null)
const lines = ref<LogLine[]>([])
const bubbles = ref<Bubble[]>([])
const packets = ref<{ id: number, from: string, to: string, color: string }[]>([])
const counters = reactive({ tracks: 0, plans: 0, rounds: 0 })
const thinking = ref(false)
const connected = ref(false)
const explain = ref<string | null>(null)
let source: EventSource | null = null
let packetId = 0

const COMPONENTS: Record<string, { name: string, what: string, color: string }> = {
  dj: { name: 'The DJ', color: '#ff6a00', what: 'Liquidsoap. Asks the switchboard what to play a few seconds before each track ends, crossfades, encodes one MP3, pushes it to the transmitter, and reports every track it starts.' },
  director: { name: 'The Switchboard', color: '#f4efe6', what: 'The hn.fm API. Answers the DJ from the current block, honours "play this next", keeps the history, and asks the producer for the next block when this one runs low.' },
  producer: { name: 'The Producer', color: '#5eead4', what: 'The local model, once per block: which episodes, in what order, who says what between them, what music. If it is down, a deterministic producer plans the block instead.' },
  bank: { name: 'The Library', color: '#b39ddb', what: 'Finished episodes from the pipeline, plus the bank: station IDs in each host\'s voice and music beds from ACE-Step, kept ready so the air never waits on a model.' },
  monitor: { name: 'The Manager', color: '#f5b642', what: 'A patrol every five minutes: is the transmitter up, is a block ready, is the bank stocked. Plans or refills when not.' },
  transmitter: { name: 'The Transmitter', color: '#ff6a00', what: 'Icecast. One feed in, any number of listeners out over plain HTTP. Each orb is a listener.' },
}

function listeners(s: Snapshot | null) {
  return (s?.icecast?.mounts || []).reduce((n, m) => n + (m.listeners || 0), 0)
}

/** Turn a commentary line into what the scene should do. */
function react(line: LogLine) {
  lines.value = [...lines.value.slice(-60), line]
  bubbles.value = [...bubbles.value.slice(-20), { component: line.component, text: line.message, at: performance.now() }]
  const m = line.message
  if (line.component === 'dj' && m.startsWith('asked')) fire('dj', 'hub', '#5eead4')
  if (line.component === 'director' && m.startsWith('served')) fire('hub', 'dj', '#ff6a00')
  if (line.component === 'dj' && m.startsWith('on air')) { fire('dj', 'hub', '#f4efe6'); counters.tracks++ }
  if (line.component === 'director' && m.includes('asked the producer')) fire('hub', 'producer', '#5eead4')
  if (line.component === 'producer' && m.startsWith('thinking')) thinking.value = true
  if (line.component === 'producer' && m.startsWith('planned')) { thinking.value = false; counters.plans++; fire('producer', 'hub', '#5eead4') }
  if (line.component === 'producer' && (m.includes('using the deterministic'))) thinking.value = false
  if (line.component === 'bank') fire('library', 'hub', '#b39ddb')
  if (line.component === 'monitor') counters.rounds++
}
function fire(from: string, to: string, color: string) {
  packets.value = [...packets.value.slice(-12), { id: ++packetId, from, to, color }]
}

async function boot() {
  try {
    const s = await $fetch<Snapshot>(`${apiBase}/api/radio/studio`)
    snap.value = s
    lines.value = s.log || []
    const last = lines.value.length ? lines.value[lines.value.length - 1].id : 0
    source = new EventSource(`${apiBase}/api/radio/stream?after=${last}`)
    source.addEventListener('log', (e) => react(JSON.parse((e as MessageEvent).data)))
    source.addEventListener('snapshot', (e) => { snap.value = { ...snap.value, ...JSON.parse((e as MessageEvent).data) } })
    source.onopen = () => { connected.value = true }
    source.onerror = () => { connected.value = false }
  } catch { snap.value = { enabled: false } as Snapshot }
}
onMounted(boot)
onUnmounted(() => source?.close())

const when = (iso: string) => new Date(iso.endsWith('Z') ? iso : iso + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
const tail = computed(() => lines.value.slice(-12).reverse())
const KIND_LABEL: Record<string, string> = { episode: 'Episode', station_id: 'Station ID', coming_up: 'Coming up', music: 'Music', time_check: 'Time check' }
</script>

<template>
  <div class="relative h-[calc(100vh-3.5rem)] min-h-[560px] w-full overflow-hidden bg-background">
    <!-- three.js has no server; the canvas is client-only, the HUD is not. -->
    <ClientOnly>
    <TresCanvas clear-color="#0b0a09" shadows :alpha="false">
      <StudioScene
        :on-air="!!snap?.icecast?.up && (snap?.icecast?.mounts?.length || 0) > 0"
        :now-kind="snap?.now?.kind || null"
        :now-title="snap?.now?.title || null"
        :now-host="snap?.now?.meta?.hnfm_host || null"
        :listeners="listeners(snap)"
        :episodes="snap?.episodes || 0"
        :station-ids="snap?.bank?.station_id || 0"
        :beds="snap?.bank?.music || 0"
        :sheet-items="snap?.sheet_items || []"
        :sheet-cursor="snap?.sheet_cursor || 0"
        :thinking="thinking"
        :bubbles="bubbles"
        :track-changes="counters.tracks"
        :plans="counters.plans"
        :packets="packets"
        :monitor-rounds="counters.rounds"
      />
    </TresCanvas>
    </ClientOnly>

    <!-- HUD: top-left masthead and now playing -->
    <div class="pointer-events-none absolute left-5 top-4 flex max-w-sm flex-col gap-3">
      <div>
        <div class="flex gap-0.5" aria-hidden="true">
          <span class="h-3 w-3" style="background:#6f3410" /><span class="h-3 w-3" style="background:#8c4210" /><span class="h-3 w-3" style="background:#b5540c" /><span class="h-3 w-3" style="background:#d96208" /><span class="h-3 w-3" style="background:#ff6a00" />
        </div>
        <h1 class="mt-1 text-2xl font-black tracking-tight text-foreground">HNFM · Studio</h1>
        <p class="text-xs text-muted-foreground">
          <span class="mr-1 inline-block h-2 w-2 rounded-full" :class="connected ? 'bg-primary' : 'bg-muted-foreground'" />
          {{ connected ? 'live' : 'connecting…' }} · drag to look around
        </p>
      </div>
      <div v-if="snap?.now" class="pointer-events-auto rounded-lg border bg-card/90 p-3 backdrop-blur">
        <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Now playing · {{ KIND_LABEL[snap.now.kind] || snap.now.kind }}</p>
        <p class="mt-1 text-sm font-semibold leading-snug">{{ snap.now.title }}</p>
        <p v-if="snap.now.meta?.hnfm_host" class="mt-0.5 text-xs text-muted-foreground">voice: {{ snap.now.meta.hnfm_host }}</p>
      </div>
      <div v-else-if="snap && !snap.enabled" class="pointer-events-auto rounded-lg border bg-card/90 p-3 backdrop-blur text-sm">
        The station is off. Turn it on (RADIO_ENABLED) and the set comes alive.
      </div>
    </div>

    <!-- HUD: legend, click to explain -->
    <div class="absolute right-5 top-4 w-64 rounded-lg border bg-card/90 p-3 text-xs backdrop-blur">
      <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Who's who</p>
      <ul class="mt-1.5 space-y-1">
        <li v-for="(c, key) in COMPONENTS" :key="key">
          <button type="button" class="flex w-full items-center gap-2 rounded px-1.5 py-1 text-left hover:bg-muted" :class="explain === key ? 'bg-muted' : ''" @click="explain = explain === key ? null : key">
            <span class="inline-block h-2.5 w-2.5 rounded-sm" :style="{ background: c.color }" />
            <span class="font-medium">{{ c.name }}</span>
          </button>
          <p v-if="explain === key" class="mt-1 px-1.5 pb-1 leading-relaxed text-muted-foreground">{{ c.what }}</p>
        </li>
      </ul>
      <div class="mt-2 flex items-center justify-between border-t pt-2 text-muted-foreground">
        <span>{{ snap?.sheet ? `block ${snap.sheet_cursor}/${snap.sheet_items.length} · ${snap.sheet.source}` : 'no block yet' }}</span>
        <NuxtLink to="/radio" class="text-primary hover:underline">control room</NuxtLink>
      </div>
    </div>

    <!-- HUD: the commentary ticker -->
    <div class="pointer-events-none absolute bottom-4 left-5 right-5 md:right-auto md:w-[36rem]">
      <div class="rounded-lg border bg-card/90 p-2.5 font-mono text-[11px] leading-relaxed backdrop-blur">
        <p v-if="!tail.length" class="text-muted-foreground">Waiting for the station to say something…</p>
        <div v-for="l in tail" :key="l.id" class="flex gap-2">
          <span class="w-16 shrink-0 text-muted-foreground">{{ when(l.at) }}</span>
          <span class="w-16 shrink-0 font-semibold" :style="{ color: COMPONENTS[l.component]?.color || 'inherit' }">{{ l.component }}</span>
          <span class="min-w-0 flex-1 truncate">{{ l.message }}</span>
        </div>
      </div>
    </div>

    <div class="absolute bottom-4 right-5 hidden md:block">
      <Button variant="outline" size="sm" as-child>
        <NuxtLink to="/listen" target="_blank"><Icon name="lucide:headphones" class="mr-1.5 h-3.5 w-3.5" />Listen</NuxtLink>
      </Button>
    </div>
  </div>
</template>
