<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Icon } from '#components'

/**
 * The browser default player is a black pill that ignores the page entirely
 * and gives no sense of where you are in a twelve-minute episode. This one is
 * token-styled, shows a real waveform-ish progress bar you can scrub, and
 * exposes the two controls that actually matter for reviewing generated
 * narration: skip back ten seconds, and play it faster.
 */
withDefaults(defineProps<{
  src: string
  label?: string
  /** Optional per-section marks, so you can jump to the part you are judging. */
  marks?: Array<{ at: number, label: string }>
  compact?: boolean
}>(), { label: undefined, marks: () => [], compact: false })

const audio = ref<HTMLAudioElement | null>(null)
const playing = ref(false)
const current = ref(0)
const duration = ref(0)
const rate = ref(1)
const ready = ref(false)

const RATES = [1, 1.25, 1.5, 2]

function fmt(s: number) {
  if (!Number.isFinite(s)) return '0:00'
  const m = Math.floor(s / 60)
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}

const pct = computed(() => duration.value ? (current.value / duration.value) * 100 : 0)

function toggle() {
  const el = audio.value
  if (!el) return
  if (el.paused) { el.play(); playing.value = true }
  else { el.pause(); playing.value = false }
}
function seekTo(e: MouseEvent) {
  const el = audio.value
  if (!el || !duration.value) return
  const bar = e.currentTarget as HTMLElement
  const r = bar.getBoundingClientRect()
  el.currentTime = ((e.clientX - r.left) / r.width) * duration.value
}
function nudge(by: number) {
  const el = audio.value
  if (el) el.currentTime = Math.max(0, Math.min(duration.value, el.currentTime + by))
}
function cycleRate() {
  rate.value = RATES[(RATES.indexOf(rate.value) + 1) % RATES.length]!
}
function jump(at: number) {
  const el = audio.value
  if (!el) return
  el.currentTime = at
  if (el.paused) { el.play(); playing.value = true }
}

watch(rate, r => { if (audio.value) audio.value.playbackRate = r })
onUnmounted(() => audio.value?.pause())
</script>

<template>
  <div class="rounded-lg border bg-card p-3">
    <audio
      ref="audio"
      :src="src"
      preload="metadata"
      class="hidden"
      @loadedmetadata="duration = ($event.target as HTMLAudioElement).duration; ready = true"
      @timeupdate="current = ($event.target as HTMLAudioElement).currentTime"
      @ended="playing = false"
      @pause="playing = false"
      @play="playing = true"
    />

    <div class="flex items-center gap-3">
      <button
        type="button"
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-transform hover:scale-105 disabled:opacity-50"
        :disabled="!ready"
        :aria-label="playing ? 'Pause' : 'Play'"
        @click="toggle"
      >
        <Icon :name="playing ? 'lucide:pause' : 'lucide:play'" class="h-4 w-4" />
      </button>

      <div class="min-w-0 flex-1">
        <p v-if="label && !compact" class="mb-1 truncate text-xs font-medium">{{ label }}</p>
        <!-- Scrub bar. A plain <input type=range> cannot show section marks. -->
        <div
          class="group relative h-2 cursor-pointer rounded-full bg-muted"
          role="slider"
          :aria-valuenow="Math.round(current)"
          :aria-valuemin="0"
          :aria-valuemax="Math.round(duration) || 0"
          aria-label="Seek"
          tabindex="0"
          @click="seekTo"
          @keydown.left.prevent="nudge(-5)"
          @keydown.right.prevent="nudge(5)"
        >
          <div class="h-2 rounded-full bg-primary transition-[width]" :style="{ width: `${pct}%` }" />
          <span
            v-for="m in marks"
            :key="m.at"
            class="absolute top-1/2 h-3 w-px -translate-y-1/2 bg-foreground/25"
            :style="{ left: duration ? `${(m.at / duration) * 100}%` : '0%' }"
            :title="m.label"
          />
        </div>
        <div class="mt-1 flex items-center justify-between text-[11px] tabular-nums text-muted-foreground">
          <span>{{ fmt(current) }}</span>
          <span>{{ fmt(duration) }}</span>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-1">
        <button
          type="button" class="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Back ten seconds" @click="nudge(-10)"
        >
          <Icon name="lucide:rotate-ccw" class="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          class="min-w-[2.6rem] rounded px-1.5 py-1 text-[11px] font-medium tabular-nums text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Playback speed" @click="cycleRate"
        >{{ rate }}&times;</button>
        <a
          :href="src" download
          class="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Download audio"
        ><Icon name="lucide:download" class="h-3.5 w-3.5" /></a>
      </div>
    </div>

    <div v-if="marks.length && !compact" class="mt-2 flex flex-wrap gap-1">
      <button
        v-for="m in marks" :key="`j-${m.at}`" type="button"
        class="rounded border px-1.5 py-0.5 text-[11px] text-muted-foreground hover:border-primary hover:text-primary"
        @click="jump(m.at)"
      >{{ m.label }}</button>
    </div>
  </div>
</template>
