<template>
  <div class="bg-card border rounded-lg overflow-hidden">
    <table class="min-w-full divide-y divide-border">
      <thead class="bg-muted/50">
        <tr>
          <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Run/Seg
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Created
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Theme
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Format
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Status
          </th>
          <th class="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
            QA
          </th>
          <th class="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Actions
          </th>
        </tr>
      </thead>
      <tbody class="bg-card divide-y divide-border">
        <template v-for="gen in generations" :key="genKey(gen)">
          <tr
            class="hover:bg-muted/50 transition-colors cursor-pointer"
            @click="toggleExpanded(gen)"
          >
            <td class="px-4 py-3 whitespace-nowrap">
              <div class="flex items-center gap-2">
                <Icon
                  :name="isExpanded(gen) ? 'lucide:chevron-down' : 'lucide:chevron-right'"
                  class="h-4 w-4 text-muted-foreground flex-shrink-0"
                />
                <span class="font-mono text-sm text-foreground">r{{ gen.run }}·s{{ gen.seg }}</span>
              </div>
            </td>
            <td class="px-4 py-3 whitespace-nowrap text-sm text-muted-foreground" :title="gen.created_at">
              {{ relativeTime(gen.created_at) }}
            </td>
            <td class="px-4 py-3 text-sm text-foreground">
              <span v-if="gen.style_theme_name || gen.style_theme" class="inline-flex items-center gap-1">
                <Icon name="lucide:palette" class="h-3 w-3 text-muted-foreground" />
                {{ gen.style_theme_name || gen.style_theme }}
              </span>
              <span v-else class="text-muted-foreground">—</span>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
              <Badge variant="outline" class="text-xs font-mono">
                {{ gen.aspect_format || '16:9' }}
              </Badge>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
              <div class="flex items-center gap-2">
                <span
                  class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium"
                  :class="chipClass(gen.audio_ready)"
                >
                  <span class="h-1.5 w-1.5 rounded-full" :class="dotClass(gen.audio_ready)" />
                  Audio
                </span>
                <span
                  class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium"
                  :class="chipClass(imagesReady(gen))"
                  :title="`${gen.images_ready || 0}/${gen.images_total || 0} images`"
                >
                  <span class="h-1.5 w-1.5 rounded-full" :class="dotClass(imagesReady(gen))" />
                  Images
                </span>
                <span
                  class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium"
                  :class="chipClass(gen.video_ready)"
                >
                  <span class="h-1.5 w-1.5 rounded-full" :class="dotClass(gen.video_ready)" />
                  Video
                </span>
              </div>
            </td>
            <td class="px-4 py-3 whitespace-nowrap">
              <span
                v-if="gen.asr_qa && gen.asr_qa.verdict"
                class="rounded px-1.5 py-0.5 text-[11px] font-medium"
                :class="qaClass(gen.asr_qa.verdict)"
                :title="`ASR match ratio ${gen.asr_qa.ratio}`"
              >
                {{ qaLabel(gen.asr_qa.verdict) }}
                <span v-if="gen.asr_qa.ratio !== undefined && gen.asr_qa.ratio !== null">{{ gen.asr_qa.ratio }}</span>
              </span>
              <span v-else class="text-xs text-muted-foreground">—</span>
            </td>
            <td class="px-4 py-3 whitespace-nowrap text-right">
              <div class="flex items-center justify-end gap-3" @click.stop>
                <NuxtLink
                  :to="`/hn/item/${itemId}/run/${gen.run}/segment/${gen.seg}`"
                  class="text-sm text-primary hover:text-primary/80 font-medium"
                >
                  X-Ray
                </NuxtLink>
                <button
                  v-if="gen.video_ready"
                  class="text-sm text-primary hover:text-primary/80 font-medium"
                  @click="expand(gen)"
                >
                  ▶ Watch
                </button>
              </div>
            </td>
          </tr>

          <!-- Expanded row: inline video + thumbnail strip -->
          <tr v-if="isExpanded(gen)" :key="`${genKey(gen)}-expanded`" class="bg-muted/30">
            <td colspan="7" class="px-6 py-4">
              <div class="space-y-4">
                <div v-if="gen.video_ready" class="mx-auto overflow-hidden rounded-lg bg-black" :style="frameStyle(gen)">
                  <video
                    :src="videoUrl(gen)"
                    controls
                    preload="metadata"
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
                <div v-else class="text-center py-4 text-sm text-muted-foreground">
                  Video not ready yet.
                </div>

                <div v-if="thumbnailIndexes(gen).length > 0" class="flex gap-2 overflow-x-auto pb-1">
                  <NuxtLink
                    v-for="idx in thumbnailIndexes(gen)"
                    :key="idx"
                    :to="`/hn/item/${itemId}/run/${gen.run}/segment/${gen.seg}`"
                    class="flex-shrink-0"
                  >
                    <img
                      :src="imageUrl(gen, idx)"
                      :alt="`Image ${idx} of r${gen.run}·s${gen.seg}`"
                      loading="lazy"
                      class="h-20 w-auto rounded border object-cover hover:opacity-80 transition-opacity"
                    >
                  </NuxtLink>
                </div>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { Badge } from '~/components/ui/badge'
import { Icon } from '#components'

const props = defineProps({
  itemId: {
    type: Number,
    required: true
  },
  generations: {
    type: Array,
    required: true
  }
})

const config = useRuntimeConfig()

// Expanded row state (keyed by "run-seg")
const expandedRows = ref(new Set())

function genKey(gen) {
  return `${gen.run}-${gen.seg}`
}

function isExpanded(gen) {
  return expandedRows.value.has(genKey(gen))
}

function toggleExpanded(gen) {
  const key = genKey(gen)
  const next = new Set(expandedRows.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedRows.value = next
}

function expand(gen) {
  const key = genKey(gen)
  if (!expandedRows.value.has(key)) {
    const next = new Set(expandedRows.value)
    next.add(key)
    expandedRows.value = next
  }
}

// Media URLs
function videoUrl(gen) {
  return `${config.public.apiBase}/api/video/${props.itemId}/${gen.run}/${gen.seg}/segment.mp4`
}

function captionsUrl(gen) {
  return `${config.public.apiBase}/api/video/${props.itemId}/${gen.run}/${gen.seg}/captions.vtt`
}

function imageUrl(gen, index) {
  return `${config.public.apiBase}/api/images/${props.itemId}/${gen.run}/${gen.seg}/${index}/image.png`
}

function thumbnailIndexes(gen) {
  const total = Math.min(gen.images_total || 0, 8)
  return Array.from({ length: total }, (_, i) => i + 1)
}

function imagesReady(gen) {
  if (typeof gen.images_ready === 'boolean') return gen.images_ready
  return (gen.images_total || 0) > 0 && (gen.images_ready || 0) >= gen.images_total
}

// Aspect-aware frame so 9:16 videos stay a reasonable size
function frameStyle(gen) {
  const ar = { '16:9': '16 / 9', '1:1': '1 / 1', '9:16': '9 / 16' }[gen.aspect_format || '16:9'] || '16 / 9'
  const maxW = gen.aspect_format === '9:16' ? '280px' : '640px'
  return { aspectRatio: ar, maxWidth: maxW }
}

// Status chip styles
function chipClass(ready) {
  return ready
    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
    : 'bg-muted text-muted-foreground'
}

function dotClass(ready) {
  return ready ? 'bg-green-500' : 'bg-gray-400'
}

// QA badge
function qaPassed(verdict) {
  const v = String(verdict || '').toLowerCase()
  return v === 'pass' || v === 'good'
}

function qaLabel(verdict) {
  return qaPassed(verdict) ? 'PASS' : String(verdict).toUpperCase()
}

function qaClass(verdict) {
  return qaPassed(verdict)
    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
    : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
}

// Relative time from ISO timestamp
function relativeTime(dateString) {
  if (!dateString) return 'Unknown'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return 'Unknown'
  const diffMs = Date.now() - date.getTime()
  const diffMins = Math.floor(diffMs / (1000 * 60))
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 30) return `${diffDays}d ago`
  return date.toLocaleDateString()
}
</script>
