<template>
  <div class="w-full px-4 py-8">
    <div class="mb-6">
      <NuxtLink
        to="/hn/items"
        class="text-primary hover:text-primary/80 font-medium"
      >
        ← Back to Items
      </NuxtLink>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"/>
      <p class="mt-2 text-muted-foreground">Loading item...</p>
    </div>

    <div v-else-if="!!error" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
      {{ error }}
    </div>

    <div v-else-if="!!item" class="space-y-6">
      <!-- Header -->
      <div class="bg-card border rounded-lg p-6">
        <h1 class="text-xl font-semibold leading-tight">
          <a
            v-if="item.url"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="hover:text-primary transition-colors"
          >
            {{ item.title || 'No Title' }}
          </a>
          <span v-else>{{ item.title || 'No Title' }}</span>
        </h1>

        <p v-if="latestShortDescription" class="mt-2 text-muted-foreground">
          {{ latestShortDescription }}
        </p>

        <!-- Compact badge row -->
        <div class="mt-4 flex flex-wrap items-center gap-2">
          <Badge class="bg-primary text-primary-foreground border-primary text-xs">
            ▲ {{ item.score || 0 }} points
          </Badge>
          <Badge variant="outline" class="text-xs">
            by {{ item.by || 'Unknown' }}
          </Badge>
          <Badge variant="outline" class="text-xs">
            {{ itemAge }}
          </Badge>
          <Badge variant="outline" class="text-xs">
            {{ item.descendants || 0 }} comment{{ (item.descendants || 0) !== 1 ? 's' : '' }}
          </Badge>
          <Badge v-if="domain" variant="outline" class="text-xs">
            <a
              :href="item.url"
              target="_blank"
              rel="noopener noreferrer"
              class="hover:text-primary"
            >
              {{ domain }}
            </a>
          </Badge>
          <Badge variant="outline" class="text-xs">
            <a
              :href="`https://news.ycombinator.com/item?id=${item.id}`"
              target="_blank"
              rel="noopener noreferrer"
              class="hover:text-primary"
            >
              HN ↗
            </a>
          </Badge>
        </div>

        <div v-if="item.text" class="mt-4">
          <p class="text-sm text-foreground whitespace-pre-wrap">{{ item.text }}</p>
        </div>
      </div>

      <!-- Action bar -->
      <div class="bg-card border rounded-lg p-4">
        <div class="flex flex-wrap items-center gap-3">
          <div class="flex items-center gap-2">
            <Button
              :disabled="isQueueing"
              variant="default"
              @click="startFullPipeline"
            >
              {{ isQueueing === 'pipeline' ? 'Queueing...' : 'Full Pipeline' }}
            </Button>
            <select
              v-model="aspectFormat"
              class="h-9 rounded-md border bg-background px-2 text-sm text-foreground"
              aria-label="Aspect format"
            >
              <option value="16:9">16:9</option>
              <option value="1:1">1:1</option>
              <option value="9:16">9:16</option>
            </select>
          </div>
          <Button
            :disabled="isQueueing"
            variant="outline"
            @click="startScriptOnlyRun"
          >
            {{ isQueueing === 'script' ? 'Queueing...' : 'New Run (script only)' }}
          </Button>

          <span
            v-if="actionMessage"
            class="text-sm"
            :class="actionMessageIsError ? 'text-destructive' : 'text-ok'"
          >
            {{ actionMessage }}
          </span>
        </div>
      </div>

      <!-- Tabs -->
      <div>
        <div class="flex items-center gap-2 mb-4">
          <Button
            :variant="activeTab === 'generations' ? 'default' : 'outline'"
            size="sm"
            @click="activeTab = 'generations'"
          >
            Generations
            <span v-if="generations.length" class="ml-1.5 text-xs opacity-70">{{ generations.length }}</span>
          </Button>
          <Button
            :variant="activeTab === 'gallery' ? 'default' : 'outline'"
            size="sm"
            @click="activeTab = 'gallery'"
          >
            Gallery
            <span v-if="galleryGenerations.length" class="ml-1.5 text-xs opacity-70">{{ galleryGenerations.length }}</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            :disabled="generationsLoading"
            @click="fetchGenerations"
          >
            <Icon name="lucide:refresh-cw" class="h-4 w-4" :class="{ 'animate-spin': generationsLoading }" />
          </Button>
        </div>

        <div v-if="generationsError" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
          {{ generationsError }}
        </div>

        <div v-if="generationsLoading && generations.length === 0" class="text-center py-8">
          <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto"/>
          <p class="mt-2 text-sm text-muted-foreground">Loading generations...</p>
        </div>

        <!-- Generations tab -->
        <template v-else-if="activeTab === 'generations'">
          <div v-if="generations.length === 0" class="bg-card border rounded-lg text-center py-12 text-muted-foreground">
            <Icon name="lucide:clapperboard" class="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No generations yet.</p>
            <p class="text-sm mt-1">Run the pipeline above to generate a segment for this story.</p>
          </div>
          <GenerationsTable
            v-else
            :item-id="itemId"
            :generations="generations"
          />
        </template>

        <!-- Gallery tab -->
        <template v-else>
          <div v-if="galleryGenerations.length === 0" class="bg-card border rounded-lg text-center py-12 text-muted-foreground">
            <Icon name="lucide:video-off" class="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No finished videos yet.</p>
            <p class="text-sm mt-1">Videos appear here once a generation's video is ready.</p>
          </div>
          <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
              v-for="gen in galleryGenerations"
              :key="`${gen.run}-${gen.seg}`"
              class="rounded-lg border bg-card p-2"
            >
              <div
                class="mx-auto overflow-hidden rounded bg-black"
                :style="galleryFrameStyle(gen)"
              >
                <video
                  :src="videoUrl(gen)"
                  :poster="posterUrl(gen)"
                  controls
                  preload="none"
                  crossorigin="anonymous"
                  class="h-full w-full object-contain"
                >
                  <track
                    v-if="gen.subtitles_path"
                    kind="subtitles"
                    srclang="en"
                    label="English"
                    :src="captionsUrl(gen)"
                    default
                  >
                  Your browser does not support the video tag.
                </video>
              </div>

              <div class="mt-2 flex flex-wrap items-center gap-1.5">
                <span class="rounded bg-muted px-1.5 py-0.5 text-[11px] font-mono font-medium">
                  r{{ gen.run }}·s{{ gen.seg }}
                </span>
                <Badge variant="outline" class="text-[11px] font-mono px-1.5 py-0">
                  {{ gen.aspect_format || '16:9' }}
                </Badge>
                <span
                  v-if="gen.style_theme_name || gen.style_theme"
                  class="rounded bg-stale-bg px-1.5 py-0.5 text-[11px] text-stale"
                >
                  {{ gen.style_theme_name || gen.style_theme }}
                </span>
                <span
                  v-if="gen.asr_qa && gen.asr_qa.verdict"
                  class="rounded px-1.5 py-0.5 text-[11px] font-medium"
                  :class="qaClass(gen.asr_qa.verdict)"
                  :title="`ASR match ratio ${gen.asr_qa.ratio}`"
                >
                  {{ qaLabel(gen.asr_qa.verdict) }}
                  <span v-if="gen.asr_qa.ratio !== undefined && gen.asr_qa.ratio !== null">{{ gen.asr_qa.ratio }}</span>
                </span>
                <NuxtLink
                  :to="`/hn/item/${itemId}/run/${gen.run}/segment/${gen.seg}`"
                  class="ml-auto text-[11px] text-primary hover:underline"
                >
                  open ↗
                </NuxtLink>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <div v-else class="text-center py-8 text-muted-foreground">
      Item not found
    </div>
  </div>
</template>

<script setup>
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Icon } from '#components'

const route = useRoute()
const config = useRuntimeConfig()

const itemId = computed(() => parseInt(Array.isArray(route.params.id) ? route.params.id[0] : route.params.id))

// Item
const { data: item, pending: isLoading, error } = await useAsyncData(
  `hn-item-${route.params.id}`,
  () => $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}`),
  {
    default: () => null
  }
)

// Header helpers
const domain = computed(() => {
  if (!item.value?.url) return null
  try {
    return new URL(item.value.url).hostname.replace(/^www\./, '')
  } catch {
    return null
  }
})

const itemAge = computed(() => {
  const ts = item.value?.time
  if (!ts) return 'Unknown'
  const diffMs = Date.now() - ts * 1000
  const diffMins = Math.floor(diffMs / (1000 * 60))
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 365) return `${diffDays}d ago`
  return `${Math.floor(diffDays / 365)}y ago`
})

// Generations
const generations = ref([])
const generationsLoading = ref(false)
const generationsError = ref(null)

const latestShortDescription = computed(() => {
  const latest = generations.value.find(g => g.run_short_description)
  return latest?.run_short_description || null
})

const galleryGenerations = computed(() => generations.value.filter(g => g.video_ready))

async function fetchGenerations() {
  try {
    generationsLoading.value = true
    generationsError.value = null

    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/generations`)
    generations.value = response.generations || []
  } catch (err) {
    console.error('Failed to fetch generations:', err)
    generationsError.value = 'Failed to load generations: ' + err.message
  } finally {
    generationsLoading.value = false
  }
}

watch(item, (newItem) => {
  if (newItem) {
    fetchGenerations()
  }
}, { immediate: true })

// Tabs
const activeTab = ref('generations')

// Actions
const aspectFormat = ref('16:9')
const isQueueing = ref('') // '' | 'pipeline' | 'script'
const actionMessage = ref('')
const actionMessageIsError = ref(false)
let messageTimer = null

function setActionMessage(message, isError = false) {
  actionMessage.value = message
  actionMessageIsError.value = isError
  if (messageTimer) clearTimeout(messageTimer)
  messageTimer = setTimeout(() => {
    actionMessage.value = ''
  }, 6000)
}

async function startFullPipeline() {
  if (isQueueing.value) return

  try {
    isQueueing.value = 'pipeline'

    await $fetch(`${config.public.apiBase}/api/hn/single-task-pipeline`, {
      method: 'POST',
      body: {
        item_id: itemId.value,
        aspect_format: aspectFormat.value
      }
    })

    setActionMessage(`Full pipeline queued (${aspectFormat.value})`)
    setTimeout(() => fetchGenerations(), 2000)
  } catch (err) {
    console.error('Failed to queue full pipeline:', err)
    setActionMessage('Failed to queue pipeline: ' + err.message, true)
  } finally {
    isQueueing.value = ''
  }
}

async function startScriptOnlyRun() {
  if (isQueueing.value) return

  try {
    isQueueing.value = 'script'

    await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs`, {
      method: 'POST',
      body: { continue_chain: false }
    })

    setActionMessage('Script-only run queued')
    setTimeout(() => fetchGenerations(), 2000)
  } catch (err) {
    console.error('Failed to queue script-only run:', err)
    setActionMessage('Failed to queue run: ' + err.message, true)
  } finally {
    isQueueing.value = ''
  }
}

// Gallery media helpers
function videoUrl(gen) {
  return `${config.public.apiBase}/api/video/${itemId.value}/${gen.run}/${gen.seg}/segment.mp4`
}

function captionsUrl(gen) {
  return `${config.public.apiBase}/api/video/${itemId.value}/${gen.run}/${gen.seg}/captions.vtt`
}

function posterUrl(gen) {
  if (!gen.images_total || gen.images_total < 1) return undefined
  return `${config.public.apiBase}/api/images/${itemId.value}/${gen.run}/${gen.seg}/1/image.png`
}

function galleryFrameStyle(gen) {
  const ar = { '16:9': '16 / 9', '1:1': '1 / 1', '9:16': '9 / 16' }[gen.aspect_format || '16:9'] || '16 / 9'
  const maxW = gen.aspect_format === '9:16' ? '240px' : '100%'
  return { aspectRatio: ar, maxWidth: maxW }
}

// QA badge (shared style with GenerationsTable)
function qaPassed(verdict) {
  const v = String(verdict || '').toLowerCase()
  return v === 'pass' || v === 'good'
}

function qaLabel(verdict) {
  return qaPassed(verdict) ? 'PASS' : String(verdict).toUpperCase()
}

function qaClass(verdict) {
  return qaPassed(verdict)
    ? 'bg-ok-bg text-ok border border-ok-border'
    : 'bg-warn-bg text-warn'
}

onBeforeUnmount(() => {
  if (messageTimer) clearTimeout(messageTimer)
})
</script>
