<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { Button } from '~/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
import { Badge } from '~/components/ui/badge'
import { Separator } from '~/components/ui/separator'
import { Icon } from '#components'

interface HNStoryData {
  id: number
  deleted?: boolean
  type: string
  by?: string
  time: number
  text?: string
  dead?: boolean
  parent?: number
  poll?: number
  kids?: number[]
  url?: string
  score?: number
  title?: string
  parts?: number[]
  descendants?: number
}

interface ContentItem {
  id: string
  title: string
  url: string
  content_type: string
  status: string
  created_at: string
  updated_at: string
  metadata: Record<string, any>
  hn_story_data?: HNStoryData
  raw_text?: string
  processed_text?: string
  script?: string
  summary?: string
  audio_path?: string
  video_path?: string
  image_paths: string[]
  processing_steps: string[]
  errors: string[]
}

const route = useRoute()
const itemId = route.params.id as string

const contentItem = ref<ContentItem | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const processing = ref(false)
const processError = ref<string | null>(null)

// Get runtime config for API base URL
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const fetchItemDetails = async () => {
  try {
    loading.value = true
    error.value = null

    const data: ContentItem = await $fetch(`${apiBase}/api/content/${itemId}`)
    contentItem.value = data
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch item details'
    console.error('Error fetching item details:', err)
  } finally {
    loading.value = false
  }
}

const getStatusVariant = (status: string) => {
  switch (status) {
    case 'completed':
      return 'default'
    case 'processing':
      return 'secondary'
    case 'pending':
      return 'outline'
    case 'failed':
      return 'destructive'
    default:
      return 'outline'
  }
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatUnixTime = (unixTime: number) => {
  const date = new Date(unixTime * 1000)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getContentTypeIcon = (contentType: string) => {
  switch (contentType) {
    case 'article':
      return 'lucide:file-text'
    case 'video':
      return 'lucide:video'
    case 'podcast':
      return 'lucide:headphones'
    case 'news':
      return 'lucide:newspaper'
    default:
      return 'lucide:file'
  }
}

const goBack = () => {
  navigateTo('/items')
}

const processContent = async () => {
  if (!contentItem.value || processing.value) return

  try {
    processing.value = true
    processError.value = null

    const response = await $fetch(`${apiBase}/api/content/${itemId}/process`, {
      method: 'POST'
    })

    // Refresh the content item to get updated status
    await fetchItemDetails()

    // Show success message
    console.log('Processing started:', response)

  } catch (err) {
    processError.value = err instanceof Error ? err.message : 'Failed to start processing'
    console.error('Error starting processing:', err)
  } finally {
    processing.value = false
  }
}

onMounted(() => {
  if (itemId) {
    fetchItemDetails()
  }
})

// Auto-refresh when processing
let refreshInterval: NodeJS.Timeout | null = null

watch(() => contentItem.value?.status, (newStatus) => {
  if (newStatus === 'processing') {
    // Start polling every 5 seconds when processing
    refreshInterval = setInterval(() => {
      fetchItemDetails()
    }, 5000)
  } else if (refreshInterval) {
    // Stop polling when not processing
    clearInterval(refreshInterval)
    refreshInterval = null
  }
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="flex items-center gap-4">
      <Button @click="goBack" variant="outline" size="sm">
        <Icon name="lucide:arrow-left" class="h-4 w-4 mr-2" />
        Back to Items
      </Button>
      <Button @click="fetchItemDetails" variant="outline" size="sm" :disabled="loading">
        <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" :class="{ 'animate-spin': loading }" />
        Refresh
      </Button>
      <div class="space-y-1">
        <h1 class="text-3xl font-bold text-foreground">Item Details</h1>
        <p class="text-muted-foreground">
          Detailed information about content item
        </p>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      <span class="ml-2 text-muted-foreground">Loading item details...</span>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-center py-8">
      <div class="text-destructive mb-2">
        <Icon name="lucide:alert-circle" class="h-8 w-8 mx-auto" />
      </div>
      <p class="text-muted-foreground">{{ error }}</p>
      <Button @click="fetchItemDetails" variant="outline" class="mt-4">
        <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
        Try Again
      </Button>
    </div>

    <!-- Item Details -->
    <div v-else-if="contentItem" class="space-y-6">
      <!-- Basic Information -->
      <Card>
        <CardHeader>
          <div class="flex items-start justify-between">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-3">
                <Icon
                  :name="getContentTypeIcon(contentItem.content_type)"
                  class="h-5 w-5 text-muted-foreground"
                />
                <Badge variant="outline">
                  {{ contentItem.content_type }}
                </Badge>
                <Badge :variant="getStatusVariant(contentItem.status)">
                  {{ contentItem.status }}
                </Badge>
              </div>
              <CardTitle class="text-2xl leading-tight">
                {{ contentItem.title }}
              </CardTitle>
            </div>
            <div class="flex gap-2 ml-4">
                            <Button
                size="sm"
                variant="outline"
                @click="processContent"
                :disabled="processing || contentItem.status === 'processing' || contentItem.script"
              >
                <Icon
                  :name="processing ? 'lucide:loader-2' : 'lucide:play'"
                  class="h-4 w-4 mr-2"
                  :class="{ 'animate-spin': processing }"
                />
                {{ processing ? 'Processing...' : contentItem.script ? 'Script Generated' : 'Generate Script' }}
              </Button>
              <Button size="sm" variant="outline">
                <Icon name="lucide:edit" class="h-4 w-4 mr-2" />
                Edit
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- URL -->
          <div>
            <label class="text-sm font-medium text-muted-foreground">Source URL</label>
            <a
              :href="contentItem.url"
              target="_blank"
              rel="noopener noreferrer"
              class="block text-primary hover:underline break-all mt-1"
            >
              <Icon name="lucide:external-link" class="h-4 w-4 inline mr-1" />
              {{ contentItem.url }}
            </a>
          </div>

          <!-- Timestamps -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-muted-foreground">Created</label>
              <p class="text-sm mt-1">{{ formatDate(contentItem.created_at) }}</p>
            </div>
            <div>
              <label class="text-sm font-medium text-muted-foreground">Last Updated</label>
              <p class="text-sm mt-1">{{ formatDate(contentItem.updated_at) }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Processing Status and Errors -->
      <Card v-if="processing || processError || contentItem.status === 'processing'">
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <Icon name="lucide:activity" class="h-5 w-5" />
            Processing Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <!-- Processing in progress -->
          <div v-if="processing" class="flex items-center gap-2 text-blue-600">
            <Icon name="lucide:loader-2" class="h-4 w-4 animate-spin" />
            <span>Starting processing...</span>
          </div>

          <!-- Processing status from backend -->
          <div v-else-if="contentItem.status === 'processing'" class="flex items-center gap-2 text-blue-600">
            <Icon name="lucide:loader-2" class="h-4 w-4 animate-spin" />
            <span>Processing in progress...</span>
          </div>

          <!-- Processing error -->
          <div v-if="processError" class="p-3 bg-destructive/10 border border-destructive/20 rounded-md">
            <p class="text-sm text-destructive">{{ processError }}</p>
          </div>
        </CardContent>
      </Card>

      <!-- Hacker News Data -->
      <Card v-if="contentItem.hn_story_data">
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <Icon name="lucide:newspaper" class="h-5 w-5" />
            Hacker News Story Data
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div v-if="contentItem.hn_story_data.score !== undefined">
              <label class="text-sm font-medium text-muted-foreground">Score</label>
              <p class="text-lg font-semibold flex items-center gap-1">
                <Icon name="lucide:arrow-up" class="h-4 w-4 text-green-600" />
                {{ contentItem.hn_story_data.score }}
              </p>
            </div>
            <div v-if="contentItem.hn_story_data.descendants !== undefined">
              <label class="text-sm font-medium text-muted-foreground">Comments</label>
              <p class="text-lg font-semibold flex items-center gap-1">
                <Icon name="lucide:message-circle" class="h-4 w-4 text-blue-600" />
                {{ contentItem.hn_story_data.descendants }}
              </p>
            </div>
            <div v-if="contentItem.hn_story_data.by">
              <label class="text-sm font-medium text-muted-foreground">Author</label>
              <p class="text-lg font-semibold">{{ contentItem.hn_story_data.by }}</p>
            </div>
            <div v-if="contentItem.hn_story_data.time">
              <label class="text-sm font-medium text-muted-foreground">Posted on HN</label>
              <p class="text-sm">{{ formatUnixTime(contentItem.hn_story_data.time) }}</p>
            </div>
            <div v-if="contentItem.hn_story_data.type">
              <label class="text-sm font-medium text-muted-foreground">HN Type</label>
              <p class="text-sm">{{ contentItem.hn_story_data.type }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Content Processing -->
      <Card v-if="contentItem.raw_text || contentItem.processed_text || contentItem.script">
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <Icon name="lucide:file-text" class="h-5 w-5" />
            Content Processing
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- Raw Text -->
          <div v-if="contentItem.raw_text">
            <label class="text-sm font-medium text-muted-foreground">Raw Scraped Text</label>
            <div class="mt-2 p-3 bg-muted rounded-md max-h-32 overflow-y-auto">
              <p class="text-sm whitespace-pre-wrap">{{ contentItem.raw_text }}</p>
            </div>
          </div>

          <!-- Processed Text -->
          <div v-if="contentItem.processed_text">
            <label class="text-sm font-medium text-muted-foreground">Processed Text</label>
            <div class="mt-2 p-3 bg-muted rounded-md max-h-32 overflow-y-auto">
              <p class="text-sm whitespace-pre-wrap">{{ contentItem.processed_text }}</p>
            </div>
          </div>

          <!-- Script -->
          <div v-if="contentItem.script">
            <label class="text-sm font-medium text-muted-foreground">Generated Script</label>
            <div class="mt-2 p-3 bg-muted rounded-md max-h-32 overflow-y-auto">
              <p class="text-sm whitespace-pre-wrap">{{ contentItem.script }}</p>
            </div>
          </div>

          <!-- Summary -->
          <div v-if="contentItem.summary">
            <label class="text-sm font-medium text-muted-foreground">Summary</label>
            <div class="mt-2 p-3 bg-muted rounded-md">
              <p class="text-sm">{{ contentItem.summary }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Media Files -->
      <Card v-if="contentItem.audio_path || contentItem.video_path || contentItem.image_paths.length > 0">
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <Icon name="lucide:media" class="h-5 w-5" />
            Generated Media
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-4">
          <!-- Audio -->
          <div v-if="contentItem.audio_path">
            <label class="text-sm font-medium text-muted-foreground">Audio File</label>
            <div class="mt-2 flex items-center gap-2">
              <Icon name="lucide:headphones" class="h-4 w-4 text-muted-foreground" />
              <span class="text-sm">{{ contentItem.audio_path }}</span>
              <Button size="sm" variant="outline">
                <Icon name="lucide:play" class="h-4 w-4 mr-2" />
                Play
              </Button>
            </div>
          </div>

          <!-- Video -->
          <div v-if="contentItem.video_path">
            <label class="text-sm font-medium text-muted-foreground">Video File</label>
            <div class="mt-2 flex items-center gap-2">
              <Icon name="lucide:video" class="h-4 w-4 text-muted-foreground" />
              <span class="text-sm">{{ contentItem.video_path }}</span>
              <Button size="sm" variant="outline">
                <Icon name="lucide:play" class="h-4 w-4 mr-2" />
                Play
              </Button>
            </div>
          </div>

          <!-- Images -->
          <div v-if="contentItem.image_paths.length > 0">
            <label class="text-sm font-medium text-muted-foreground">Generated Images</label>
            <div class="mt-2 grid grid-cols-2 md:grid-cols-3 gap-2">
              <div
                v-for="(imagePath, index) in contentItem.image_paths"
                :key="index"
                class="relative group"
              >
                <div class="aspect-square bg-muted rounded-md flex items-center justify-center">
                  <Icon name="lucide:image" class="h-8 w-8 text-muted-foreground" />
                </div>
                <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all rounded-md flex items-center justify-center opacity-0 group-hover:opacity-100">
                  <Button size="sm" variant="secondary">
                    <Icon name="lucide:eye" class="h-4 w-4 mr-2" />
                    View
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Processing Steps -->
      <Card v-if="contentItem.processing_steps.length > 0">
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <Icon name="lucide:list-checks" class="h-5 w-5" />
            Processing Steps
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="space-y-2">
            <div
              v-for="(step, index) in contentItem.processing_steps"
              :key="index"
              class="flex items-center gap-2"
            >
              <Icon name="lucide:check-circle" class="h-4 w-4 text-green-600" />
              <span class="text-sm capitalize">{{ step.replace(/_/g, ' ') }}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Errors -->
      <Card v-if="contentItem.errors.length > 0">
        <CardHeader>
          <CardTitle class="flex items-center gap-2 text-destructive">
            <Icon name="lucide:alert-triangle" class="h-5 w-5" />
            Processing Errors
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="space-y-2">
            <div
              v-for="(error, index) in contentItem.errors"
              :key="index"
              class="p-3 bg-destructive/10 border border-destructive/20 rounded-md"
            >
              <p class="text-sm text-destructive">{{ error }}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <!-- Metadata -->
      <Card v-if="Object.keys(contentItem.metadata).length > 0">
        <CardHeader>
          <CardTitle class="flex items-center gap-2">
            <Icon name="lucide:info" class="h-5 w-5" />
            Additional Metadata
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div
              v-for="(value, key) in contentItem.metadata"
              :key="key"
              class="space-y-1"
            >
              <label class="text-sm font-medium text-muted-foreground capitalize">
                {{ key.replace(/_/g, ' ') }}
              </label>
              <p class="text-sm">
                {{ typeof value === 'object' ? JSON.stringify(value) : String(value) }}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  </div>
</template>
