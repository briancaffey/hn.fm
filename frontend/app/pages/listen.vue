<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

/**
 * The public face of HNFM. This is the only page a public host exposes: the
 * player, the show that is on, the words being spoken, the day's schedule
 * and the archive of finished blocks. No controls, no dashboard.
 */
definePageMeta({ layout: false })
useHead({ title: 'HNFM · on air' })

interface Line { speaker: string, mood: string, text: string }
interface Now {
  id: number, at: string, kind: string, title: string | null
  segment?: string | null, name?: string | null, host?: string | null
  text?: Line[] | null, lyrics?: string | null, item_id?: number | null
}
interface Show { key: string, name: string, tagline: string, anchor: string, cohost: string, start: number, end: number, on_air?: boolean }
interface Status {
  enabled: boolean
  now: Now | null
  show?: Show
  schedule?: Show[]
  icecast: { up: boolean, mounts?: { listeners: number }[] }
  produce?: { mode: string, producing: boolean }
}
interface Edition {
  id: string, title: string | null, show_name: string, date: string, aired_at: string
  seconds: number | null, stories: { item_id: number, title: string | null }[]
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase
const status = ref<Status | null>(null)
const history = ref<Now[]>([])
const editions = ref<Edition[]>([])
const open = ref<string | null>(null)

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
    if (!status.value?.enabled) return
    const [h, a] = await Promise.all([
      $fetch<{ events: Now[] }>(`${apiBase}/api/radio/history?hours=2`),
      $fetch<{ editions: Edition[] }>(`${apiBase}/api/radio/archive?limit=12`),
    ])
    history.value = [...h.events].reverse().filter(e => e.kind !== 'music' && e.kind !== 'station_id').slice(0, 8)
    editions.value = a.editions
  } catch { /* the page still shows the player */ }
}
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => { load(); timer = setInterval(load, 8000) })
onUnmounted(() => { if (timer) clearInterval(timer) })

const listeners = computed(() => (status.value?.icecast?.mounts || []).reduce((n, m) => n + (m.listeners || 0), 0))
const now = computed(() => status.value?.now || null)
const show = computed(() => status.value?.show || null)
const cap = (s?: string | null) => s ? s.charAt(0).toUpperCase() + s.slice(1) : ''
const speaker = (s: string) => s.startsWith('caller') ? `Line ${s.replace('caller', '')}` : cap(s)
const hour = (h: number) => `${h % 12 || 12}${h < 12 ? 'am' : 'pm'}`
const when = (iso: string) => new Date(iso.endsWith('Z') || iso.includes('+') || /-\d\d:\d\d$/.test(iso) ? iso : iso + 'Z')
  .toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
const minutes = (s: number | null) => s ? `${Math.round(s / 60)} min` : ''
</script>

<template>
  <main class="min-h-screen bg-background text-foreground">
    <div class="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-10 sm:px-6 sm:py-14">
      <header class="flex flex-col gap-3">
        <div class="flex gap-0.5" aria-hidden="true">
          <span class="h-5 w-5" style="background:#6f3410" /><span class="h-5 w-5" style="background:#8c4210" /><span class="h-5 w-5" style="background:#b5540c" /><span class="h-5 w-5" style="background:#d96208" /><span class="h-5 w-5" style="background:#ff6a00" />
        </div>
        <h1 class="text-2xl font-black tracking-tight">HNFM</h1>
        <p class="text-sm text-muted-foreground">
          Hacker News on the radio. Six shows a day, written, voiced and scored by models running in one house.
        </p>
      </header>

      <section class="rounded-xl border bg-card p-5">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
          <span class="inline-block h-2 w-2 rounded-full" :class="status?.icecast?.up ? 'bg-destructive' : 'bg-muted-foreground'" />
          {{ status?.icecast?.up ? 'On air' : 'Off air' }}
          <span v-if="listeners" class="ml-auto normal-case tracking-normal">{{ listeners }} listening</span>
        </div>

        <div v-if="show" class="mt-3">
          <p class="text-xl font-bold leading-tight">{{ show.name }}</p>
          <p class="text-sm text-muted-foreground">
            {{ show.tagline }} With {{ cap(show.anchor) }} and {{ cap(show.cohost) }}, {{ hour(show.start) }} to {{ hour(show.end) }}.
          </p>
        </div>

        <audio controls preload="none" :src="streamUrl" class="mt-4 w-full" />

        <div v-if="now" class="mt-4 border-t pt-4">
          <p class="text-[11px] uppercase tracking-wider text-muted-foreground">
            Now<template v-if="now.name"> · {{ now.name }}</template>
          </p>
          <p class="mt-1 text-base font-semibold leading-snug">{{ now.title }}</p>
          <div v-if="now.text?.length" class="mt-3 flex flex-col gap-2 text-sm leading-relaxed">
            <p v-for="(l, i) in now.text" :key="i">
              <span class="mr-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{{ speaker(l.speaker) }}</span>{{ l.text }}
            </p>
          </div>
          <pre v-if="now.lyrics" class="mt-3 whitespace-pre-wrap font-sans text-sm italic leading-relaxed text-muted-foreground">{{ now.lyrics }}</pre>
          <a
            v-if="now.item_id" :href="`https://news.ycombinator.com/item?id=${now.item_id}`" target="_blank" rel="noopener"
            class="mt-3 inline-block text-xs text-muted-foreground underline underline-offset-2"
          >The story on Hacker News</a>
        </div>
        <p v-else-if="status?.produce && !status.produce.producing" class="mt-4 border-t pt-4 text-sm text-muted-foreground">
          Music from the library. The hosts start talking a minute or two after someone tunes in.
        </p>
      </section>

      <section v-if="status?.schedule?.length">
        <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Today</p>
        <ol class="mt-2 divide-y text-sm">
          <li v-for="s in status.schedule" :key="s.key" class="flex items-baseline gap-3 py-2" :class="s.on_air ? 'font-semibold' : ''">
            <span class="w-24 shrink-0 font-mono text-xs text-muted-foreground">{{ hour(s.start) }}–{{ hour(s.end) }}</span>
            <span class="min-w-0 flex-1">
              {{ s.name }}
              <span class="block text-xs font-normal text-muted-foreground">{{ s.tagline }}</span>
            </span>
            <span v-if="s.on_air" class="shrink-0 rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wider">On now</span>
          </li>
        </ol>
      </section>

      <section v-if="history.length">
        <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Recently on</p>
        <ol class="mt-2 divide-y text-sm">
          <li v-for="e in history" :key="e.id" class="flex gap-3 py-2">
            <span class="w-16 shrink-0 font-mono text-xs text-muted-foreground">{{ when(e.at) }}</span>
            <span class="min-w-0 flex-1 truncate">{{ e.title }}</span>
          </li>
        </ol>
      </section>

      <section v-if="editions.length">
        <div class="flex items-baseline justify-between gap-3">
          <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Listen again</p>
          <a :href="`${apiBase}/api/radio/archive/feed.xml`" class="text-xs text-muted-foreground underline underline-offset-2">Podcast feed</a>
        </div>
        <ul class="mt-2 divide-y text-sm">
          <li v-for="e in editions" :key="e.id" class="py-3">
            <button type="button" class="flex w-full items-baseline gap-3 text-left" :aria-expanded="open === e.id" @click="open = open === e.id ? null : e.id">
              <span class="w-24 shrink-0 font-mono text-xs text-muted-foreground">{{ e.date.slice(5) }} {{ when(e.aired_at) }}</span>
              <span class="min-w-0 flex-1">
                <span class="font-medium">{{ e.show_name }}</span>
                <span class="text-muted-foreground"> · {{ e.title }}</span>
              </span>
              <span class="shrink-0 text-xs text-muted-foreground">{{ minutes(e.seconds) }}</span>
            </button>
            <div v-if="open === e.id" class="mt-3 flex flex-col gap-2">
              <audio controls preload="none" :src="`${apiBase}/api/radio/archive/${e.id}.mp3`" class="w-full" />
              <ul class="list-disc pl-5 text-xs text-muted-foreground">
                <li v-for="s in e.stories" :key="s.item_id">{{ s.title }}</li>
              </ul>
            </div>
          </li>
        </ul>
      </section>

      <footer class="text-xs text-muted-foreground">
        Stream: <span class="break-all font-mono">{{ streamUrl }}</span>. Paste it into any player.
      </footer>
    </div>
  </main>
</template>
