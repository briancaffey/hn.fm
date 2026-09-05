<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Icon } from '#components'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import StatusBadge from '~/components/kit/StatusBadge.vue'
import InfoHint from '~/components/kit/InfoHint.vue'

/**
 * One finished (or in-progress) piece of content.
 *
 * The readiness badges used to be three hardcoded pastel chips that only
 * appeared when a stage was done, so a half-built segment looked the same as
 * one that had not started. They are now a fixed three-stage strip: you can
 * always see which stage a segment reached and which it has not.
 */
interface Segment {
  item_id: number
  run: number
  seg: number
  created_at?: string
  script?: string
  audio_ready?: boolean
  images_ready?: boolean
  video_ready?: boolean
  video_path?: string | null
  images_total?: number
  sections_total?: number
  style_theme_name?: string | null
  aspect_format?: string | null
}

const props = defineProps<{ segment: Segment }>()

const config = useRuntimeConfig()
const apiBase = config.public.apiBase
const runData = ref<{ title?: string, tags?: string[], emoji?: string[], summary?: string } | null>(null)

const title = computed(() =>
  runData.value?.title || `Item ${props.segment.item_id} · run ${props.segment.run}`)

const videoUrl = computed(() =>
  `${apiBase}/api/video/${props.segment.item_id}/${props.segment.run}/${props.segment.seg}/segment.mp4`)

/** The pipeline in order, so a gap is visible rather than merely absent. */
const stages = computed(() => [
  { key: 'audio', label: 'Audio', icon: 'lucide:volume-2', done: !!props.segment.audio_ready,
    hint: 'Speech generated for every script section, stitched into one track.' },
  { key: 'images', label: 'Images', icon: 'lucide:image', done: !!props.segment.images_ready,
    hint: 'One rendered scene per section. Each prompt sees the previous shots, so a take keeps its cast and setting.' },
  { key: 'video', label: 'Video', icon: 'lucide:video', done: !!props.segment.video_ready,
    hint: 'Images, motion, captions and audio assembled into the finished file.' },
])

const reached = computed(() => stages.value.filter(s => s.done).length)

async function fetchRun() {
  try {
    runData.value = await $fetch(`${apiBase}/api/hn/items/${props.segment.item_id}/runs/${props.segment.run}`)
  } catch {
    // The card is still useful without the run's title and tags.
  }
}
onMounted(fetchRun)

function relative(iso?: string) {
  if (!iso) return ''
  const h = Math.floor((Date.now() - new Date(iso).getTime()) / 3600000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

const href = computed(() =>
  `/hn/item/${props.segment.item_id}/run/${props.segment.run}/segment/${props.segment.seg}`)
</script>

<template>
  <article class="overflow-hidden rounded-lg border bg-card transition-colors hover:border-primary/40">
    <div class="flex flex-col gap-4 p-4 lg:flex-row">
      <div class="min-w-0 flex-1 space-y-3">
        <div>
          <NuxtLink :to="href" class="block">
            <h3 class="line-clamp-2 text-sm font-semibold leading-snug hover:text-primary">
              {{ title }}
            </h3>
          </NuxtLink>
          <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
            <span class="font-mono">{{ segment.item_id }}</span>
            <span class="opacity-40">·</span>
            <span>run {{ segment.run }}</span>
            <span class="opacity-40">·</span>
            <span>segment {{ segment.seg }}</span>
            <template v-if="segment.style_theme_name">
              <span class="opacity-40">·</span>
              <span>{{ segment.style_theme_name }}</span>
            </template>
            <template v-if="segment.aspect_format">
              <span class="opacity-40">·</span>
              <span>{{ segment.aspect_format }}</span>
            </template>
            <template v-if="segment.created_at">
              <span class="opacity-40">·</span>
              <span>{{ relative(segment.created_at) }}</span>
            </template>
          </p>
        </div>

        <!-- Progress strip: always three stages, so a gap reads as a gap. -->
        <div class="flex flex-wrap items-center gap-1.5">
          <StatusBadge
            v-for="s in stages" :key="s.key"
            :status="s.done ? 'ok' : 'queued'"
            :label="s.label"
          />
          <span class="ml-1 text-xs text-muted-foreground">
            {{ reached }}/3 stages
            <InfoHint text="A segment goes script → audio → images → video. A missing stage means the run stopped or is still working, not that the stage was skipped." />
          </span>
        </div>

        <p v-if="segment.script" class="line-clamp-2 rounded-md bg-muted/60 p-2.5 text-xs leading-relaxed text-muted-foreground">
          {{ segment.script.replace(/\[S\d\]\s*/g, '') }}
        </p>

        <div v-if="runData?.tags?.length" class="flex flex-wrap items-center gap-1">
          <Badge v-for="tag in runData.tags.slice(0, 4)" :key="tag" variant="outline" class="text-[11px]">
            {{ tag }}
          </Badge>
          <span v-if="runData.emoji?.length" class="ml-1 text-sm">{{ runData.emoji.join('') }}</span>
        </div>

        <div class="flex items-center gap-2 pt-1">
          <Button as-child size="sm" variant="outline">
            <NuxtLink :to="href">
              <Icon name="lucide:list-tree" class="mr-1.5 h-3.5 w-3.5" />
              Open
            </NuxtLink>
          </Button>
          <Button v-if="segment.video_ready" as-child size="sm" variant="ghost">
            <a :href="videoUrl" target="_blank" rel="noopener">
              <Icon name="lucide:external-link" class="mr-1.5 h-3.5 w-3.5" />
              Video file
            </a>
          </Button>
        </div>
      </div>

      <div v-if="segment.video_ready" class="w-full shrink-0 lg:w-72" @click.stop>
        <video
          :src="videoUrl"
          controls
          preload="metadata"
          class="aspect-video w-full rounded-md border bg-muted object-cover"
        />
      </div>
    </div>
  </article>
</template>
