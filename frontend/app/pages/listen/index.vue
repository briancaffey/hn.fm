<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '#components'
import EditionPlayer from '~/components/radio/EditionPlayer.vue'
import type { Character, Edition, StationStatus } from '~/composables/useStation'

/**
 * The public face of HNFM. Editions come first: the station makes
 * programmes, not a continuous feed, so the newest one is at the top and
 * playable, the shows are below it, and the live stream is a strip that
 * says honestly what it is playing.
 */
definePageMeta({ layout: false })
useHead({ title: 'HNFM · Hacker News on the radio' })

const { apiBase, art, audio, cap, hour, mins, day, streamUrl } = useStation()
const status = ref<StationStatus | null>(null)
const editions = ref<Edition[]>([])
const cast = ref<Character[]>([])
const filter = ref<string | null>(null)
const loaded = ref(false)

async function load() {
  try {
    status.value = await $fetch<StationStatus>(`${apiBase}/api/radio/status`)
    if (!status.value?.enabled) return
    const [a, c] = await Promise.all([
      $fetch<{ editions: Edition[] }>(`${apiBase}/api/radio/archive?limit=120`),
      cast.value.length ? Promise.resolve({ cast: cast.value }) : $fetch<{ cast: Character[] }>(`${apiBase}/api/radio/cast`),
    ])
    editions.value = a.editions
    cast.value = c.cast
  } catch { /* the page still stands */ } finally { loaded.value = true }
}
const pasteUrl = ref('')
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  pasteUrl.value = streamUrl.value.startsWith('/') ? window.location.origin + streamUrl.value : streamUrl.value
  load(); timer = setInterval(load, 20000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })

const shows = computed(() => status.value?.schedule || [])
// Newest first by when it was for, with a featured edition ahead of the rest.
const ordered = computed(() => [...editions.value].sort((a, b) =>
  (Number(!!b.featured) - Number(!!a.featured)) || b.aired_at.localeCompare(a.aired_at)))
const lead = computed(() => ordered.value.find(e => e.kind === 'episode') || ordered.value[0] || null)
const listed = computed(() => ordered.value.filter(e => e.id !== lead.value?.id && (!filter.value || e.show === filter.value)))
const count = (key: string) => editions.value.filter(e => e.show === key).length
const hosts = computed(() => cast.value.filter(c => c.role === 'host'))
const others = computed(() => cast.value.filter(c => c.role === 'correspondent'))
const listeners = computed(() => (status.value?.icecast?.mounts || []).reduce((n, m) => n + (m.listeners || 0), 0))
const liveLine = computed(() => {
  const s = status.value
  if (!s?.icecast?.up) return 'The transmitter is off.'
  if (s.now?.title && s.produce?.producing) return `Now: ${s.now.title}`
  return 'Playing from the library: music and pieces already made.'
})
</script>

<template>
  <main class="min-h-screen bg-background text-foreground">
    <div class="mx-auto flex max-w-5xl flex-col gap-12 px-4 py-8 sm:px-6 sm:py-12">
      <header class="flex items-center justify-between gap-4">
        <NuxtLink to="/listen" class="flex items-center gap-3">
          <span class="flex gap-0.5" aria-hidden="true">
            <span v-for="c in ['#6f3410', '#8c4210', '#b5540c', '#d96208', '#ff6a00']" :key="c" class="h-5 w-5" :style="{ background: c }" />
          </span>
          <span class="text-xl font-black tracking-tight">HNFM</span>
        </NuxtLink>
        <nav class="flex items-center gap-4 text-sm text-muted-foreground">
          <NuxtLink to="/listen/station" class="hover:text-foreground">The station</NuxtLink>
          <a :href="`${apiBase}/api/radio/archive/feed.xml`" class="hover:text-foreground">Podcast feed</a>
        </nav>
      </header>

      <!-- The newest edition -->
      <section v-if="lead" class="grid items-center gap-6 sm:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] sm:gap-10">
        <NuxtLink :to="`/listen/${lead.id}`" class="block overflow-hidden rounded-2xl border bg-card">
          <img :src="art(lead.show)" :alt="`${lead.show_name} cover`" class="aspect-square w-full object-cover" loading="eager">
        </NuxtLink>
        <div class="flex min-w-0 flex-col gap-4">
          <p class="text-xs font-semibold uppercase tracking-widest text-primary">
            {{ lead.featured ? 'Featured' : 'Latest' }} · {{ day(lead.date) }}
          </p>
          <h1 class="text-4xl font-black leading-none tracking-tight sm:text-5xl">{{ lead.show_name }}</h1>
          <p class="text-lg text-muted-foreground">{{ lead.tagline || shows.find(s => s.key === lead?.show)?.tagline || lead.title }}</p>
          <p class="text-sm text-muted-foreground">
            With {{ cap(lead.anchor) }} and {{ cap(lead.cohost) }} · {{ mins(lead.seconds) }} · {{ lead.stories.length }} stories
          </p>
          <EditionPlayer :src="audio(lead.id)" :seconds="lead.seconds" />
          <ul class="flex flex-col gap-1 text-sm">
            <li v-for="s in lead.stories.slice(0, 4)" :key="s.item_id" class="truncate text-muted-foreground">
              <span class="mr-2 text-primary">—</span>{{ s.title }}
            </li>
          </ul>
          <NuxtLink :to="`/listen/${lead.id}`" class="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
            Chapters and the words as they are spoken <Icon name="lucide:arrow-right" class="h-4 w-4" />
          </NuxtLink>
        </div>
      </section>
      <section v-else-if="loaded" class="rounded-2xl border bg-card p-8 text-center">
        <img :src="art('station')" alt="" class="mx-auto mb-6 aspect-square w-48 rounded-xl object-cover">
        <h1 class="text-3xl font-black tracking-tight">Hacker News on the radio</h1>
        <p class="mt-2 text-sm text-muted-foreground">No editions have been made yet. The first one will appear here.</p>
      </section>

      <!-- Live -->
      <section class="flex flex-col gap-2">
        <EditionPlayer :src="streamUrl" live compact>{{ liveLine }}</EditionPlayer>
        <p class="px-2 text-xs text-muted-foreground">
          <template v-if="status?.show">On the schedule now: {{ status.show.name }}. </template>
          <template v-if="listeners">{{ listeners }} listening. </template>
          <template v-if="status?.produce?.mode === 'off'">The station is not making new programmes around the clock; it makes editions.</template>
        </p>
      </section>

      <!-- The shows -->
      <section v-if="shows.length">
        <h2 class="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Six shows a day</h2>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <button
            v-for="s in shows" :key="s.key" type="button"
            class="group overflow-hidden rounded-xl border bg-card text-left transition-colors"
            :class="filter === s.key ? 'border-primary' : 'hover:border-primary/50'"
            :aria-pressed="filter === s.key" @click="filter = filter === s.key ? null : s.key"
          >
            <img :src="art(s.key)" :alt="`${s.name} cover`" class="aspect-[16/10] w-full object-cover" loading="lazy">
            <div class="p-3">
              <p class="flex items-baseline justify-between gap-2">
                <span class="truncate font-bold">{{ s.name }}</span>
                <span class="shrink-0 font-mono text-[11px] text-muted-foreground">{{ hour(s.start) }}–{{ hour(s.end) }}</span>
              </p>
              <p class="mt-0.5 text-xs leading-snug text-muted-foreground">{{ s.tagline }}</p>
              <p class="mt-2 text-[11px] text-muted-foreground">
                {{ cap(s.anchor) }} &amp; {{ cap(s.cohost) }}<template v-if="count(s.key)"> · {{ count(s.key) }} to hear</template>
              </p>
            </div>
          </button>
        </div>
      </section>

      <!-- Listen again -->
      <section v-if="listed.length || filter">
        <div class="mb-3 flex items-baseline justify-between gap-3">
          <h2 class="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            {{ filter ? shows.find(s => s.key === filter)?.name : 'Listen again' }}
          </h2>
          <button v-if="filter" type="button" class="text-xs text-muted-foreground underline underline-offset-2" @click="filter = null">All shows</button>
        </div>
        <p v-if="!listed.length" class="text-sm text-muted-foreground">Nothing from this show yet.</p>
        <ul class="divide-y">
          <li v-for="e in listed.slice(0, 40)" :key="e.id">
            <NuxtLink :to="`/listen/${e.id}`" class="flex items-center gap-4 py-3 hover:bg-muted/40">
              <img :src="art(e.show)" alt="" class="h-14 w-14 shrink-0 rounded-md object-cover" loading="lazy">
              <span class="min-w-0 flex-1">
                <span class="flex items-baseline gap-2">
                  <span class="truncate font-semibold">{{ e.show_name }}</span>
                  <span v-if="e.kind === 'episode'" class="shrink-0 rounded border px-1 text-[10px] uppercase tracking-wider text-muted-foreground">Whole hour</span>
                  <Icon v-if="e.video" name="lucide:video" class="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                </span>
                <span class="block truncate text-sm text-muted-foreground">{{ e.stories.map(s => s.title).filter(Boolean).slice(0, 2).join(' · ') || e.title }}</span>
              </span>
              <span class="shrink-0 text-right text-xs text-muted-foreground">
                <span class="block">{{ day(e.date) }}</span>
                <span class="block font-mono">{{ mins(e.seconds) }}</span>
              </span>
            </NuxtLink>
          </li>
        </ul>
      </section>

      <!-- The people -->
      <section v-if="hosts.length">
        <div class="mb-4 flex items-baseline justify-between gap-3">
          <h2 class="text-xs font-semibold uppercase tracking-widest text-muted-foreground">The voices</h2>
          <NuxtLink to="/listen/station" class="text-xs text-muted-foreground underline underline-offset-2">Hear each of them</NuxtLink>
        </div>
        <div class="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
          <div v-for="c in [...hosts, ...others]" :key="c.key" class="flex gap-3">
            <span class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-primary/15 text-sm font-bold text-primary">{{ c.name.charAt(0) }}</span>
            <span class="min-w-0">
              <span class="block text-sm font-semibold">{{ c.name }} <span v-if="c.role !== 'host'" class="font-normal text-muted-foreground">· correspondent</span></span>
              <span class="block text-xs leading-snug text-muted-foreground">{{ c.line }}</span>
            </span>
          </div>
        </div>
      </section>

      <footer class="border-t pt-6 text-xs leading-relaxed text-muted-foreground">
        <p>Written, voiced, scored and drawn by models running in one house. Nobody is in the building.</p>
        <p class="mt-1">Stream address: <span class="break-all font-mono">{{ pasteUrl || streamUrl }}</span></p>
      </footer>
    </div>
  </main>
</template>
