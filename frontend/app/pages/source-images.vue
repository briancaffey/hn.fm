<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '#components'
import { Button } from '~/components/ui/button'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import EmptyState from '~/components/kit/EmptyState.vue'
import LoadingRows from '~/components/kit/LoadingRows.vue'
import InfoHint from '~/components/kit/InfoHint.vue'
import StatTile from '~/components/kit/StatTile.vue'

/**
 * The article's own pictures (plans/18): what the page served, what we
 * kept, what the vision model made of each, and what looking at it cost.
 */
useHead({ title: 'hn.fm · Source images' })

interface Restyle {
  id: number
  style_key: string | null
  style_label: string | null
  prompt: string
  path: string | null
  seconds: number | null
  created_at: string | null
}

interface SrcImg {
  id: number
  item_id: number
  run: number
  index: number
  created_at: string | null
  title: string | null
  url: string
  alt: string | null
  origin: string | null
  content_type: string | null
  width: number | null
  height: number | null
  bytes: number | null
  stored_width: number | null
  stored_height: number | null
  stored_bytes: number | null
  resized: boolean
  description: string | null
  kind: string | null
  subjects: string[]
  text_in_image: string | null
  interest: number | null
  usable: boolean | null
  use_hint: string | null
  caveat: string | null
  analysis_model: string | null
  tokens_in: number | null
  tokens_out: number | null
  analysis_seconds: number | null
  analyzed_at: string | null
  analysis_error: string | null
  restyles: Restyle[]
}

interface Facets {
  kinds: Record<string, number>
  usable: number
  tokens_in: number
  tokens_out: number
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const images = ref<SrcImg[]>([])
const facets = ref<Facets>({ kinds: {}, usable: 0, tokens_in: 0, tokens_out: 0 })
const total = ref(0)
const enabled = ref(true)
const loading = ref(true)
const kind = ref<string | null>(null)
const usableOnly = ref(false)
const sort = ref('recent')
const offset = ref(0)
const LIMIT = 48
const open = ref<SrcImg | null>(null)
const restyling = ref(false)
const message = ref('')
const restyleTheme = ref('')

const SORTS = [
  { key: 'recent', label: 'Newest' },
  { key: 'oldest', label: 'Oldest' },
  { key: 'interest', label: 'Most interesting' },
  { key: 'largest', label: 'Largest served' },
  { key: 'tokens', label: 'Most tokens' },
]

/** Mirrors content/art_direction.py THEMES; the API accepts any key. */
const THEMES = [
  ['', 'Random theme'],
  ['synthwave', 'Neon Synthwave'], ['risograph', 'Risograph Print'],
  ['watercolor', 'Editorial Watercolor'], ['isometric', 'Isometric Low-Poly 3D'],
  ['noir', 'Ink Noir Comic'], ['blueprint', 'Technical Blueprint'],
  ['claymation', 'Claymation Diorama'], ['vaporwave', 'Surreal Vaporwave Collage'],
  ['papercut', 'Layered Papercut'], ['oilpaint', 'Dramatic Oil Painting'],
  ['pixelart', 'Retro Pixel Art'], ['infographic', 'Bold Flat Infographic'],
]

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams({ sort: sort.value, offset: String(offset.value), limit: String(LIMIT) })
    if (kind.value) params.set('kind', kind.value)
    if (usableOnly.value) params.set('usable', 'true')
    const res = await $fetch<{ images: SrcImg[], facets: Facets, enabled: boolean, pagination: { total: number } }>(
      `${apiBase}/api/source-images?${params}`)
    images.value = res.images
    facets.value = res.facets
    enabled.value = res.enabled
    total.value = res.pagination.total
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch([kind, sort, usableOnly], () => { offset.value = 0; load() })

const kinds = computed(() => Object.entries(facets.value.kinds || {}))
const shown = computed(() => `${offset.value + 1}–${Math.min(offset.value + images.value.length, total.value)} of ${total.value}`)

const src = (i: SrcImg) => `${apiBase}/api/source-images/${i.id}/file`
const restyleSrc = (i: SrcImg, r: Restyle) =>
  r.path ? `${apiBase}/api/source-images/${i.id}/restyles/${r.path.split('/').pop()}` : ''

const kb = (n: number | null) => n == null ? '—' : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`
const dims = (w: number | null, h: number | null) => w && h ? `${w}×${h}` : '—'
const tokens = (i: SrcImg) => (i.tokens_in ?? 0) + (i.tokens_out ?? 0)
const fmt = (n: number) => n.toLocaleString()

async function restyle(i: SrcImg) {
  restyling.value = true
  message.value = 'Asking flux to re-render it… about half a minute.'
  try {
    const res = await $fetch<{ theme: string, seconds: number }>(
      `${apiBase}/api/source-images/${i.id}/restyle`,
      { method: 'POST', body: { theme: restyleTheme.value || null } })
    message.value = `Restyled as ${res.theme} in ${res.seconds}s.`
    await load()
    open.value = images.value.find(x => x.id === i.id) || null
  } catch (e: unknown) {
    message.value = `Restyle failed: ${e}`
  } finally {
    restyling.value = false
  }
}

async function recollect(i: SrcImg) {
  message.value = 'Queued a fresh collection for this run. Refresh in a minute.'
  try {
    await $fetch(`${apiBase}/api/hn/items/${i.item_id}/runs/${i.run}/source-images`,
      { method: 'POST', body: { force: true } })
  } catch (e: unknown) {
    message.value = `Could not queue: ${e}`
  }
}
</script>

<template>
  <PageShell>
    <PageHeader
      title="Source images"
      subtitle="The pictures on the page each story links to, downscaled, looked at, and ready for a video."
      hint="Real images from the article — the chart, the board, the screenshot — often tell the story better than a generated scene. Each one is stored at a sane size, described by the vision model, and scored for whether a video could use it. The image builder can then show it as-is or have flux re-render it in the take's art style."
      :meta="loading ? [] : [shown]"
    >
      <template #actions>
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </template>
      <template #below>
        <div class="mt-3 grid gap-3 sm:grid-cols-3">
          <StatTile label="Usable in a video" :value="fmt(facets.usable)" :hint="`of ${fmt(total)} collected`" />
          <StatTile label="Vision tokens in" :value="fmt(facets.tokens_in)" hint="prompt side, all images" />
          <StatTile label="Vision tokens out" :value="fmt(facets.tokens_out)" hint="the analyses themselves" />
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <div class="flex flex-wrap items-center gap-1">
            <button
              type="button"
              class="rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
              :class="!kind ? 'border-primary bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'"
              @click="kind = null"
            >All</button>
            <button
              v-for="[k, n] in kinds" :key="k" type="button"
              class="rounded-full border px-2.5 py-1 text-xs font-medium capitalize transition-colors"
              :class="kind === k ? 'border-primary bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted'"
              @click="kind = k"
            >{{ k }} ({{ n }})</button>
          </div>
          <label class="flex items-center gap-1.5 text-xs">
            <input v-model="usableOnly" type="checkbox" class="h-3.5 w-3.5">
            Usable only
          </label>
          <div class="ml-auto flex items-center gap-1.5">
            <span class="text-xs text-muted-foreground">Sort</span>
            <select v-model="sort" class="h-7 rounded-md border bg-card px-2 text-xs" aria-label="Sort images">
              <option v-for="s in SORTS" :key="s.key" :value="s.key">{{ s.label }}</option>
            </select>
          </div>
        </div>
        <p v-if="!enabled" class="mt-2 text-xs text-destructive">
          Collection is switched off (SOURCE_IMAGES_ENABLED). Nothing new will arrive until it is on.
        </p>
        <p v-if="message" class="mt-2 text-xs text-muted-foreground">{{ message }}</p>
      </template>
    </PageHeader>

    <LoadingRows v-if="loading && !images.length" :rows="6" height="h-40" />

    <EmptyState
      v-else-if="!images.length"
      icon="lucide:images"
      title="No source images yet"
      body="They are collected when a story passes triage. Score a story, or open one and ask for its images."
    />

    <template v-else>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <button
          v-for="i in images" :key="i.id" type="button"
          class="group overflow-hidden rounded-lg border bg-card text-left transition-colors hover:border-primary/50"
          @click="open = i"
        >
          <div class="relative">
            <img :src="src(i)" :alt="i.alt || i.description || ''" loading="lazy" class="aspect-[3/2] w-full bg-muted object-cover">
            <span
              v-if="i.usable != null"
              class="absolute left-2 top-2 rounded px-1.5 py-0.5 text-[10px] font-medium"
              :class="i.usable ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'"
            >{{ i.usable ? `usable · ${i.interest}` : 'not usable' }}</span>
            <span v-if="i.restyles.length" class="absolute right-2 top-2 rounded bg-card/90 px-1.5 py-0.5 text-[10px]">
              {{ i.restyles.length }} restyle{{ i.restyles.length > 1 ? 's' : '' }}
            </span>
          </div>
          <div class="p-2.5">
            <div class="flex items-center justify-between gap-2">
              <span class="truncate text-xs font-medium">{{ i.title || `Item ${i.item_id}` }}</span>
              <span v-if="i.kind" class="shrink-0 rounded border px-1 py-0.5 text-[10px] capitalize text-muted-foreground">{{ i.kind }}</span>
            </div>
            <p class="mt-1 line-clamp-2 text-[11px] leading-snug text-muted-foreground">
              {{ i.description || i.analysis_error || 'Not analysed yet.' }}
            </p>
            <p class="mt-1.5 font-mono text-[10px] text-muted-foreground">
              {{ dims(i.width, i.height) }} · {{ kb(i.bytes) }}
              <template v-if="i.resized"> → {{ dims(i.stored_width, i.stored_height) }} · {{ kb(i.stored_bytes) }}</template>
              <template v-if="tokens(i)"> · {{ fmt(tokens(i)) }} tok</template>
            </p>
          </div>
        </button>
      </div>

      <div class="mt-5 flex items-center justify-between">
        <Button variant="outline" size="sm" :disabled="offset === 0" @click="offset = Math.max(0, offset - LIMIT); load()">Previous</Button>
        <span class="text-xs text-muted-foreground">{{ shown }}</span>
        <Button variant="outline" size="sm" :disabled="offset + LIMIT >= total" @click="offset += LIMIT; load()">Next</Button>
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
            <h2 class="truncate text-base font-semibold">{{ open.title || `Item ${open.item_id}` }}</h2>
            <p class="mt-0.5 truncate text-xs text-muted-foreground">
              <a :href="open.url" target="_blank" rel="noopener" class="hover:underline">{{ open.url }}</a>
            </p>
          </div>
          <button type="button" class="rounded p-1 text-muted-foreground hover:bg-muted" aria-label="Close" @click="open = null">
            <Icon name="lucide:x" class="h-4 w-4" />
          </button>
        </div>
        <img :src="src(open)" :alt="open.alt || ''" class="w-full bg-muted">
        <div class="space-y-4 p-4">
          <div>
            <div class="mb-1 flex items-center gap-1.5">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">What the vision model saw</p>
              <InfoHint text="One structured call per image on the omni route. Interest is how much it would add to a video about this story; usable is whether it could fill a frame at all." />
            </div>
            <p v-if="open.description" class="rounded border-l-2 border-primary bg-muted/60 p-2.5 text-sm leading-relaxed">{{ open.description }}</p>
            <p v-else-if="open.analysis_error" class="rounded border-l-2 border-destructive bg-muted/60 p-2.5 font-mono text-xs">{{ open.analysis_error }}</p>
            <p v-else class="text-xs text-muted-foreground">Not analysed.</p>
            <p v-if="open.use_hint" class="mt-2 text-xs"><span class="font-medium">How to use it:</span> {{ open.use_hint }}</p>
            <p v-if="open.caveat" class="mt-1 text-xs text-destructive"><span class="font-medium">Caveat:</span> {{ open.caveat }}</p>
            <p v-if="open.text_in_image" class="mt-1 font-mono text-xs text-muted-foreground">Text: “{{ open.text_in_image }}”</p>
            <p v-if="open.subjects?.length" class="mt-1 text-xs text-muted-foreground">{{ open.subjects.join(' · ') }}</p>
          </div>
          <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
            <div><dt class="text-muted-foreground">Served</dt><dd class="font-mono">{{ dims(open.width, open.height) }} · {{ kb(open.bytes) }}</dd></div>
            <div><dt class="text-muted-foreground">Stored</dt><dd class="font-mono">{{ dims(open.stored_width, open.stored_height) }} · {{ kb(open.stored_bytes) }}<span v-if="open.resized"> (resized)</span></dd></div>
            <div><dt class="text-muted-foreground">Kind</dt><dd class="capitalize">{{ open.kind || '—' }}</dd></div>
            <div><dt class="text-muted-foreground">Interest</dt><dd class="font-mono">{{ open.interest ?? '—' }}</dd></div>
            <div><dt class="text-muted-foreground">Tokens in / out</dt><dd class="font-mono">{{ open.tokens_in ?? '—' }} / {{ open.tokens_out ?? '—' }}</dd></div>
            <div><dt class="text-muted-foreground">Model</dt><dd class="truncate font-mono">{{ open.analysis_model || '—' }}</dd></div>
            <div><dt class="text-muted-foreground">Analysis</dt><dd class="font-mono">{{ open.analysis_seconds ? `${open.analysis_seconds}s` : '—' }}</dd></div>
            <div><dt class="text-muted-foreground">Found as</dt><dd class="font-mono">{{ open.origin || '—' }}<span v-if="open.content_type"> · {{ open.content_type }}</span></dd></div>
            <div><dt class="text-muted-foreground">Story</dt>
              <dd><NuxtLink :to="`/hn/item/${open.item_id}`" class="text-primary hover:underline">{{ open.item_id }}</NuxtLink> · run {{ open.run }}</dd></div>
            <div v-if="open.alt" class="col-span-2"><dt class="text-muted-foreground">Alt text</dt><dd class="truncate">{{ open.alt }}</dd></div>
          </dl>

          <div>
            <div class="mb-1 flex items-center gap-1.5">
              <p class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Restyles</p>
              <InfoHint text="flux re-renders the picture in a take's art style, keeping the subject and composition. This is what the image builder does when it casts a photo into a section." />
            </div>
            <div v-if="open.restyles.length" class="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <figure v-for="r in open.restyles" :key="r.id" class="overflow-hidden rounded border">
                <img :src="restyleSrc(open, r)" :alt="r.style_label || ''" class="aspect-video w-full bg-muted object-cover">
                <figcaption class="p-1.5 text-[10px] text-muted-foreground">{{ r.style_label }} · {{ r.seconds }}s</figcaption>
              </figure>
            </div>
            <p v-else class="text-xs text-muted-foreground">None yet.</p>
            <div class="mt-2 flex flex-wrap items-center gap-2">
              <select v-model="restyleTheme" class="h-8 rounded-md border bg-card px-2 text-xs" aria-label="Theme">
                <option v-for="[k, l] in THEMES" :key="k" :value="k">{{ l }}</option>
              </select>
              <Button size="sm" :disabled="restyling" @click="restyle(open)">
                {{ restyling ? 'Rendering…' : 'Restyle with flux' }}
              </Button>
              <Button size="sm" variant="outline" @click="recollect(open)">Re-collect this run</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </PageShell>
</template>
