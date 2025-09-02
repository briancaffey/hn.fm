<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { Button } from '~/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
import { Badge } from '~/components/ui/badge'

import { Icon } from '#components'



interface ContentItem {
  id: string
  hn_item_id: number
  title: string
  url: string
  post_text?: string
  status: string
  created_at: string
  updated_at: string
  raw_content?: string
  processed_content?: string
  script?: string
  audio_file_path?: string
  asr_data?: Record<string, unknown>
}

interface PipelineStatus {
  content_id: string
  status: string
  created_at: string
  updated_at: string
  has_script: boolean
  has_audio: boolean
  has_asr: boolean
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
  // Media endpoint removed - simplified
  return '#'
}

const fetchContentItem = async () => {
  try {
    loading.value = true
    error.value = null

    const data = await $fetch<ContentItem>(`${apiBase}/api/content/${itemId}`)
    contentItem.value = data
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch content item'
    console.error('Error fetching content item:', err)
  } finally {
    loading.value = false
  }
}

const fetchPipelineStatus = async () => {
  // Pipeline status endpoint removed - simplified
  pipelineStatus.value = null
}

const fetchArtifacts = async () => {
  // Artifacts endpoint removed - simplified
  artifacts.value = null
}

const triggerProcessing = async () => {
  try {
    processing.value = true
    processError.value = null

    // Debug: Check what we're sending
    console.log('Content item:', contentItem.value)
    console.log('HN item ID:', contentItem.value?.hn_item_id)
    console.log('HN item ID type:', typeof contentItem.value?.hn_item_id)

    if (!contentItem.value?.hn_item_id) {
      throw new Error('No HN item ID found for this content item')
    }

    // Trigger the pipeline
    const response = await $fetch(`${apiBase}/api/pipeline/process`, {
      method: 'POST',
      body: {
        hn_item_id: contentItem.value.hn_item_id
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
  if (newStatus && newStatus.status === 'processing') {
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
  <div class="space-y-6">
        <!-- Page Header -->
        <div class="flex items-center gap-4">
          <Button variant="outline" class="cursor-pointer" @click="navigateTo('/items')">
            <Icon name="lucide:arrow-left" class="h-4 w-4 mr-2" />
            Back to Items
          </Button>
          <Button variant="outline" :disabled="loading" class="cursor-pointer" @click="refreshData">
            <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" :class="{ 'animate-spin': loading }" />
            Refresh
          </Button>
          <div class="flex-1"/>
          <Button variant="destructive" :disabled="deleting" class="cursor-pointer" @click="deleteContent">
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
          <Button variant="outline" size="sm" class="mt-2 cursor-pointer" @click="deleteContent">
            <Icon name="lucide:refresh-cw" class="h-3 w-3 mr-1" />
            Try Again
          </Button>
        </div>

        <div class="space-y-1">
          <h1 class="text-3xl font-bold text-foreground">
            <span class="text-orange-600">Content</span> Details
          </h1>
          <p class="text-muted-foreground">Pipeline status and generated artifacts</p>
        </div>

        <!-- Loading State -->
        <div v-if="loading" class="flex justify-center items-center py-8">
          <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"/>
          <span class="ml-2 text-muted-foreground">Loading item details...</span>
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="text-center py-8">
          <div class="text-destructive mb-2">
            <Icon name="lucide:alert-circle" class="h-8 w-8 mx-auto" />
          </div>
          <p class="text-muted-foreground">{{ error }}</p>
          <Button variant="outline" class="mt-4 cursor-pointer" @click="refreshData">
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
                <Icon name="lucide:file-text" class="h-5 w-5 text-orange-600" />
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
                <Icon name="lucide:workflow" class="h-5 w-5 text-orange-600" />
                Pipeline Status
              </CardTitle>
            </CardHeader>
            <CardContent class="space-y-4">
              <!-- Overall Progress -->
              <div class="space-y-2">
                <div class="flex justify-between text-sm">
                  <span>Status</span>
                  <span>{{ pipelineStatus.status }}</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                  <div
                    class="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    :style="{ width: pipelineStatus.status === 'completed' ? '100%' : pipelineStatus.status === 'processing' ? '50%' : '0%' }"
                  />
                </div>
              </div>

              <!-- Processing Status -->
              <div class="space-y-3">
                <h4 class="text-sm font-medium">Processing Status</h4>
                <div class="flex items-center justify-between p-3 border rounded-lg">
                  <div class="flex items-center gap-3">
                    <Icon
                      :name="pipelineStatus.has_script ? 'lucide:check-circle' : 'lucide:circle'"
                      :class="[
                        'h-4 w-4',
                        pipelineStatus.has_script ? 'text-green-600' : 'text-gray-400'
                      ]"
                    />
                    <div>
                      <p class="text-sm font-medium">Script Generated</p>
                      <p class="text-xs text-muted-foreground">{{ pipelineStatus.has_script ? 'Completed' : 'Pending' }}</p>
                    </div>
                  </div>
                  <Badge :variant="pipelineStatus.has_script ? 'default' : 'outline'">
                    {{ pipelineStatus.has_script ? 'Completed' : 'Pending' }}
                  </Badge>
                </div>

                <div class="flex items-center justify-between p-3 border rounded-lg">
                  <div class="flex items-center gap-3">
                    <Icon
                      :name="pipelineStatus.has_audio ? 'lucide:check-circle' : 'lucide:circle'"
                      :class="[
                        'h-4 w-4',
                        pipelineStatus.has_audio ? 'text-green-600' : 'text-gray-400'
                      ]"
                    />
                    <div>
                      <p class="text-sm font-medium">Audio Generated</p>
                      <p class="text-xs text-muted-foreground">{{ pipelineStatus.has_audio ? 'Completed' : 'Pending' }}</p>
                    </div>
                  </div>
                  <Badge :variant="pipelineStatus.has_audio ? 'default' : 'outline'">
                    {{ pipelineStatus.has_audio ? 'Completed' : 'Pending' }}
                  </Badge>
                </div>

                <div class="flex items-center justify-between p-3 border rounded-lg">
                  <div class="flex items-center gap-3">
                    <Icon
                      :name="pipelineStatus.has_asr ? 'lucide:check-circle' : 'lucide:circle'"
                      :class="[
                        'h-4 w-4',
                        pipelineStatus.has_asr ? 'text-green-600' : 'text-gray-400'
                      ]"
                    />
                    <div>
                      <p class="text-sm font-medium">ASR Processing</p>
                      <p class="text-xs text-muted-foreground">{{ pipelineStatus.has_asr ? 'Completed' : 'Pending' }}</p>
                    </div>
                  </div>
                  <Badge :variant="pipelineStatus.has_asr ? 'default' : 'outline'">
                    {{ pipelineStatus.has_asr ? 'Completed' : 'Pending' }}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          <!-- Generated Artifacts -->
          <Card v-if="artifacts && (artifacts.audio_files.length > 0 || artifacts.image_files.length > 0 || artifacts.video_files.length > 0)">
            <CardHeader>
              <CardTitle class="flex items-center gap-2">
                <Icon name="lucide:package" class="h-5 w-5 text-orange-600" />
                Generated Artifacts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <!-- Simple Tab Navigation -->
              <div class="flex border-b border-gray-200 mb-4">
                <button
                  :class="[
                    'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                    activeTab === 'audio'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  ]"
                  @click="activeTab = 'audio'"
                >
                  Audio ({{ artifacts.audio_files.length }})
                </button>
                <button
                  :class="[
                    'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                    activeTab === 'images'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  ]"
                  @click="activeTab = 'images'"
                >
                  Images ({{ artifacts.image_files.length }})
                </button>
                <button
                  :class="[
                    'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                    activeTab === 'video'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  ]"
                  @click="activeTab = 'video'"
                >
                  Video ({{ artifacts.video_files.length }})
                </button>
                <button
                  :class="[
                    'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
                    activeTab === 'scripts'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  ]"
                  @click="activeTab = 'scripts'"
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
                      >
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
                <Icon name="lucide:play" class="h-5 w-5 text-orange-600" />
                Processing Controls
              </CardTitle>
            </CardHeader>
            <CardContent class="space-y-4">
              <div v-if="!pipelineStatus" class="text-center py-4">
                <p class="text-muted-foreground mb-4">No pipeline data available for this content item.</p>
                <Button :disabled="processing" class="cursor-pointer" @click="triggerProcessing">
                  <Icon name="lucide:play" class="h-4 w-4 mr-2" />
                  Start Processing
                </Button>
              </div>
              <div v-else-if="pipelineStatus.status === 'processing'" class="text-center py-4">
                <div class="flex items-center justify-center gap-2 mb-4">
                  <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"/>
                  <span>Processing in progress...</span>
                </div>
                <p class="text-sm text-muted-foreground">The pipeline is currently running. This page will auto-refresh.</p>
              </div>
              <div v-else class="text-center py-4">
                <p class="text-muted-foreground mb-4">Pipeline status: {{ pipelineStatus.status }}</p>
                <Button :disabled="processing" class="cursor-pointer" @click="triggerProcessing">
                  <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
                  Restart Processing
                </Button>
              </div>

              <div v-if="processError" class="text-center py-4">
                <p class="text-destructive mb-2">{{ processError }}</p>
                <Button variant="outline" class="cursor-pointer" @click="triggerProcessing">
                  <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
                  Try Again
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
  </div>
</template>
