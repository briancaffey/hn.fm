<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '#components'

/**
 * The station's player: one audio element with the controls a programme
 * needs and a browser's default player lacks. Chapter marks sit on the
 * bar, so the shape of the edition can be seen before it is heard.
 */
const props = withDefaults(defineProps<{
  src: string
  /** Total length in seconds, if known before the file loads. */
  seconds?: number | null
  /** Where each spoken chapter starts, in seconds. */
  marks?: { at: number, title: string }[]
  /** No seeking, no speed: a live stream. */
  live?: boolean
  compact?: boolean
}>(), { seconds: null, marks: () => [], live: false, compact: false })

const emit = defineEmits<{ time: [seconds: number], playing: [on: boolean] }>()

const audio = ref<HTMLAudioElement | null>(null)
const playing = ref(false)
const waiting = ref(false)
const now = ref(0)
const length = ref(props.seconds || 0)
const rate = ref(1)
const RATES = [1, 1.25, 1.5, 0.85]

watch(() => props.seconds, (s) => { if (s && !length.value) length.value = s })
watch(() => props.src, () => { playing.value = false; now.value = 0 })

function toggle() {
  const a = audio.value
  if (!a) return
  if (a.paused) { waiting.value = true; a.play().catch(() => { waiting.value = false }) }
  else a.pause()
}
function seek(t: number, play = true) {
  const a = audio.value
  if (!a || props.live) return
  a.currentTime = Math.max(0, Math.min(t, length.value || t))
  now.value = a.currentTime
  if (play && a.paused) toggle()
}
function onBar(e: MouseEvent) {
  if (props.live || !length.value) return
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect()
  seek(((e.clientX - r.left) / r.width) * length.value)
}
function nextRate() {
  rate.value = RATES[(RATES.indexOf(rate.value) + 1) % RATES.length] || 1
  if (audio.value) audio.value.playbackRate = rate.value
}
function onKey(e: KeyboardEvent) {
  if (e.key === ' ' || e.key === 'k') { e.preventDefault(); toggle() }
  else if (e.key === 'ArrowRight') seek(now.value + 15, false)
  else if (e.key === 'ArrowLeft') seek(now.value - 15, false)
}
const clock = (s: number) => {
  s = Math.max(0, Math.floor(s))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return (h ? `${h}:${String(m).padStart(2, '0')}` : `${m}`) + `:${String(s % 60).padStart(2, '0')}`
}
const done = computed(() => (length.value ? Math.min(100, (now.value / length.value) * 100) : 0))

defineExpose({ seek, toggle })
onBeforeUnmount(() => audio.value?.pause())
</script>

<template>
  <div
    class="flex items-center gap-3 rounded-full border bg-background/70 py-1.5 pl-1.5 pr-4 backdrop-blur"
    :class="compact ? 'text-xs' : 'text-sm'" role="group" aria-label="Player" tabindex="0" @keydown="onKey"
  >
    <audio
      ref="audio" :src="src" preload="none"
      @play="playing = true; waiting = false; emit('playing', true)"
      @pause="playing = false; emit('playing', false)"
      @waiting="waiting = true" @playing="waiting = false"
      @timeupdate="now = audio?.currentTime || 0; emit('time', now)"
      @loadedmetadata="length = Number.isFinite(audio?.duration) ? (audio?.duration || length) : length"
    />
    <button
      type="button" :aria-label="playing ? 'Pause' : 'Play'"
      class="grid shrink-0 place-items-center rounded-full bg-primary text-primary-foreground transition-transform hover:scale-105 active:scale-95"
      :class="compact ? 'h-9 w-9' : 'h-11 w-11'" @click="toggle"
    >
      <Icon v-if="waiting" name="lucide:loader-circle" class="h-5 w-5 animate-spin" />
      <Icon v-else :name="playing ? 'lucide:pause' : 'lucide:play'" class="h-5 w-5" />
    </button>

    <template v-if="live">
      <span class="flex min-w-0 flex-1 items-center gap-2 text-muted-foreground">
        <span class="h-2 w-2 shrink-0 rounded-full" :class="playing ? 'animate-pulse bg-destructive' : 'bg-muted-foreground/50'" />
        <span class="truncate"><slot>Live stream</slot></span>
      </span>
    </template>
    <template v-else>
      <span class="w-10 shrink-0 text-right font-mono text-xs tabular-nums text-muted-foreground">{{ clock(now) }}</span>
      <div
        class="relative h-6 min-w-0 flex-1 cursor-pointer" role="slider" aria-label="Position"
        :aria-valuemin="0" :aria-valuemax="Math.round(length)" :aria-valuenow="Math.round(now)" @click="onBar"
      >
        <div class="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 overflow-hidden rounded-full bg-muted">
          <div class="h-full bg-primary" :style="{ width: `${done}%` }" />
        </div>
        <span
          v-for="m in (length ? marks : [])" :key="m.at" :title="m.title"
          class="absolute top-1/2 h-2.5 w-px -translate-y-1/2 bg-foreground/40"
          :style="{ left: `${(m.at / length) * 100}%` }"
        />
      </div>
      <span class="w-10 shrink-0 font-mono text-xs tabular-nums text-muted-foreground">{{ length ? clock(length) : '' }}</span>
      <button
        v-if="!compact" type="button" class="shrink-0 rounded-md border px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground hover:text-foreground"
        :aria-label="`Speed ${rate}`" @click="nextRate"
      >{{ rate }}×</button>
    </template>
  </div>
</template>
