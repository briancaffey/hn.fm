<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted, computed } from 'vue'
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

interface PipelineStepStatus {
  step_name: string
  status: string
  segment_id?: string
  start_time?: string
  end_time?: string
  error?: string
  progress?: number
  dependencies: string[]
}

interface PipelineStatus {
  content_id: string
  overall_status: string
  current_step?: string
  step_statuses: PipelineStepStatus[]
  completed_steps: string[]
  failed_steps: string[]
  total_steps: number
  progress_percentage: number
  estimated_completion?: string
  last_updated: string
  processing_options: Record<string, any>
}

interface ArtifactFile {
  path: string
  step: string
  type: string
}

interface ContentArtifacts {
  content_id: string
  audio_files: ArtifactFile[]
  image_files: ArtifactFile[]
  video_files: ArtifactFile[]
  script_files: ArtifactFile[]
  raw_files: ArtifactFile[]
}

const route = useRoute()
const itemId = route.params.id as string

const contentItem = ref<ContentItem | null>(null)
const pipelineStatus = ref<PipelineStatus | null>(null)
const artifacts = ref<ContentArtifacts | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const processing = ref(false)
const processError = ref<string | null>(null)
const activeTab = ref('audio')
const deleting = ref(false)
const deleteError = ref<string | null>(null)

// Get runtime config for API base URL
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const hasPipelineData = computed(() => {
  return pipelineStatus.value !== null
})

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

const getMediaUrl = (path: string, mediaType: string) => {
  return `${apiBase}/api/content/${itemId}/media/${mediaType}/${path.split('/').pop()}`
}

const fetchContentItem = async () => {
  try {
    loading.value = true
    error.value = null

    const data: ContentItem = await $fetch(`${apiBase}/api/content/${itemId}`)
    contentItem.value = data
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch content item'
    console.error('Error fetching content item:', err)
  } finally {
    loading.value = false
  }
}

const fetchPipelineStatus = async () => {
  try {
    const data: PipelineStatus = await $fetch(`${apiBase}/api/content/${itemId}/pipeline-status`)
    pipelineStatus.value = data
  } catch (err) {
    console.log('Pipeline status not available for this content item')
  }
}

const fetchArtifacts = async () => {
  try {
    const data: ContentArtifacts = await $fetch(`${apiBase}/api/content/${itemId}/artifacts`)
    artifacts.value = data
  } catch (err) {
    console.log('Artifacts not available for this content item')
  }
}

const triggerProcessing = async () => {
  try {
    processing.value = true
    processError.value = null

    // Trigger the pipeline
    const response = await $fetch(`${apiBase}/api/pipeline/process`, {
      method: 'POST',
      body: {
        url: contentItem.value?.url,
        content_type: contentItem.value?.content_type || 'article',
        options: {
          priority: 'high',
          voice: 'en-US-Standard-A'
        }
      }
    })

    console.log('Processing triggered:', response)

    // Refresh status after a delay
    setTimeout(() => {
      fetchPipelineStatus()
      fetchArtifacts()
    }, 2000)
  } catch (err) {
    processError.value = err instanceof Error ? err.message : 'Failed to trigger processing'
    console.error('Error triggering processing:', err)
  } finally {
    processing.value = false
  }
}

const deleteContent = async () => {
  if (!confirm('Are you sure you want to delete this content item? This action cannot be undone.')) {
    return
  }

  try {
    deleting.value = true
    deleteError.value = null

    await $fetch(`${apiBase}/api/content/${itemId}`, {
      method: 'DELETE'
    })

    // Redirect to items list page after successful deletion
    await navigateTo('/items')
  } catch (err) {
    deleteError.value = err instanceof Error ? err.message : 'Failed to delete content'
    console.error('Error deleting content:', err)
  } finally {
    deleting.value = false
  }
}

const refreshData = async () => {
  await Promise.all([
    fetchContentItem(),
    fetchPipelineStatus(),
    fetchArtifacts()
  ])
}

onMounted(() => {
  refreshData()
})

// Auto-refresh pipeline status every 5 seconds if processing
let refreshInterval: NodeJS.Timeout | null = null

watch(pipelineStatus, (newStatus) => {
  if (newStatus && newStatus.overall_status === 'processing') {
    if (!refreshInterval) {
      refreshInterval = setInterval(() => {
        fetchPipelineStatus()
        fetchArtifacts()
      }, 5000)
    }
  } else {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<template>
  <div class="min-h-screen bg-background">
    <!-- Navigation Bar -->
    <nav class="border-b bg-card">
      <div class="container mx-auto px-4 py-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-4">
            <h1 class="text-xl font-bold text-foreground">HN.fm</h1>
            <div class="hidden md:flex space-x-6">
              <NuxtLink to="/" class="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                Home
              </NuxtLink>
              <NuxtLink to="/items" class="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                Items
              </NuxtLink>
              <NuxtLink to="/services" class="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors">
                Services
              </NuxtLink>
            </div>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8">
      <div class="space-y-6">
        <!-- Page Header -->
        <div class="flex items-center gap-4">
          <Button variant="outline" @click="navigateTo('/items')">
            <Icon name="lucide:arrow-left" class="h-4 w-4 mr-2" />
            Back to Items
          </Button>
          <Button variant="outline" @click="refreshData" :disabled="loading">
            <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" :class="{ 'animate-spin': loading }" />
            Refresh
          </Button>
          <div class="flex-1"></div>
          <Button variant="destructive" @click="deleteContent" :disabled="deleting">
            <Icon name="lucide:trash-2" class="h-4 w-4 mr-2" :class="{ 'animate-spin': deleting }" />
            {{ deleting ? 'Deleting...' : 'Delete Content' }}
          </Button>
        </div>

        <!-- Delete Error -->
        <div v-if="deleteError" class="text-center py-4 bg-destructive/10 border border-destructive/20 rounded-lg">
          <div class="text-destructive mb-2">
            <Icon name="lucide:alert-circle" class="h-5 w-5 mx-auto" />
          </div>
          <p class="text-destructive text-sm">{{ deleteError }}</p>
          <Button @click="deleteContent" variant="outline" size="sm" class="mt-2">
            <Icon name="lucide:refresh-cw" class="h-3 w-3 mr-1" />
            Try Again
          </Button>
        </div>

        <div class="space-y-1">
          <h1 class="text-3xl font-bold text-foreground">Content Details</h1>
          <p class="text-muted-foreground">Pipeline status and generated artifacts</p>
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
          <Button @click="refreshData" variant="outline" class="mt-4">
            <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
            Try Again
          </Button>
        </div>

        <!-- Content -->
        <div v-else-if="contentItem" class="space-y-6">
          <!-- Content Item Info -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Icon name="lucide:file-text" class="h-5 w-5" />
                Content Information
              </CardTitle>
            </CardHeader>
            <CardContent class="space-y-4">
              <div>
                <h3 class="text-lg font-semibold">{{ contentItem.title }}</h3>
                <p class="text-sm text-muted-foreground">{{ contentItem.url }}</p>
              </div>
              <div class="flex items-center gap-4">
                <Badge :variant="getStatusVariant(contentItem.status)">
                  {{ contentItem.status }}
                </Badge>
                <span class="text-sm text-muted-foreground">
                  Created: {{ new Date(contentItem.created_at).toLocaleDateString() }}
                </span>
              </div>
            </CardContent>
          </Card>

          <!-- Pipeline Status -->
          <Card v-if="pipelineStatus">
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Icon name="lucide:workflow" class="h-5 w-5" />
                Pipeline Status
              </CardTitle>
            </CardHeader>
            <CardContent class="space-y-4">
              <!-- Overall Progress -->
              <div class="space-y-2">
                <div class="flex justify-between text-sm">
                  <span>Overall Progress</span>
                  <span>{{ Math.round(pipelineStatus.progress_percentage) }}%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                  <div
                    class="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    :style="{ width: pipelineStatus.progress_percentage + '%' }"
                  ></div>
                </div>
              </div>

              <!-- Current Step -->
              <div v-if="pipelineStatus.current_step" class="flex items-center gap-2">
                <Icon name="lucide:play" class="h-4 w-4 text-blue-600" />
                <span class="text-sm font-medium">Current Step: {{ pipelineStatus.current_step }}</span>
              </div>

              <!-- Step Statuses -->
              <div class="space-y-3">
                <h4 class="text-sm font-medium">Step Details</h4>
                <div v-for="step in pipelineStatus.step_statuses" :key="step.step_name" class="flex items-center justify-between p-3 border rounded-lg">
                  <div class="flex items-center gap-3">
                    <Icon
                      :name="step.status === 'completed' ? 'lucide:check-circle' : step.status === 'processing' ? 'lucide:play-circle' : 'lucide:circle'"
                      :class="[
                        'h-4 w-4',
                        step.status === 'completed' ? 'text-green-600' : step.status === 'processing' ? 'text-blue-600' : 'text-gray-400'
                      ]"
                    />
                    <div>
                      <p class="text-sm font-medium">{{ step.step_name }}</p>
                      <p class="text-xs text-muted-foreground">{{ step.status }}</p>
                    </div>
                  </div>
                  <Badge :variant="getStatusVariant(step.status)">
                    {{ step.status }}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Generated Artifacts -->
          <Card v-if="artifacts && (artifacts.audio_files.length > 0 || artifacts.image_files.length > 0 || artifacts.video_files.length > 0)">
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Icon name="lucide:package" class="h-5 w-5" />
                Generated Artifacts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <!-- Simple Tab Navigation -->
              <div class="flex border-b border-gray-200 mb-4">
                <button
                  @click="activeTab = 'audio'"
                  :class="[
                    'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                    activeTab === 'audio'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  ]"
                >
                  Audio ({{ artifacts.audio_files.length }})
                </button>
                <button
                  @click="activeTab = 'images'"
                  :class="[
                    'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                    activeTab === 'images'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  ]"
                >
                  Images ({{ artifacts.image_files.length }})
                </button>
                <button
                  @click="activeTab = 'video'"
                  :class="[
                    'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                    activeTab === 'video'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  ]"
                >
                  Video ({{ artifacts.video_files.length }})
                </button>
                <button
                  @click="activeTab = 'scripts'"
                  :class="[
                    'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                    activeTab === 'scripts'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  ]"
                >
                  Scripts ({{ artifacts.script_files.length }})
                </button>
              </div>

              <!-- Audio Files -->
              <div v-if="activeTab === 'audio'" class="space-y-4">
                <div v-if="artifacts.audio_files.length === 0" class="text-center py-8 text-muted-foreground">
                  <Icon name="lucide:headphones" class="h-8 w-8 mx-auto mb-2" />
                  <p>No audio files generated yet</p>
                </div>
                <div v-else class="space-y-3">
                  <div
                    v-for="(audio, index) in artifacts.audio_files"
                    :key="index"
                    class="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <div class="flex items-center gap-3">
                      <Icon name="lucide:headphones" class="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p class="text-sm font-medium">{{ audio.path.split('/').pop() }}</p>
                        <p class="text-xs text-muted-foreground">From: {{ audio.step }}</p>
                      </div>
                    </div>
                    <div class="flex gap-2">
                      <audio :src="getMediaUrl(audio.path, 'audio')" controls class="h-8">
                        Your browser does not support the audio element.
                      </audio>
                      <Button size="sm" variant="outline" as-child>
                        <a :href="getMediaUrl(audio.path, 'audio')" download>
                          <Icon name="lucide:download" class="h-3 w-3 mr-1" />
                          Download
                        </a>
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Image Files -->
              <div v-if="activeTab === 'images'" class="space-y-4">
                <div v-if="artifacts.image_files.length === 0" class="text-center py-8 text-muted-foreground">
                  <Icon name="lucide:image" class="h-8 w-8 mx-auto mb-2" />
                  <p>No images generated yet</p>
                </div>
                <div v-else class="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div
                    v-for="(image, index) in artifacts.image_files"
                    :key="index"
                    class="relative group"
                  >
                    <div class="aspect-square bg-muted rounded-md overflow-hidden">
                      <img
                        :src="getMediaUrl(image.path, 'images')"
                        :alt="image.path.split('/').pop()"
                        class="w-full h-full object-cover"
                      />
                    </div>
                    <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all rounded-md flex items-center justify-center opacity-0 group-hover:opacity-100">
                      <div class="flex gap-2">
                        <Button size="sm" variant="secondary" as-child>
                          <a :href="getMediaUrl(image.path, 'images')" target="_blank">
                            <Icon name="lucide:eye" class="h-3 w-3 mr-1" />
                            View
                          </a>
                        </Button>
                        <Button size="sm" variant="secondary" as-child>
                          <a :href="getMediaUrl(image.path, 'images')" download>
                            <Icon name="lucide:download" class="h-3 w-3 mr-1" />
                            Download
                          </a>
                        </Button>
                      </div>
                    </div>
                    <p class="text-xs text-muted-foreground mt-1">{{ image.path.split('/').pop() }}</p>
                  </div>
                </div>
              </div>

              <!-- Video Files -->
              <div v-if="activeTab === 'video'" class="space-y-4">
                <div v-if="artifacts.video_files.length === 0" class="text-center py-8 text-muted-foreground">
                  <Icon name="lucide:video" class="h-8 w-8 mx-auto mb-2" />
                  <p>No video files generated yet</p>
                </div>
                <div v-else class="space-y-4">
                  <div
                    v-for="(video, index) in artifacts.video_files"
                    :key="index"
                    class="space-y-3"
                  >
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-3">
                        <Icon name="lucide:video" class="h-4 w-4 text-muted-foreground" />
                        <div>
                          <p class="text-sm font-medium">{{ video.path.split('/').pop() }}</p>
                          <p class="text-xs text-muted-foreground">From: {{ video.step }}</p>
                        </div>
                      </div>
                      <Button size="sm" variant="outline" as-child>
                        <a :href="getMediaUrl(video.path, 'video')" download>
                          <Icon name="lucide:download" class="h-3 w-3 mr-1" />
                          Download
                        </a>
                      </Button>
                    </div>
                    <video :src="getMediaUrl(video.path, 'video')" controls class="w-full rounded-md">
                      Your browser does not support the video element.
                    </video>
                  </div>
                </div>
              </div>

              <!-- Script Files -->
              <div v-if="activeTab === 'scripts'" class="space-y-4">
                <div v-if="artifacts.script_files.length === 0" class="text-center py-8 text-muted-foreground">
                  <Icon name="lucide:file-text" class="h-8 w-8 mx-auto mb-2" />
                  <p>No script files generated yet</p>
                </div>
                <div v-else class="space-y-3">
                  <div
                    v-for="(script, index) in artifacts.script_files"
                    :key="index"
                    class="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <div class="flex items-center gap-3">
                      <Icon name="lucide:file-text" class="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p class="text-sm font-medium">{{ script.path.split('/').pop() }}</p>
                        <p class="text-xs text-muted-foreground">From: {{ script.step }}</p>
                      </div>
                    </div>
                    <Button size="sm" variant="outline" as-child>
                      <a :href="getMediaUrl(script.path, 'content')" download>
                        <Icon name="lucide:download" class="h-3 w-3 mr-1" />
                        Download
                      </a>
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Processing Controls -->
          <Card>
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Icon name="lucide:play" class="h-5 w-5" />
                Processing Controls
              </CardTitle>
            </CardHeader>
            <CardContent class="space-y-4">
              <div v-if="!pipelineStatus" class="text-center py-4">
                <p class="text-muted-foreground mb-4">No pipeline data available for this content item.</p>
                <Button @click="triggerProcessing" :disabled="processing">
                  <Icon name="lucide:play" class="h-4 w-4 mr-2" />
                  Start Processing
                </Button>
              </div>
              <div v-else-if="pipelineStatus.overall_status === 'processing'" class="text-center py-4">
                <div class="flex items-center justify-center gap-2 mb-4">
                  <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                  <span>Processing in progress...</span>
                </div>
                <p class="text-sm text-muted-foreground">The pipeline is currently running. This page will auto-refresh.</p>
              </div>
              <div v-else class="text-center py-4">
                <p class="text-muted-foreground mb-4">Pipeline status: {{ pipelineStatus.overall_status }}</p>
                <Button @click="triggerProcessing" :disabled="processing">
                  <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
                  Restart Processing
                </Button>
              </div>

              <div v-if="processError" class="text-center py-4">
                <p class="text-destructive mb-2">{{ processError }}</p>
                <Button @click="triggerProcessing" variant="outline">
                  <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
                  Try Again
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  </div>
</template>
