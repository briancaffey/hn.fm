<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '#components'
import { Button } from '~/components/ui/button'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import EmptyState from '~/components/kit/EmptyState.vue'
import LoadingRows from '~/components/kit/LoadingRows.vue'
import InfoHint from '~/components/kit/InfoHint.vue'

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
  if (i.path && i.item_id != null) {
    const file = i.path.split('/').pop()
    return `${apiBase}/api/images/${i.item_id}/${i.run}/${i.seg}/${i.seg}/${file}`
  }
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
          @click="open = i"
        >
          <img
            v-if="src(i)" :src="src(i)" :alt="i.style_label || i.kind" loading="lazy"
            class="aspect-[3/2] w-full bg-muted object-cover"
          />
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

    <!-- Detail -->
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog" aria-modal="true"
      @click.self="open = null"
      @keydown.esc="open = null"
    >
      <div class="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-lg border bg-card shadow-xl">
        <div class="flex items-start justify-between gap-3 border-b p-4">
          <div class="min-w-0">
            <h2 class="text-base font-semibold">{{ open.style_label || open.kind }}</h2>
            <p class="mt-0.5 text-xs text-muted-foreground">{{ open.technique }}</p>
          </div>
          <button
            type="button" class="rounded p-1 text-muted-foreground hover:bg-muted"
            aria-label="Close" @click="open = null"
          ><Icon name="lucide:x" class="h-4 w-4" /></button>
        </div>
        <img v-if="src(open)" :src="src(open)" :alt="open.style_label || ''" class="w-full bg-muted" />
        <div class="space-y-4 p-4">
          <div>
            <div class="mb-1 flex items-center gap-1.5">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Prompt as sent</p>
              <InfoHint text="The exact string given to the image model. Copy it to reuse a look you liked." />
              <button
                type="button" class="ml-auto text-xs text-primary hover:underline"
                @click="copyPrompt(open.prompt)"
              >Copy</button>
            </div>
            <p class="rounded border-l-2 border-primary bg-muted/60 p-2.5 font-mono text-xs leading-relaxed">{{ open.prompt }}</p>
          </div>
          <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
            <div><dt class="text-muted-foreground">Model</dt><dd class="font-mono">{{ open.model || '—' }}</dd></div>
            <div><dt class="text-muted-foreground">Dimensions</dt><dd class="font-mono">{{ open.width }}&times;{{ open.height }}</dd></div>
            <div><dt class="text-muted-foreground">Ink</dt><dd class="font-mono">{{ open.ink ?? '—' }}</dd></div>
            <div><dt class="text-muted-foreground">Render</dt><dd class="font-mono">{{ open.seconds ? `${open.seconds}s` : '—' }}</dd></div>
            <div><dt class="text-muted-foreground">Kind</dt><dd class="capitalize">{{ open.kind }}</dd></div>
            <div><dt class="text-muted-foreground">Created</dt><dd>{{ new Date(open.created_at).toLocaleString() }}</dd></div>
            <div v-if="open.item_id"><dt class="text-muted-foreground">Story</dt>
              <dd><NuxtLink :to="`/hn/item/${open.item_id}`" class="text-primary hover:underline">{{ open.item_id }}</NuxtLink></dd></div>
            <div v-if="open.slug"><dt class="text-muted-foreground">Edition</dt><dd class="truncate">{{ open.slug }}</dd></div>
          </dl>
          <p v-if="open.title" class="text-xs text-muted-foreground">
            <span class="font-medium text-foreground">Subject line:</span> {{ open.title }}
          </p>
        </div>
      </div>
    </div>
  </PageShell>
</template>
