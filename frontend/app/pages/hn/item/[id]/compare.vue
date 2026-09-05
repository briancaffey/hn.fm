<template>
  <PageShell>
    <Breadcrumbs
      :items="[
        { label: 'Stories', to: '/hn/items' },
        { label: `Item ${itemId}`, to: `/hn/item/${itemId}` },
        { label: 'Compare takes' },
      ]"
    />
    <div class="mb-4 flex items-center justify-between gap-3">
      <div>
        <h1 class="text-lg font-semibold">Compare takes</h1>
        <p class="text-xs text-muted-foreground">
          Item {{ itemId }} · {{ takes.length }} take{{ takes.length === 1 ? '' : 's' }}
          <span v-if="title"> · {{ title }}</span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button
          class="rounded border px-2 py-1 text-xs hover:bg-muted"
          @click="load"
        >Refresh</button>
        <NuxtLink :to="`/hn/item/${itemId}`" class="rounded border px-2 py-1 text-xs hover:bg-muted">
          Item page
        </NuxtLink>
      </div>
    </div>

    <p v-if="loading" class="text-xs text-muted-foreground">Loading takes…</p>
    <p v-else-if="!takes.length" class="text-xs text-muted-foreground">
      No takes yet for this item. Run the pipeline to create some.
    </p>

    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="t in takes"
        :key="`${t.run}-${t.seg}`"
        class="rounded-lg border bg-card p-2"
      >
        <!-- aspect-aware video frame -->
        <div
          class="mx-auto overflow-hidden rounded bg-black"
          :style="frameStyle(t)"
        >
          <video
            v-if="t.video_ready"
            :src="videoUrl(t)"
            controls
            preload="metadata"
            class="h-full w-full object-contain"
          />
          <div v-else class="flex h-full w-full items-center justify-center text-xs text-white/60">
            rendering…
          </div>
        </div>

        <!-- receipts -->
        <div class="mt-2 flex flex-wrap gap-1">
          <span class="rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium">
            run {{ t.run }}·{{ t.seg }}
          </span>
          <span class="rounded bg-running-bg px-1.5 py-0.5 text-[11px] text-running">
            {{ t.aspect_format || '16:9' }}
          </span>
          <span v-if="t.style_theme_name" class="rounded bg-stale-bg px-1.5 py-0.5 text-[11px] text-stale">
            🎨 {{ t.style_theme_name }}
          </span>
          <span
            v-if="t.asr_qa && t.asr_qa.verdict"
            class="rounded px-1.5 py-0.5 text-[11px]"
            :class="qaClass(t.asr_qa.verdict)"
            :title="`ASR match ratio ${t.asr_qa.ratio}`"
          >
            QA {{ t.asr_qa.verdict }} {{ t.asr_qa.ratio }}
          </span>
        </div>

        <div class="mt-1 flex items-center justify-between">
          <span class="text-[11px] text-muted-foreground">
            {{ t.images_ready ? 'images ✓' : '' }} {{ t.audio_ready ? 'audio ✓' : '' }}
          </span>
          <NuxtLink
            :to="`/hn/item/${itemId}/run/${t.run}/segment/${t.seg}`"
            class="text-[11px] text-running hover:underline"
          >open ↗</NuxtLink>
        </div>
      </div>
    </div>
  </PageShell>
</template>

<script setup lang="ts">
import PageShell from '~/components/kit/PageShell.vue'
import Breadcrumbs from '~/components/kit/Breadcrumbs.vue'
const route = useRoute()
const config = useRuntimeConfig()
const itemId = computed(() => Number(route.params.id))

// One row from /api/segments. Only the fields this page reads are declared —
// enough for a backend rename to break here rather than render an empty card.
interface Take {
  item_id: number
  run: number
  seg: number
  aspect_format?: string | null
  style_theme?: string | null
  style_theme_name?: string | null
  asr_qa?: { verdict?: string, score?: number } | null
  video_path?: string | null
}

const takes = ref<Take[]>([])
const title = ref<string>('')
const loading = ref(true)

const apiBase = computed(() => config.public?.apiBase || 'http://localhost:8000')

function videoUrl(t: Take) {
  return `${apiBase.value}/api/video/${t.item_id}/${t.run}/${t.seg}/segment.mp4`
}

function frameStyle(t: Take) {
  const ar = { '16:9': '16 / 9', '1:1': '1 / 1', '9:16': '9 / 16' }[t.aspect_format || '16:9']
  // cap vertical height so 9:16 cards stay reasonable
  const maxW = (t.aspect_format === '9:16') ? '220px' : '100%'
  return { aspectRatio: ar, maxWidth: maxW }
}

function qaClass(verdict: string) {
  if (verdict === 'good') return 'bg-ok-bg text-ok'
  if (verdict === 'ok') return 'bg-warn-bg text-warn'
  return 'bg-danger-bg text-danger'
}

async function load() {
  loading.value = true
  try {
    const resp = await $fetch<{ segments?: Take[] }>(
      `${apiBase.value}/api/segments?offset=0&limit=500`
    )
    const all = resp?.segments || []
    takes.value = all
      .filter(s => Number(s.item_id) === itemId.value)
      .sort((a, b) => (a.run - b.run) || (a.seg - b.seg))
    try {
      const item = await $fetch<{ title?: string }>(
        `${apiBase.value}/api/hn/items/${itemId.value}`
      )
      title.value = item?.title || ''
    } catch {
      // A missing title just leaves the heading blank.
    }
  } catch {
    takes.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
