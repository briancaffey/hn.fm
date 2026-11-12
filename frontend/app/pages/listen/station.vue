<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '#components'
import type { Character, Show } from '~/composables/useStation'

/**
 * The station, explained by being heard: every voice in every mood it
 * has, every treatment a voice can be put through, every effect. Nothing
 * here is recorded; each sample is made by the models when it is asked for
 * (and kept, so the second listen costs nothing).
 */
definePageMeta({ layout: false })
useHead({ title: 'The station · HNFM' })

interface Fx { key: string, name: string, what: string, seconds?: number }
const { apiBase, art, cap, hour } = useStation()
const { data } = await useAsyncData('station', async () => {
  const [c, s] = await Promise.all([
    $fetch<{ cast: Character[], callers: number, effects: Fx[], treatments: Fx[] }>(`${apiBase}/api/radio/cast`),
    $fetch<{ shows: Show[] }>(`${apiBase}/api/radio/schedule`),
  ])
  return { ...c, shows: s.shows }
})

const playing = ref<string | null>(null)
let el: HTMLAudioElement | null = null
function play(key: string, url: string) {
  el?.pause()
  if (playing.value === key) { playing.value = null; return }
  el = new Audio(url)
  playing.value = key
  el.onended = el.onerror = () => { if (playing.value === key) playing.value = null }
  el.play().catch(() => { playing.value = null })
}
const audition = (c: Character, mood: string, treatment = '') =>
  play(`${c.key}:${mood}:${treatment}`,
    `${apiBase}/api/radio/audition.mp3?speaker=${c.key}&mood=${mood}${treatment ? `&treatment=${treatment}` : ''}`)
const people = computed(() => (data.value?.cast || []).filter(c => c.role !== 'announcer'))
const announcer = computed(() => (data.value?.cast || []).find(c => c.role === 'announcer'))
const voice = ref('mia')
const voiceOf = computed(() => people.value.find(c => c.key === voice.value) || people.value[0])
</script>

<template>
  <main class="min-h-screen bg-background text-foreground">
    <div class="mx-auto flex max-w-5xl flex-col gap-12 px-4 py-8 sm:px-6 sm:py-10">
      <NuxtLink to="/listen" class="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <Icon name="lucide:arrow-left" class="h-4 w-4" /> HNFM
      </NuxtLink>

      <header class="grid items-center gap-6 sm:grid-cols-[220px_minmax(0,1fr)]">
        <img :src="art('station')" alt="A radio mast on the roof of a small house" class="aspect-square w-40 rounded-xl border object-cover sm:w-full">
        <div>
          <h1 class="text-4xl font-black tracking-tight sm:text-5xl">The station</h1>
          <p class="mt-3 max-w-prose text-muted-foreground">
            HNFM reads Hacker News and makes radio of it. A language model writes, a speech model voices a cast of
            {{ people.length }} and {{ data?.callers }} callers, a music model plays and sings, an image model drew the
            covers, and a speech recogniser listens to every line before it airs. All of it runs on computers in one
            house. Press anything on this page to hear it.
          </p>
        </div>
      </header>

      <section v-if="people.length">
        <h2 class="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">The cast, in every mood they have</h2>
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div v-for="c in people" :key="c.key" class="flex flex-col gap-3 rounded-xl border bg-card p-4">
            <div class="flex items-center gap-3">
              <span class="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-primary/15 text-base font-bold text-primary">{{ c.name.charAt(0) }}</span>
              <span class="min-w-0">
                <span class="block font-bold">{{ c.name }}</span>
                <span class="block truncate text-xs text-muted-foreground">
                  {{ c.role === 'host' ? c.shows.join(', ') : `Correspondent: ${c.beat}` }}
                </span>
              </span>
            </div>
            <p class="text-sm leading-snug text-muted-foreground">{{ c.line }}</p>
            <div class="mt-auto flex flex-wrap gap-1.5">
              <button
                v-for="m in c.moods" :key="m" type="button"
                class="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors"
                :class="playing === `${c.key}:${m}:` ? 'border-primary bg-primary text-primary-foreground' : 'hover:border-primary/60'"
                @click="audition(c, m)"
              >
                <Icon :name="playing === `${c.key}:${m}:` ? 'lucide:square' : 'lucide:play'" class="h-3 w-3" />{{ m === 'default' ? 'natural' : m }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="data?.treatments?.length && voiceOf">
        <h2 class="mb-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Where a voice is speaking from</h2>
        <p class="mb-4 text-sm text-muted-foreground">
          The same line by
          <select v-model="voice" class="rounded-md border bg-background px-1.5 py-0.5 text-foreground" aria-label="Voice">
            <option v-for="c in people" :key="c.key" :value="c.key">{{ c.name }}</option>
          </select>
          put through each treatment. Hosts are in the studio, callers on the phone, correspondents on a line from outside.
        </p>
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <button
            v-for="tr in data.treatments" :key="tr.key" type="button"
            class="flex items-start gap-3 rounded-xl border bg-card p-4 text-left transition-colors hover:border-primary/60"
            :class="playing === `${voiceOf.key}:default:${tr.key}` ? 'border-primary' : ''"
            @click="audition(voiceOf, 'default', tr.key)"
          >
            <Icon :name="playing === `${voiceOf.key}:default:${tr.key}` ? 'lucide:square' : 'lucide:play'" class="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span><span class="block text-sm font-semibold">{{ tr.name }}</span><span class="block text-xs leading-snug text-muted-foreground">{{ tr.what }}</span></span>
          </button>
          <button
            v-if="announcer" type="button"
            class="flex items-start gap-3 rounded-xl border bg-card p-4 text-left transition-colors hover:border-primary/60"
            :class="playing === 'announcer:default:' ? 'border-primary' : ''" @click="audition(announcer, 'default')"
          >
            <Icon :name="playing === 'announcer:default:' ? 'lucide:square' : 'lucide:play'" class="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span><span class="block text-sm font-semibold">The announcer</span><span class="block text-xs leading-snug text-muted-foreground">{{ announcer.line }}</span></span>
          </button>
        </div>
      </section>

      <section v-if="data?.effects?.length">
        <h2 class="mb-1 text-xs font-semibold uppercase tracking-widest text-muted-foreground">The effects</h2>
        <p class="mb-4 text-sm text-muted-foreground">Synthesised from sine waves and noise. No recordings, no samples.</p>
        <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <button
            v-for="e in data.effects" :key="e.key" type="button"
            class="flex items-start gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors hover:border-primary/60"
            :class="playing === `fx:${e.key}` ? 'border-primary' : ''"
            @click="play(`fx:${e.key}`, `${apiBase}/api/radio/fx/${e.key}.wav`)"
          >
            <Icon :name="playing === `fx:${e.key}` ? 'lucide:square' : 'lucide:play'" class="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span><span class="block text-sm font-semibold">{{ e.name }}</span><span class="block text-xs leading-snug text-muted-foreground">{{ e.what }}</span></span>
          </button>
        </div>
      </section>

      <section v-if="data?.shows?.length">
        <h2 class="mb-4 text-xs font-semibold uppercase tracking-widest text-muted-foreground">The day</h2>
        <ol class="divide-y">
          <li v-for="s in data.shows" :key="s.key" class="flex items-center gap-4 py-3">
            <img :src="art(s.key)" alt="" class="h-16 w-16 shrink-0 rounded-md object-cover" loading="lazy">
            <span class="w-24 shrink-0 font-mono text-xs text-muted-foreground">{{ hour(s.start) }}–{{ hour(s.end) }}</span>
            <span class="min-w-0 flex-1">
              <span class="block font-bold">{{ s.name }}</span>
              <span class="block text-sm text-muted-foreground">{{ s.tagline }} With {{ cap(s.anchor) }} and {{ cap(s.cohost) }}.</span>
            </span>
          </li>
        </ol>
      </section>
    </div>
  </main>
</template>
