<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '#components'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import EmptyState from '~/components/kit/EmptyState.vue'
import StatTile from '~/components/kit/StatTile.vue'
import StatusBadge from '~/components/kit/StatusBadge.vue'

/**
 * HNFM on air (plans/20): the station's control room. Listen, see what is
 * playing and what the producer planned, queue a story, skip.
 */
useHead({ title: 'hn.fm · Radio' })

interface Event { id: number, at: string, kind: string, title: string | null, ref: string | null, meta: Record<string, string> }
interface Sheet { sheet_id: string, title: string | null, source: string | null, cursor: number, items: number | Array<Record<string, string | number | null>>, created_at: string | null, tokens_in?: number | null, tokens_out?: number | null, model?: string | null }
interface Status {
  enabled: boolean
  now: Event | null
  queue: string[]
  sheet: Sheet | null
  bank: Record<string, number>
  episodes: number
  icecast: { up: boolean, error?: string, mounts?: { mount: string, listeners: number, peak: number, title: string | null, bitrate: string | null }[], server_start?: string }
  root: string
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const status = ref<Status | null>(null)
const history = ref<Event[]>([])
const sheets = ref<Sheet[]>([])
const loading = ref(true)
const message = ref('')
const queueRef = ref('')

/** The stream, on the same origin as the API: /radio/hnfm.mp3 behind the
 *  ingress, or the compose port locally. */
const streamUrl = computed(() => {
  try {
    const u = new URL(apiBase)
    if (u.hostname === 'localhost' || u.hostname === '127.0.0.1') return 'http://localhost:8010/hnfm.mp3'
    return `${u.origin}/radio/hnfm.mp3`
  } catch { return '/radio/hnfm.mp3' }
})

async function load() {
  try {
    status.value = await $fetch<Status>(`${apiBase}/api/radio/status`)
    if (status.value?.enabled) {
      const [h, s] = await Promise.all([
        $fetch<{ events: Event[] }>(`${apiBase}/api/radio/history?hours=3`),
        $fetch<{ sheets: Sheet[] }>(`${apiBase}/api/radio/sheets?limit=5`),
      ])
      history.value = [...h.events].reverse()
      sheets.value = s.sheets
    }
  } finally {
    loading.value = false
  }
}
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => { load(); timer = setInterval(load, 15000) })
onUnmounted(() => { if (timer) clearInterval(timer) })

async function act(path: string, body?: Record<string, unknown>, note = '') {
  try {
    await $fetch(`${apiBase}${path}`, { method: 'POST', body })
    message.value = note
    await load()
  } catch (e: unknown) {
    message.value = `Failed: ${e}`
  }
}
const listeners = computed(() => (status.value?.icecast?.mounts || []).reduce((n, m) => n + (m.listeners || 0), 0))
const when = (iso: string) => new Date(iso.endsWith('Z') ? iso : iso + 'Z').toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
const KIND_LABEL: Record<string, string> = { episode: 'Episode', station_id: 'Station ID', coming_up: 'Coming up', music: 'Music', time_check: 'Time check', brief: 'Brief', unknown: '—' }
</script>

<template>
  <PageShell>
    <PageHeader
      title="Radio"
      subtitle="HNFM on air: what is playing, what the producer planned, and the controls."
      hint="The producer plans a block of programming with one call to the local model; the DJ (Liquidsoap) asks the API what to play next and reports every track change; Icecast fans the stream out to listeners. Everything here is off unless RADIO_ENABLED is true."
    >
      <template #actions>
        <Button size="sm" as-child>
          <NuxtLink to="/studio"><Icon name="lucide:box" class="mr-1.5 h-3.5 w-3.5" />Open the Studio</NuxtLink>
        </Button>
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <EmptyState
      v-if="status && !status.enabled"
      icon="lucide:radio"
      title="The station is off"
      body="Set RADIO_ENABLED=true (and start the radio compose profile, or radio.enabled in the chart) and this page comes alive. Nothing runs until then."
    />

    <template v-else-if="status">
      <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div class="space-y-4">
          <div class="rounded-lg border bg-card p-4">
            <div class="flex flex-wrap items-center gap-3">
              <StatusBadge :status="status.icecast.up ? 'ok' : 'failed'" :label="status.icecast.up ? 'On air' : 'Transmitter down'" dot />
              <span class="text-xs text-muted-foreground font-mono">{{ streamUrl }}</span>
            </div>
            <audio controls preload="none" :src="streamUrl" class="mt-3 w-full" />
            <div v-if="status.now" class="mt-4">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Now playing · {{ KIND_LABEL[status.now.kind] || status.now.kind }}</p>
              <p class="mt-1 text-lg font-semibold leading-snug">{{ status.now.title || '—' }}</p>
              <p class="mt-0.5 text-xs text-muted-foreground">
                since {{ when(status.now.at) }}
                <template v-if="status.now.meta?.hnfm_host"> · voice {{ status.now.meta.hnfm_host }}</template>
                <NuxtLink v-if="status.now.ref" :to="`/hn/item/${status.now.ref.split(':')[0]}/run/${status.now.ref.split(':')[1]}/segment/${status.now.ref.split(':')[2]}`" class="ml-2 text-primary hover:underline">open segment</NuxtLink>
              </p>
            </div>
            <p v-else class="mt-4 text-sm text-muted-foreground">Nothing reported yet. The DJ reports each track as it starts.</p>
            <div class="mt-4 flex flex-wrap items-center gap-2">
              <Button size="sm" variant="outline" @click="act('/api/radio/skip', undefined, 'Skipped.')">
                <Icon name="lucide:skip-forward" class="mr-1.5 h-3.5 w-3.5" />Skip
              </Button>
              <Button size="sm" variant="outline" @click="act('/api/radio/plan', {}, 'Planning a new block.')">
                <Icon name="lucide:list-music" class="mr-1.5 h-3.5 w-3.5" />Plan a block
              </Button>
              <Button size="sm" variant="outline" @click="act('/api/radio/bank/fill', {}, 'Filling the bank.')">
                <Icon name="lucide:package-plus" class="mr-1.5 h-3.5 w-3.5" />Fill the bank
              </Button>
              <span v-if="message" class="text-xs text-muted-foreground">{{ message }}</span>
            </div>
          </div>

          <div class="rounded-lg border bg-card p-4">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Last three hours</p>
            <ol v-if="history.length" class="mt-2 divide-y text-sm">
              <li v-for="e in history" :key="e.id" class="flex items-center gap-3 py-1.5">
                <span class="w-14 shrink-0 font-mono text-xs text-muted-foreground">{{ when(e.at) }}</span>
                <span class="w-20 shrink-0 rounded border px-1.5 py-0.5 text-center text-[10px] text-muted-foreground">{{ KIND_LABEL[e.kind] || e.kind }}</span>
                <span class="min-w-0 flex-1 truncate">{{ e.title }}</span>
                <span v-if="e.meta?.hnfm_host" class="text-xs text-muted-foreground">{{ e.meta.hnfm_host }}</span>
              </li>
            </ol>
            <p v-else class="mt-2 text-sm text-muted-foreground">No history yet.</p>
          </div>
        </div>

        <div class="space-y-4">
          <div class="grid grid-cols-2 gap-3">
            <StatTile label="Listeners" :value="listeners" :hint="status.icecast.up ? 'right now' : 'icecast down'" />
            <StatTile label="Episodes" :value="status.episodes" hint="ready to air" />
            <StatTile label="Station IDs" :value="status.bank.station_id || 0" hint="in the bank" />
            <StatTile label="Music beds" :value="status.bank.music || 0" hint="in the bank" />
          </div>

          <div class="rounded-lg border bg-card p-4">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Play next</p>
            <p class="mt-1 text-xs text-muted-foreground">An episode ref, item:run:seg — from a segment page's URL.</p>
            <div class="mt-2 flex gap-2">
              <Input v-model="queueRef" placeholder="49584615:2:1" class="h-8 text-xs font-mono" />
              <Button size="sm" class="h-8" :disabled="!queueRef" @click="act('/api/radio/queue', { ref: queueRef }, `Queued ${queueRef}.`); queueRef = ''">Queue</Button>
            </div>
            <ul v-if="status.queue.length" class="mt-2 space-y-1 font-mono text-xs">
              <li v-for="r in status.queue" :key="r">{{ r }}</li>
            </ul>
          </div>

          <div class="rounded-lg border bg-card p-4">
            <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Blocks</p>
            <ul v-if="sheets.length" class="mt-2 space-y-2 text-sm">
              <li v-for="s in sheets" :key="s.sheet_id" class="rounded border px-2.5 py-2">
                <div class="flex items-center justify-between gap-2">
                  <span class="truncate font-medium">{{ s.title || s.sheet_id }}</span>
                  <span class="shrink-0 rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">{{ s.source }}</span>
                </div>
                <p class="mt-0.5 text-xs text-muted-foreground">
                  {{ s.cursor }} / {{ Array.isArray(s.items) ? s.items.length : s.items }} played
                  <template v-if="s.tokens_in"> · {{ s.tokens_in }}/{{ s.tokens_out }} tokens</template>
                  <template v-if="s.created_at"> · {{ when(s.created_at) }}</template>
                </p>
              </li>
            </ul>
            <p v-else class="mt-2 text-sm text-muted-foreground">No block planned yet.</p>
          </div>
        </div>
      </div>
    </template>
  </PageShell>
</template>
