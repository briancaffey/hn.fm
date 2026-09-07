<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '#components'

/**
 * A photograph of the page a story links to.
 *
 * The API captures lazily: a cold item answers 404 and queues the shot, so
 * this asks again a couple of times and then gives up. Giving up matters — a
 * self-post has no external page and a dead domain never will, and a component
 * that retried forever would keep a triage list of fifty cards polling.
 *
 * The placeholder is the domain rather than a spinner: it is the useful thing
 * to know when there is no picture, and it does not imply something is coming.
 */
const props = withDefaults(defineProps<{
  itemId: number
  url?: string | null
  /** Attempts after the first miss. Each one is a capture already in flight. */
  retries?: number
  /**
   * Ask the API to capture what it does not have. Off for long lists: the
   * stories table shows everything ingested, and a page of fifty would queue
   * fifty captures at eight seconds each for rows nobody looked at. Those
   * show whatever is already cached and nothing more.
   */
  capture?: boolean
  /** Too small for a caption. Below about 80px the domain does not fit. */
  compact?: boolean
}>(), { url: null, retries: 2, capture: true, compact: false })

const config = useRuntimeConfig()
const src = computed(() =>
  `${config.public.apiBase}/api/hn/items/${props.itemId}/thumbnail`
  + (props.capture ? '' : '?cached=1'))

const state = ref<'loading' | 'ready' | 'none'>('loading')
const bust = ref(0)
const attempts = ref(0)
let timer: ReturnType<typeof setTimeout> | undefined

const host = computed(() => {
  if (!props.url) return ''
  try {
    return new URL(props.url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
})

function onError() {
  // Nothing was queued, so waiting five seconds and asking again would get
  // the same 404.
  if (!props.capture || attempts.value >= props.retries) {
    state.value = 'none'
    return
  }
  attempts.value += 1
  // Long enough for the queued capture to finish — two chromium launches,
  // measured at three to four seconds.
  timer = setTimeout(() => { bust.value += 1 }, 5000)
}

watch(() => props.itemId, () => {
  state.value = 'loading'
  attempts.value = 0
  bust.value = 0
})

onBeforeUnmount(() => { if (timer) clearTimeout(timer) })
</script>

<template>
  <a
    v-if="url"
    :href="url"
    target="_blank"
    rel="noopener noreferrer"
    class="group relative block overflow-hidden rounded-md border bg-muted"
    :title="url"
    @click.stop
  >
    <!-- The placeholder sits underneath rather than replacing the image, and
         the image fades in over it. Hiding the image until it loads is a
         deadlock with `loading="lazy"`: a display:none image never enters the
         viewport, so it never loads, so the load event that would reveal it
         never fires. Opacity keeps it in the layout and in the load path. -->
    <img
      :key="bust"
      :src="bust ? `${src}${src.includes('?') ? '&' : '?'}r=${bust}` : src"
      alt=""
      loading="lazy"
      decoding="async"
      class="absolute inset-0 h-full w-full object-cover object-top transition-all duration-300 group-hover:scale-[1.02]"
      :class="state === 'ready' ? 'opacity-100' : 'opacity-0'"
      @load="state = 'ready'"
      @error="onError"
    >
    <div
      v-if="state !== 'ready'"
      class="flex h-full w-full flex-col items-center justify-center gap-1 px-2 text-center"
    >
      <Icon
        :name="state === 'loading' ? 'lucide:image' : 'lucide:link'"
        class="text-muted-foreground/50"
        :class="compact ? 'h-3.5 w-3.5' : 'h-4 w-4'"
      />
      <span
        v-if="!compact"
        class="line-clamp-2 text-[10px] leading-tight text-muted-foreground"
      >
        {{ host }}
      </span>
    </div>
  </a>
</template>
