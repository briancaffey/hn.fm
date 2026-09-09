<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Icon } from '#components'
import { Button } from '~/components/ui/button'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import EmptyState from '~/components/kit/EmptyState.vue'
import LoadingRows from '~/components/kit/LoadingRows.vue'

/**
 * Every image the pipeline has produced, with the prompt that produced it.
 *
 * The prompt is the point. A good picture whose prompt is lost is a picture
 * you cannot make again, and until now digest art recorded nothing at all
 * while segment art was reachable only through the segment that owned it.
 */
useHead({ title: 'hn.fm · Images' })

interface Img {
  id: number
  kind: string
  created_at: string
  item_id: number | null
  run: number | null
  seg: number | null
  slug: string | null
  title: string | null
  prompt: string
  style_key: string | null
  style_label: string | null
  technique: string | null
  model: string | null
  width: number | null
  height: number | null
  ink: number | null
  seconds: number | null
  path: string | null
  thumb: string | null
  /** Server-derived; the page must not rebuild this from item/run/seg. */
  url: string | null
  source_image_id: number | null
  /** Where the picture was used — the segment page or the edition's HTML. */
  link: { href: string, label: string, external: boolean } | null
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const images = ref<Img[]>([])
const facets = ref<{ kinds: Record<string, number>, styles: Record<string, number> }>({ kinds: {}, styles: {} })
const total = ref(0)
const loading = ref(true)
const kind = ref<string | null>(null)
const sort = ref('recent')
const offset = ref(0)
const LIMIT = 48
const open = ref<Img | null>(null)
const promptOpen = ref(false)

/** Lightbox navigation across the loaded page: ← → keys and the arrows. */
const openIndex = computed(() => open.value ? images.value.findIndex(i => i.id === open.value!.id) : -1)
function show(i: Img | null) {
  open.value = i
  promptOpen.value = false
}
function step(delta: number) {
  if (openIndex.value < 0) return
  const next = images.value[openIndex.value + delta]
  if (next) show(next)
}
function onKey(e: KeyboardEvent) {
  if (!open.value) return
  if (e.key === 'Escape') show(null)
  else if (e.key === 'ArrowRight') step(1)
  else if (e.key === 'ArrowLeft') step(-1)
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
function linkHref(l: NonNullable<Img['link']>) {
  return l.external ? `${apiBase}${l.href}` : l.href
}

const SORTS = [
  { key: 'recent', label: 'Newest' },
  { key: 'oldest', label: 'Oldest' },
  { key: 'ink', label: 'Most ink' },
  { key: 'ink_asc', label: 'Least ink' },
  { key: 'slowest', label: 'Slowest' },
  { key: 'style', label: 'By style' },
]

const KIND_HINT: Record<string, string> = {
  digest: 'Inline illustrations inside a Kindle edition. Greyscale line art, sized for a 6" screen.',
  cover: 'The plate on the front of an edition. Heavier line weight so it survives a thumbnail.',
  segment: 'Scenes for a video, one per script section, in that take’s art-direction theme.',
  restyle: 'A real picture from the article, re-rendered by flux in a take’s theme. Its source is on the Source images page.',
}

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      sort: sort.value, offset: String(offset.value), limit: String(LIMIT),
    })
    if (kind.value) params.set('kind', kind.value)
    const res = await $fetch<{ images: Img[], facets: typeof facets.value, pagination: { total: number } }>(
      `${apiBase}/api/images/catalog?${params}`)
    images.value = res.images
    facets.value = res.facets
    total.value = res.pagination.total
  } catch {
    images.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch([kind, sort], () => { offset.value = 0; load() })

const kinds = computed(() => Object.entries(facets.value.kinds || {}))
const shown = computed(() => `${offset.value + 1}–${Math.min(offset.value + images.value.length, total.value)} of ${total.value}`)

function src(i: Img) {
  if (i.thumb) return i.thumb
  // The API derives this from the recorded path. Rebuilding it here put the
  // segment number where the section index goes, so every entry of a take
  // showed its first section's picture.
  if (i.url) return i.url.startsWith('/') ? `${apiBase}${i.url}` : i.url
  return ''
}
function copyPrompt(text: string) {
  navigator.clipboard?.writeText(text)
}
</script>

<template>
  <PageShell>
    <PageHeader
      title="Image catalogue"
      subtitle="Every image the pipeline has drawn, with the prompt that drew it."
      hint="Digest illustrations, edition covers and video scenes in one place. The prompt is kept because a good picture whose prompt is lost is a picture you cannot make again — digest art used to record nothing at all, and segment art was reachable only through its own segment."
      :meta="loading ? [] : [shown]"
    >
      <template #actions>
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </template>
      <template #below>
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <div class="flex flex-wrap items-center gap-1">
            <button
              type="button"
              class="rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
              :class="!kind ? 'border-primary bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'"
              @click="kind = null"
            >All {{ total ? `(${total})` : '' }}</button>
            <button
              v-for="[k, n] in kinds" :key="k" type="button"
              :title="KIND_HINT[k]"
              class="rounded-full border px-2.5 py-1 text-xs font-medium capitalize transition-colors"
              :class="kind === k ? 'border-primary bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'"
              @click="kind = k"
            >{{ k }} ({{ n }})</button>
          </div>
          <div class="ml-auto flex items-center gap-1.5">
            <span class="text-xs text-muted-foreground">Sort</span>
            <select
              v-model="sort"
              class="h-7 rounded-md border bg-card px-2 text-xs"
              aria-label="Sort images"
            >
              <option v-for="s in SORTS" :key="s.key" :value="s.key">{{ s.label }}</option>
            </select>
          </div>
        </div>
        <p v-if="kind && KIND_HINT[kind]" class="mt-2 text-xs text-muted-foreground">
          {{ KIND_HINT[kind] }}
        </p>
      </template>
    </PageHeader>

    <LoadingRows v-if="loading && !images.length" :rows="6" height="h-40" />

    <EmptyState
      v-else-if="!images.length"
      icon="lucide:image"
      title="No images yet"
      body="Illustrated digests and video segments both add to this catalogue. Build one with images and it will appear here."
    />

    <template v-else>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <button
          v-for="i in images" :key="i.id" type="button"
          class="group overflow-hidden rounded-lg border bg-card text-left transition-colors hover:border-primary/50"
          @click="show(i)"
        >
          <img
            v-if="src(i)" :src="src(i)" :alt="i.style_label || i.kind" loading="lazy"
            class="aspect-[3/2] w-full bg-muted object-cover"
          >
          <div v-else class="flex aspect-[3/2] items-center justify-center bg-muted">
            <Icon name="lucide:image-off" class="h-6 w-6 text-muted-foreground/50" />
          </div>
          <div class="p-2.5">
            <div class="flex items-center justify-between gap-2">
              <span class="truncate text-xs font-medium">{{ i.style_label || '—' }}</span>
              <span class="shrink-0 rounded border px-1 py-0.5 text-[10px] capitalize text-muted-foreground">{{ i.kind }}</span>
            </div>
            <p class="mt-1 line-clamp-2 font-mono text-[11px] leading-snug text-muted-foreground">{{ i.prompt }}</p>
          </div>
        </button>
      </div>

      <div class="mt-5 flex items-center justify-between">
        <Button
          variant="outline" size="sm" :disabled="offset === 0"
          @click="offset = Math.max(0, offset - LIMIT); load()"
        >Previous</Button>
        <span class="text-xs text-muted-foreground">{{ shown }}</span>
        <Button
          variant="outline" size="sm" :disabled="offset + LIMIT >= total"
          @click="offset += LIMIT; load()"
        >Next</Button>
      </div>
    </template>

    <!-- Lightbox: the picture large on a dark ground, one compact strip of
         facts beneath it. Nothing scrolls — a long prompt folds behind a
         toggle rather than pushing the image off the screen. -->
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/85 p-4 sm:p-8"
      role="dialog" aria-modal="true"
      @click.self="show(null)"
    >
      <button
        type="button" class="absolute right-4 top-4 rounded-full bg-black/40 p-2 text-white/80 hover:bg-black/60 hover:text-white"
        aria-label="Close" @click="show(null)"
      ><Icon name="lucide:x" class="h-5 w-5" /></button>
      <button
        v-if="openIndex > 0" type="button"
        class="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white/80 hover:bg-black/60 hover:text-white sm:left-4"
        aria-label="Previous image" @click.stop="step(-1)"
      ><Icon name="lucide:chevron-left" class="h-6 w-6" /></button>
      <button
        v-if="openIndex >= 0 && openIndex < images.length - 1" type="button"
        class="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-2 text-white/80 hover:bg-black/60 hover:text-white sm:right-4"
        aria-label="Next image" @click.stop="step(1)"
      ><Icon name="lucide:chevron-right" class="h-6 w-6" /></button>

      <img
        v-if="src(open)" :src="src(open)" :alt="open.style_label || open.kind"
        class="max-h-[68vh] max-w-full rounded-md object-contain shadow-[0_30px_80px_-20px_rgba(0,0,0,0.9)] ring-1 ring-white/10"
        @click.stop
      >

      <div class="mt-4 w-full max-w-3xl rounded-lg border border-white/10 bg-card/95 p-3 text-xs shadow-xl backdrop-blur" @click.stop>
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <span class="rounded border px-1.5 py-0.5 text-[10px] capitalize text-muted-foreground">{{ open.kind }}</span>
          <span class="font-medium">{{ open.style_label || '—' }}</span>
          <span v-if="open.technique" class="text-muted-foreground">{{ open.technique }}</span>
          <span class="font-mono text-muted-foreground">{{ open.width }}&times;{{ open.height }}</span>
          <span v-if="open.model" class="font-mono text-muted-foreground">{{ open.model }}</span>
          <span v-if="open.seconds" class="font-mono text-muted-foreground">{{ open.seconds }}s</span>
          <span v-if="open.ink != null" class="font-mono text-muted-foreground">ink {{ open.ink }}</span>
          <span class="text-muted-foreground">{{ new Date(open.created_at).toLocaleString() }}</span>
          <span class="ml-auto flex items-center gap-2">
            <NuxtLink
              v-if="open.item_id" :to="`/hn/item/${open.item_id}`"
              class="text-primary hover:underline"
            >Story {{ open.item_id }}</NuxtLink>
            <NuxtLink
              v-if="open.link && !open.link.external" :to="open.link.href"
              class="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-primary-foreground hover:bg-primary/90"
            ><Icon name="lucide:arrow-up-right" class="h-3.5 w-3.5" />{{ open.link.label }}</NuxtLink>
            <a
              v-else-if="open.link" :href="linkHref(open.link)" target="_blank" rel="noopener"
              class="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-primary-foreground hover:bg-primary/90"
            ><Icon name="lucide:arrow-up-right" class="h-3.5 w-3.5" />{{ open.link.label }}</a>
          </span>
        </div>
        <p v-if="open.title" class="mt-1.5 truncate text-muted-foreground">{{ open.title }}</p>
        <div class="mt-2 flex items-start gap-2">
          <p
            class="min-w-0 flex-1 cursor-pointer font-mono text-[11px] leading-relaxed text-muted-foreground"
            :class="promptOpen ? '' : 'line-clamp-2'"
            :title="promptOpen ? 'Collapse' : 'Show the whole prompt'"
            @click="promptOpen = !promptOpen"
          >{{ open.prompt }}</p>
          <button
            type="button" class="shrink-0 text-primary hover:underline"
            title="Copy the exact string given to the image model"
            @click="copyPrompt(open.prompt)"
          >Copy</button>
        </div>
      </div>
    </div>
  </PageShell>
</template>
