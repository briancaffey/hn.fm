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
}>(), { url: null, retries: 2 })

const config = useRuntimeConfig()
const src = computed(() =>
  `${config.public.apiBase}/api/hn/items/${props.itemId}/thumbnail`)

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
  if (attempts.value >= props.retries) {
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
    <img
      v-show="state === 'ready'"
      :key="bust"
      :src="bust ? `${src}?r=${bust}` : src"
      alt=""
      loading="lazy"
      decoding="async"
      class="h-full w-full object-cover object-top transition-transform group-hover:scale-[1.02]"
      @load="state = 'ready'"
      @error="onError"
    >
    <div
      v-if="state !== 'ready'"
      class="flex h-full w-full flex-col items-center justify-center gap-1 px-2 text-center"
    >
      <Icon
        :name="state === 'loading' ? 'lucide:image' : 'lucide:link'"
        class="h-4 w-4 text-muted-foreground/50"
      />
      <span class="line-clamp-2 text-[10px] leading-tight text-muted-foreground">
        {{ host }}
      </span>
    </div>
  </a>
</template>
