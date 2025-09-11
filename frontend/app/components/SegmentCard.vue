<template>
  <Card class="transition-all duration-200 hover:shadow-md hover:border-orange-500/50 border-l-4 border-l-orange-500/20 cursor-pointer" @click="navigateToSegment">
    <CardContent class="p-6">
      <div class="flex gap-6">
        <!-- Main Content -->
        <div class="flex-1 min-w-0 space-y-3">
          <!-- Title and Status Row -->
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 min-w-0">
              <h3 class="text-lg font-semibold leading-tight text-foreground line-clamp-2">
                {{ segmentTitle }}
              </h3>
              <p class="text-sm text-muted-foreground mt-1">
                Item {{ segment.item_id }} • Run {{ segment.run }} • Segment {{ segment.seg }}
              </p>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <!-- Status Badges -->
              <Badge v-if="segment.audio_ready" variant="default" class="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300">
                <Icon name="lucide:volume-2" class="h-3 w-3 mr-1" />
                Audio Ready
              </Badge>
              <Badge v-if="segment.images_ready" variant="default" class="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300">
                <Icon name="lucide:image" class="h-3 w-3 mr-1" />
                Images Ready
              </Badge>
              <Badge v-if="segment.video_ready" variant="default" class="bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300">
                <Icon name="lucide:video" class="h-3 w-3 mr-1" />
                Video Ready
              </Badge>
            </div>
          </div>

          <!-- Script Preview -->
          <div class="bg-muted/50 rounded-lg p-3">
            <p class="text-sm text-muted-foreground line-clamp-3">
              {{ segment.script || 'No script available' }}
            </p>
          </div>

          <!-- Tags and Emojis -->
          <div class="flex items-center gap-2 flex-wrap">
            <div v-if="runData?.tags?.length" class="flex items-center gap-1">
              <Icon name="lucide:tag" class="h-3 w-3 text-muted-foreground" />
              <div class="flex gap-1">
                <Badge
                  v-for="tag in runData.tags.slice(0, 3)"
                  :key="tag"
                  variant="outline"
                  class="text-xs"
                >
                  {{ tag }}
                </Badge>
                <Badge v-if="runData.tags.length > 3" variant="outline" class="text-xs">
                  +{{ runData.tags.length - 3 }}
                </Badge>
              </div>
            </div>
            <div v-if="runData?.emoji?.length" class="flex items-center gap-1">
              <Icon name="lucide:smile" class="h-3 w-3 text-muted-foreground" />
              <span class="text-lg">{{ runData.emoji.join(' ') }}</span>
            </div>
          </div>

          <!-- Created Date -->
          <div class="text-xs text-muted-foreground">
            <Icon name="lucide:clock" class="h-3 w-3 inline mr-1" />
            Created {{ formatDate(segment.created_at) }}
          </div>
        </div>

        <!-- Video Player - Right side, full height -->
        <div v-if="segment.video_ready && segment.video_path" class="flex-shrink-0 self-stretch" @click.stop>
          <div class="w-80 h-full min-h-48 bg-muted rounded-lg overflow-hidden">
            <video
              :src="videoUrl"
              controls
              class="w-full h-full object-cover"
              preload="metadata"
            >
              Your browser does not support the video tag.
            </video>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex items-center justify-between mt-4 pt-4 border-t">
        <div class="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            @click.stop="navigateToSegment"
          >
            <Icon name="lucide:eye" class="h-4 w-4 mr-2" />
            View Details
          </Button>
          <Button
            v-if="segment.audio_ready"
            size="sm"
            variant="outline"
            @click.stop="playAudio"
          >
            <Icon name="lucide:play" class="h-4 w-4 mr-2" />
            Play Audio
          </Button>
        </div>
        <div class="text-xs text-muted-foreground">
          {{ segment.sections_total }} sections
        </div>
      </div>
    </CardContent>
  </Card>
</template>

<script setup>
import { Card, CardContent } from '~/components/ui/card'
import { Button } from '~/components/ui/button'
import { Badge } from '~/components/ui/badge'
import { Icon } from '#components'

const props = defineProps({
  segment: {
    type: Object,
    required: true
  }
})

const config = useRuntimeConfig()

// Get run data for tags and emojis
const runData = ref(null)

// Computed properties
const segmentTitle = computed(() => {
  if (runData.value?.short_description) {
    return runData.value.short_description
  }
  return `Segment ${props.segment.seg}`
})

const videoUrl = computed(() => {
  if (!props.segment.video_path) return null
  return `${config.public.apiBase}/api/video/${props.segment.item_id}/${props.segment.run}/${props.segment.seg}/segment.mp4`
})

const audioUrl = computed(() => {
  if (!props.segment.audio_combined_path) return null
  return `${config.public.apiBase}/api/audio/${props.segment.item_id}/${props.segment.run}/${props.segment.seg}/segment.wav`
})

// Fetch run data
async function fetchRunData() {
  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${props.segment.item_id}/runs/${props.segment.run}`)
    runData.value = response
  } catch (error) {
    console.error('Failed to fetch run data:', error)
  }
}

// Format date
function formatDate(dateString) {
  const date = new Date(dateString)
  const now = new Date()
  const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60))

  if (diffInHours < 1) {
    return 'Just now'
  } else if (diffInHours < 24) {
    return `${diffInHours} hour${diffInHours > 1 ? 's' : ''} ago`
  } else {
    const diffInDays = Math.floor(diffInHours / 24)
    return `${diffInDays} day${diffInDays > 1 ? 's' : ''} ago`
  }
}

// Navigation
function navigateToSegment() {
  navigateTo(`/hn/item/${props.segment.item_id}/run/${props.segment.run}/segment/${props.segment.seg}`)
}

// Play audio
function playAudio() {
  if (audioUrl.value) {
    const audio = new Audio(audioUrl.value)
    audio.play()
  }
}

// Fetch run data on mount
onMounted(() => {
  fetchRunData()
})
</script>
