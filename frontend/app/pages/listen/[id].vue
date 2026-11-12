<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Icon } from '#components'
import EditionPlayer from '~/components/radio/EditionPlayer.vue'
import type { Edition, RundownItem } from '~/composables/useStation'

/**
 * One edition, standing on its own: the player, the chapters, and the
 * words as they are spoken. The booth records when each line starts, so
 * the line being said is the line that is lit, and any line can be
 * clicked to hear it.
 */
definePageMeta({ layout: false })

const route = useRoute()
const { apiBase, art, audio, cap, speaker, mins, clock, day } = useStation()
const id = computed(() => String(route.params.id))
const { data: edition, error } = await useAsyncData<Edition>(`edition-${id.value}`,
  () => $fetch(`${apiBase}/api/radio/archive/${id.value}`))
useHead({ title: () => edition.value ? `${edition.value.show_name} · ${day(edition.value.date)} · HNFM` : 'HNFM' })

const player = ref<InstanceType<typeof EditionPlayer> | null>(null)
const t = ref(0)
const follow = ref(true)
const watching = ref(false)

const rundown = computed<RundownItem[]>(() => edition.value?.rundown || [])
const spoken = (r: RundownItem) => !!(r.text?.length || r.lyrics)
const chapters = computed(() => rundown.value.filter(spoken))
const marks = computed(() => chapters.value.map(r => ({ at: r.at, title: r.title || r.name || '' })))
const current = computed(() => {
  let found = -1
  rundown.value.forEach((r, i) => { if (t.value >= r.at) found = i })
  return found
})
/** Which line of item `i` is being said at time `t`, or -1. */
function lineAt(r: RundownItem, i: number): number {
  if (i !== current.value || !r.cues?.length) return -1
  const local = t.value - r.at
  let n = -1
  for (const c of r.cues) if (local >= c.at - 0.15) n = c.n
  return n
}
function seekLine(r: RundownItem, n: number) {
  const c = r.cues?.find(c => c.n === n)
  player.value?.seek(r.at + (c ? c.at : 0))
}
// Keep the line being spoken in view, unless the reader has scrolled away.
watch(() => [current.value, current.value >= 0 ? lineAt(rundown.value[current.value]!, current.value) : -1], async () => {
  if (!follow.value || !t.value) return
  await nextTick()
  document.querySelector('[data-now="line"]')?.scrollIntoView({ block: 'center', behavior: 'smooth' })
})
const label = (r: RundownItem) => r.title || r.name || 'Music'
const score = computed(() => {
  const m = rundown.value.map(r => r.qa?.match).filter((x): x is number => typeof x === 'number')
  return m.length ? Math.round((m.reduce((a, b) => a + b, 0) / m.length) * 100) : null
})
</script>

<template>
  <main class="min-h-screen bg-background text-foreground">
    <div class="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
      <NuxtLink to="/listen" class="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <Icon name="lucide:arrow-left" class="h-4 w-4" /> HNFM
      </NuxtLink>

      <p v-if="error || !edition" class="mt-10 text-sm text-muted-foreground">
        That edition is not in the archive. <NuxtLink to="/listen" class="underline">Back to the station.</NuxtLink>
      </p>

      <template v-else>
        <header class="mt-6 grid items-end gap-6 sm:grid-cols-[200px_minmax(0,1fr)]">
          <img :src="art(edition.show)" :alt="`${edition.show_name} cover`" class="aspect-square w-40 rounded-xl border object-cover sm:w-full">
          <div class="min-w-0">
            <p class="text-xs font-semibold uppercase tracking-widest text-primary">
              {{ day(edition.date) }}<template v-if="edition.kind === 'episode'"> · the whole hour</template>
            </p>
            <h1 class="mt-1 text-4xl font-black leading-none tracking-tight sm:text-5xl">{{ edition.show_name }}</h1>
            <p class="mt-2 text-muted-foreground">{{ edition.tagline || edition.title }}</p>
            <p class="mt-2 text-sm text-muted-foreground">
              With {{ cap(edition.anchor) }} and {{ cap(edition.cohost) }} · {{ mins(edition.seconds) }} ·
              {{ edition.stories.length }} stories
            </p>
          </div>
        </header>

        <div class="sticky top-0 z-10 -mx-4 mt-6 bg-background/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
          <EditionPlayer ref="player" :src="audio(edition.id)" :seconds="edition.seconds" :marks="marks" @time="t = $event" />
        </div>

        <div class="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
          <a :href="audio(edition.id)" download class="inline-flex items-center gap-1 hover:text-foreground"><Icon name="lucide:download" class="h-3.5 w-3.5" /> MP3</a>
          <a :href="`${apiBase}/api/radio/archive/${edition.id}/transcript.txt`" target="_blank" class="inline-flex items-center gap-1 hover:text-foreground"><Icon name="lucide:file-text" class="h-3.5 w-3.5" /> Transcript</a>
          <button v-if="edition.video" type="button" class="inline-flex items-center gap-1 hover:text-foreground" @click="watching = !watching">
            <Icon name="lucide:video" class="h-3.5 w-3.5" /> {{ watching ? 'Hide the video' : 'Watch it' }}
          </button>
          <label class="ml-auto inline-flex cursor-pointer items-center gap-1.5">
            <input v-model="follow" type="checkbox" class="accent-[var(--primary)]"> Follow along
          </label>
        </div>

        <video
          v-if="watching" controls preload="metadata" class="mt-4 w-full rounded-xl border"
          :src="`${apiBase}/api/radio/archive/${edition.id}/video.mp4`"
        />

        <div class="mt-8 grid gap-10 lg:grid-cols-[260px_minmax(0,1fr)]">
          <!-- Chapters -->
          <aside class="lg:sticky lg:top-24 lg:max-h-[calc(100vh-7rem)] lg:self-start lg:overflow-y-auto">
            <h2 class="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Running order</h2>
            <ol class="text-sm">
              <li v-for="(r, i) in rundown" :key="i">
                <button
                  type="button" class="flex w-full items-baseline gap-3 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted"
                  :class="i === current ? 'bg-primary/10 text-primary' : spoken(r) ? '' : 'text-muted-foreground'"
                  @click="player?.seek(r.at)"
                >
                  <span class="w-9 shrink-0 font-mono text-[11px] tabular-nums opacity-70">{{ clock(r.at) }}</span>
                  <span class="min-w-0 flex-1 truncate">
                    <Icon v-if="!spoken(r)" name="lucide:music" class="mr-1 inline h-3 w-3" />{{ spoken(r) ? label(r) : (r.name || 'Music') }}
                  </span>
                </button>
              </li>
            </ol>

            <h2 class="mb-2 mt-6 text-xs font-semibold uppercase tracking-widest text-muted-foreground">The stories</h2>
            <ul class="flex flex-col gap-1.5 text-sm">
              <li v-for="s in edition.stories" :key="s.item_id">
                <a :href="`https://news.ycombinator.com/item?id=${s.item_id}`" target="_blank" rel="noopener" class="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">{{ s.title }}</a>
              </li>
            </ul>
            <p v-if="score" class="mt-6 text-xs leading-relaxed text-muted-foreground">
              Every line was transcribed by a speech recogniser before it aired and compared with its script.
              This edition matched {{ score }}%.
            </p>
          </aside>

          <!-- The words -->
          <section class="min-w-0">
            <template v-for="(r, i) in rundown" :key="i">
              <article v-if="spoken(r)" class="mb-8">
                <button type="button" class="mb-2 flex w-full items-baseline gap-3 text-left" @click="player?.seek(r.at)">
                  <span class="font-mono text-xs tabular-nums text-muted-foreground">{{ clock(r.at) }}</span>
                  <span class="text-xs font-semibold uppercase tracking-widest" :class="i === current ? 'text-primary' : 'text-muted-foreground'">{{ r.name }}</span>
                </button>
                <h3 v-if="r.story" class="mb-3 text-lg font-bold leading-snug">{{ r.title }}</h3>
                <p
                  v-for="(l, n) in r.text || []" :key="n"
                  class="-mx-2 cursor-pointer rounded-md px-2 py-1.5 leading-relaxed transition-colors hover:bg-muted"
                  :class="lineAt(r, i) === n ? 'bg-primary/10' : ''"
                  :data-now="lineAt(r, i) === n ? 'line' : undefined"
                  @click="seekLine(r, n)"
                >
                  <span class="mr-2 text-[11px] font-bold uppercase tracking-wider" :class="l.speaker.startsWith('caller') ? 'text-muted-foreground' : 'text-primary'">{{ speaker(l.speaker) }}</span>{{ l.text }}
                </p>
                <pre v-if="r.lyrics" class="mt-3 whitespace-pre-wrap border-l-2 border-primary/40 pl-4 font-sans text-sm italic leading-relaxed text-muted-foreground">{{ r.lyrics }}</pre>
              </article>
              <p v-else class="mb-8 flex items-center gap-2 text-xs text-muted-foreground">
                <span class="font-mono tabular-nums">{{ clock(r.at) }}</span>
                <Icon name="lucide:music" class="h-3.5 w-3.5" />
                <span class="truncate">{{ r.title || r.name }}</span>
              </p>
            </template>
          </section>
        </div>
      </template>
    </div>
  </main>
</template>
