<template>
  <div class="container mx-auto px-4 py-8">
    <div class="mb-6">
      <NuxtLink
        :to="`/hn/item/${itemId}/run/${runId}`"
        class="text-primary hover:text-primary/80 font-medium"
      >
        ← Back to Run {{ runId }}
      </NuxtLink>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"/>
      <p class="mt-2 text-muted-foreground">Loading segment details...</p>
    </div>

    <div v-else-if="!!error" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
      {{ error }}
    </div>

    <div v-if="deleteMessage" class="bg-green-100 border border-green-300 text-green-800 px-4 py-3 rounded mb-4">
      {{ deleteMessage }}
    </div>

    <div v-else-if="!!item && !!segment" class="space-y-6">
      <!-- Item Info -->
      <div class="bg-card border rounded-lg p-6">
        <h1 class="text-3xl font-bold mb-4">{{ item.title || 'No Title' }}</h1>

        <div class="flex flex-wrap gap-2 mb-4 items-center justify-between">
          <div class="flex flex-wrap gap-2">
            <Badge class="bg-orange-500 text-white border-orange-500 text-sm">
              Item ID: {{ item.id }}
            </Badge>
            <Badge class="bg-blue-500 text-white border-blue-500 text-sm">
              Run: {{ segment.run }}
            </Badge>
            <Badge class="bg-purple-500 text-white border-purple-500 text-sm">
              Segment: {{ segment.seg }}
            </Badge>
            <Badge class="bg-green-500 text-white border-green-500 text-sm">
              {{ formatDateTime(segment.created_at) }}
            </Badge>
          </div>
          <Button
            variant="destructive"
            size="sm"
            :disabled="isDeleting"
            class="ml-auto bg-red-600 hover:bg-red-700 text-white border-red-600"
            @click="deleteSegment"
          >
            <span v-if="isDeleting">Deleting...</span>
            <span v-else>🗑️ Delete Segment</span>
          </Button>
        </div>

        <div v-if="item.url" class="mb-4">
          <a
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary hover:text-primary/80 font-medium break-all"
          >
            🔗 {{ item.url }}
          </a>
        </div>
      </div>

      <!-- Segment Content with Accordions -->
      <div class="bg-card border rounded-lg p-6">
        <h2 class="text-2xl font-bold mb-6">Segment Content</h2>

        <Accordion type="single" collapsible class="w-full" :default-value="'script'">
          <AccordionItem value="script">
            <AccordionTrigger class="text-lg font-semibold">
              Script (Full Text)
            </AccordionTrigger>
            <AccordionContent>
              <div class="bg-muted/50 p-4 rounded-lg">
                <pre class="whitespace-pre-wrap text-sm text-foreground font-mono overflow-x-auto">{{ segment.script }}</pre>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>

      <!-- Narration Sections -->
      <div class="bg-card border rounded-lg p-6">
        <Accordion type="single" collapsible class="w-full" :default-value="'narration-sections'">
          <AccordionItem value="narration-sections">
            <AccordionTrigger class="text-lg font-semibold">
              <div class="flex items-center justify-between w-full">
                <span>Narration Sections</span>
                <div class="flex items-center gap-2">
                  <Badge v-if="segment.audio_ready" class="bg-green-500 text-white border-green-500 text-xs">
                    Audio Ready
                  </Badge>
                  <Badge v-else class="bg-yellow-500 text-white border-yellow-500 text-xs">
                    No Audio
                  </Badge>
                  <Button
                    :disabled="isBuildingAudio"
                    size="sm"
                    class="bg-blue-600 hover:bg-blue-700 text-white border-blue-600"
                    @click.stop="buildAllAudio"
                  >
                    <span v-if="isBuildingAudio">Building...</span>
                    <span v-else>🎵 Build All</span>
                  </Button>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div v-if="sectionsLoading" class="text-center py-4">
                <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto"/>
                <p class="mt-2 text-muted-foreground text-sm">Loading sections...</p>
              </div>

              <div v-else-if="sectionsError" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
                {{ sectionsError }}
              </div>

              <div v-else-if="sections.length === 0" class="text-center py-8 text-muted-foreground">
                <p>No sections yet. Click "Build All" to generate audio sections from the script.</p>
              </div>

              <div v-else class="space-y-4">
                <div
                  v-for="section in sections"
                  :key="section.section"
                  class="border rounded-lg p-4 bg-muted/30"
                >
                  <div class="flex items-start justify-between mb-3">
                    <h4 class="text-lg font-semibold">Section {{ section.section }}</h4>
                    <div class="flex items-center gap-2">
                      <Badge v-if="section.cleaned" class="bg-green-100 text-green-800 border-green-200 text-xs">
                        Cleaned
                      </Badge>
                      <span v-if="section.duration_ms" class="text-sm text-muted-foreground">
                        {{ (section.duration_ms / 1000).toFixed(1) }}s
                      </span>
                    </div>
                  </div>

                  <div class="space-y-3">
                    <div>
                      <label class="text-sm font-medium text-muted-foreground mb-1 block">Text</label>
                      <textarea
                        v-model="section.text"
                        class="w-full p-3 border rounded-lg bg-background text-foreground font-mono text-sm"
                        rows="3"
                        @input="markSectionAsDirty(section.section)"
                      />
                    </div>

                    <div class="flex items-center gap-2">
                      <Button
                        :disabled="isRegeneratingSection === section.section"
                        size="sm"
                        variant="outline"
                        class="text-primary border-primary hover:bg-primary hover:text-white"
                        @click="regenerateSection(section.section)"
                      >
                        <span v-if="isRegeneratingSection === section.section">Regenerating...</span>
                        <span v-else>🔄 Regenerate</span>
                      </Button>

                      <div v-if="section.audio_path" class="flex items-center gap-2">
                        <audio controls class="h-8">
                          <source :src="getAudioUrl(section.audio_path)" type="audio/wav" >
                          Your browser does not support the audio element.
                        </audio>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="combined-audio">
            <AccordionTrigger class="text-lg font-semibold">
              Combined Audio
            </AccordionTrigger>
            <AccordionContent>
              <div v-if="segment.audio_ready && segment.audio_combined_path" class="space-y-4">
                <div class="flex items-center gap-4">
                  <audio controls class="w-full">
                    <source :src="getAudioUrl(segment.audio_combined_path)" type="audio/wav" >
                    Your browser does not support the audio element.
                  </audio>
                </div>
                <div class="text-sm text-muted-foreground">
                  <p>Total sections: {{ segment.sections_total }}</p>
                  <p>Combined audio file: {{ segment.audio_combined_path }}</p>
                </div>
              </div>
              <div v-else class="text-center py-8 text-muted-foreground">
                <p>Combined audio not built yet. Generate individual sections first.</p>
              </div>
            </AccordionContent>
          </AccordionItem>

          <AccordionItem value="asr">
            <AccordionTrigger class="text-lg font-semibold">
              <div class="flex items-center justify-between w-full">
                <span>ASR (Word Timestamps)</span>
                <div class="flex items-center gap-2">
                  <Button
                    :disabled="isRefreshingAsr"
                    size="sm"
                    variant="outline"
                    class="text-primary border-primary hover:bg-primary hover:text-white"
                    @click.stop="refreshAsr"
                  >
                    <span v-if="isRefreshingAsr">Refreshing...</span>
                    <span v-else>🔄 Refresh</span>
                  </Button>
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div v-if="asrData" class="space-y-4">
                <div class="bg-muted/50 p-4 rounded-lg">
                  <pre class="whitespace-pre-wrap text-sm text-foreground font-mono overflow-x-auto">{{ JSON.stringify(asrData.asr, null, 2) }}</pre>
                </div>
              </div>
              <div v-else class="text-center py-8 text-muted-foreground">
                <p>ASR not ready yet.</p>
              </div>
            </AccordionContent>
          </AccordionItem>

          <!-- Images Accordion Item -->
          <AccordionItem value="images">
            <AccordionTrigger class="text-lg font-semibold">
              Images
            </AccordionTrigger>
            <AccordionContent>
              <div class="mb-4 flex justify-end">
                <Button
                  v-if="segment.script && !isGeneratingImages"
                  size="sm"
                  @click="generateImages"
                  class="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  Generate Images
                </Button>
                <div v-if="isGeneratingImages" class="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              </div>

              <div v-if="images.length > 0" class="space-y-4">
                <div v-for="image in images" :key="image.index" class="border rounded-lg p-4">
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Image Preview -->
                    <div class="space-y-2">
                      <h4 class="font-medium">Image {{ image.index }}</h4>
                      <div class="relative">
                        <img
                          :src="getImageUrl(image.image_path, image.index)"
                          :alt="`Image for section ${image.index}`"
                          class="w-full h-48 object-cover rounded-lg border"
                          @error="handleImageError"
                        />
                      </div>
                      <div v-if="image.start_ms !== null && image.duration_ms !== null" class="text-sm text-muted-foreground">
                        Start: {{ (image.start_ms / 1000).toFixed(1) }}s · Duration: {{ (image.duration_ms / 1000).toFixed(1) }}s
                      </div>
                    </div>

                    <!-- Text and Prompt -->
                    <div class="space-y-3">
                      <div>
                        <label class="text-sm font-medium text-muted-foreground">Line Text</label>
                        <textarea
                          v-model="imageEdits[image.index]"
                          class="w-full h-16 p-2 border rounded text-sm resize-none"
                          :placeholder="image.line_text"
                        ></textarea>
                      </div>

                      <div>
                        <details class="group">
                          <summary class="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground">
                            Prompt
                          </summary>
                          <div class="mt-2 p-3 bg-muted/50 rounded text-sm font-mono whitespace-pre-wrap">{{ image.prompt }}</div>
                        </details>
                      </div>

                      <div>
                        <label class="text-sm font-medium text-muted-foreground">Custom Prompt (optional)</label>
                        <textarea
                          v-model="promptEdits[image.index]"
                          class="w-full h-16 p-2 border rounded text-sm resize-none"
                          placeholder="Override the generated prompt..."
                        ></textarea>
                      </div>

                      <Button
                        size="sm"
                        @click="regenerateImage(image.index)"
                        :disabled="isRegenerating[image.index]"
                        class="w-full bg-green-600 hover:bg-green-700 text-white"
                      >
                        <div v-if="isRegenerating[image.index]" class="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                        Regenerate Image
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="text-center py-8 text-muted-foreground">
                <p>No images yet. Click 'Generate Images' to create them.</p>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>
    </div>

    <div v-else class="text-center py-8 text-muted-foreground">
      Segment not found
    </div>
  </div>
</template>

<script setup>
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '~/components/ui/accordion'

// Define page meta to ensure proper routing
definePageMeta({
  layout: 'default'
})

const route = useRoute()
const config = useRuntimeConfig()

// Extract parameters with better error handling
const itemId = computed(() => {
  const id = route.params.id
  console.log('Raw item ID param:', id, 'Type:', typeof id)
  return parseInt(Array.isArray(id) ? id[0] : id)
})

const runId = computed(() => {
  const run = route.params.runId
  console.log('Raw run ID param:', run, 'Type:', typeof run)
  return parseInt(Array.isArray(run) ? run[0] : run)
})

const segId = computed(() => {
  const seg = route.params.segId
  console.log('Raw segment ID param:', seg, 'Type:', typeof seg)
  return parseInt(Array.isArray(seg) ? seg[0] : seg)
})

// Debug logging
console.log('Segment detail page - Route params:', route.params)
console.log('Segment detail page - Route path:', route.path)
console.log('Segment detail page - Item ID:', itemId.value, 'Run ID:', runId.value, 'Segment ID:', segId.value)

// Data
const item = ref(null)
const segment = ref(null)
const isLoading = ref(true)
const error = ref(null)
const isDeleting = ref(false)
const deleteMessage = ref('')

// Audio sections data
const sections = ref([])
const sectionsLoading = ref(false)
const sectionsError = ref(null)
const isBuildingAudio = ref(false)
const isRegeneratingSection = ref(null)
const dirtySections = ref(new Set())

// ASR data
const asrData = ref(null)
const isRefreshingAsr = ref(false)

// Image data
const images = ref([])
const isGeneratingImages = ref(false)
const isRegenerating = ref({})
const imageEdits = ref({})
const promptEdits = ref({})

// Fetch data
const { data: itemData, pending: itemLoading, error: itemError } = await useAsyncData(
  `hn-item-${itemId.value}`,
  async () => {
    try {
      const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}`)
      return response
    } catch (err) {
      console.error('API error fetching item:', err)
      throw err
    }
  },
  {
    default: () => null
  }
)

const { data: segmentData, pending: segmentLoading, error: segmentError } = await useAsyncData(
  `hn-segment-${itemId.value}-${runId.value}-${segId.value}`,
  async () => {
    try {
      const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}`)
      return response
    } catch (err) {
      console.error('API error fetching segment:', err)
      throw err
    }
  },
  {
    default: () => null
  }
)

// ASR data fetching
const { data: asrDataResponse, refresh: refreshAsrData } = await useFetch(
  `${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/asr`,
  {
    key: `asr-${itemId.value}-${runId.value}-${segId.value}`,
    server: true,
    default: () => null
  }
).catch(() => ({ data: null }))

// Set reactive data
item.value = itemData.value
segment.value = segmentData.value
asrData.value = asrDataResponse.value
isLoading.value = itemLoading.value || segmentLoading.value
error.value = itemError.value || segmentError.value

// Watch for data changes - simplified to prevent multiple renders
watch([itemData, segmentData], ([newItem, newSegment]) => {
  if (newItem !== item.value) item.value = newItem
  if (newSegment !== segment.value) segment.value = newSegment
}, { immediate: false })

watch(asrDataResponse, (newAsrData) => {
  if (newAsrData !== asrData.value) asrData.value = newAsrData
}, { immediate: false })

watch([itemLoading, segmentLoading], ([itemLoad, segmentLoad]) => {
  const newLoading = itemLoad || segmentLoad
  if (newLoading !== isLoading.value) isLoading.value = newLoading
}, { immediate: false })

watch([itemError, segmentError], ([itemErr, segmentErr]) => {
  const newError = itemErr || segmentErr
  if (newError !== error.value) error.value = newError
}, { immediate: false })

function formatDateTime(dateString) {
  if (!dateString) return 'Unknown'

  const date = new Date(dateString)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}

async function deleteSegment() {
  if (isDeleting.value) return

  isDeleting.value = true
  deleteMessage.value = ''

  try {
    await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}`, {
      method: 'DELETE'
    })

    deleteMessage.value = 'Segment deleted successfully!'

    // Redirect to run detail page after a short delay
    setTimeout(() => {
      navigateTo(`/hn/item/${itemId.value}/run/${runId.value}`)
    }, 1000)

  } catch (err) {
    console.error('Failed to delete segment:', err)
    deleteMessage.value = 'Failed to delete segment. Please try again.'
  } finally {
    isDeleting.value = false
  }
}

// Audio functions
async function fetchSections() {
  sectionsLoading.value = true
  sectionsError.value = null

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/sections`)
    sections.value = response.sections || []
  } catch (err) {
    console.error('Failed to fetch sections:', err)
    sectionsError.value = 'Failed to load sections'
  } finally {
    sectionsLoading.value = false
  }
}

async function buildAllAudio() {
  if (isBuildingAudio.value) return

  isBuildingAudio.value = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/audio`, {
      method: 'POST'
    })

    console.log('Audio build queued:', response)

    // Refresh sections and segment data
    await Promise.all([
      fetchSections(),
      refreshSegment()
    ])

  } catch (err) {
    console.error('Failed to build audio:', err)
    sectionsError.value = 'Failed to queue audio build'
  } finally {
    isBuildingAudio.value = false
  }
}

async function regenerateSection(sectionNumber) {
  if (isRegeneratingSection.value) return

  isRegeneratingSection.value = sectionNumber

  try {
    const section = sections.value.find(s => s.section === sectionNumber)
    if (!section) {
      throw new Error('Section not found')
    }

    const body = dirtySections.value.has(sectionNumber) ? { text: section.text } : {}

    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/sections/${sectionNumber}/audio`, {
      method: 'POST',
      body
    })

    console.log('Section regeneration queued:', response)

    // Refresh sections and segment data
    await Promise.all([
      fetchSections(),
      refreshSegment()
    ])

    // Mark section as clean
    dirtySections.value.delete(sectionNumber)

  } catch (err) {
    console.error('Failed to regenerate section:', err)
    sectionsError.value = 'Failed to queue section regeneration'
  } finally {
    isRegeneratingSection.value = null
  }
}

function markSectionAsDirty(sectionNumber) {
  dirtySections.value.add(sectionNumber)
}

function getAudioUrl(audioPath) {
  if (!audioPath) return ''

  // Convert container path to API endpoint
  // Example: /app/outputs/hn/item/45114003/runs/2/segments/9/audio/segment.wav
  // -> /api/audio/45114003/2/9/segment.wav

  // Example: /app/outputs/hn/item/45114003/runs/2/segments/9/audio/sections/1/audio.wav
  // -> /api/audio/45114003/2/9/section_1.wav

  if (audioPath.includes('/audio/segment.wav')) {
    // Combined segment audio
    const match = audioPath.match(/\/item\/(\d+)\/runs\/(\d+)\/segments\/(\d+)\/audio\/segment\.wav/)
    if (match) {
      const [, itemId, runId, segId] = match
      return `${config.public.apiBase}/api/audio/${itemId}/${runId}/${segId}/segment.wav`
    }
  } else if (audioPath.includes('/sections/') && audioPath.includes('/audio.wav')) {
    // Individual section audio
    const match = audioPath.match(/\/item\/(\d+)\/runs\/(\d+)\/segments\/(\d+)\/audio\/sections\/(\d+)\/audio\.wav/)
    if (match) {
      const [, itemId, runId, segId, sectionNum] = match
      return `${config.public.apiBase}/api/audio/${itemId}/${runId}/${segId}/section_${sectionNum}.wav`
    }
  }

  // Fallback to original logic if pattern doesn't match
  const relativePath = audioPath.replace(/^.*\/outputs\//, '/outputs/')
  return `${config.public.apiBase}${relativePath}`
}

function getImageUrl(imagePath, imageIndex) {
  if (!imagePath) return ''

  // Convert container path to API endpoint
  // Example: /app/outputs/hn/item/45106314/runs/1/segments/1/images/1/image.png
  // -> /api/images/45106314/1/1/1/image.png

  const match = imagePath.match(/\/item\/(\d+)\/runs\/(\d+)\/segments\/(\d+)\/images\/\d+\/image\.png/)
  if (match) {
    const [, itemId, runId, segId] = match
    return `${config.public.apiBase}/api/images/${itemId}/${runId}/${segId}/${imageIndex}/image.png`
  }

  // Fallback to original path if pattern doesn't match
  return imagePath
}

async function refreshSegment() {
  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}`)
    segment.value = response
  } catch (err) {
    console.error('Failed to refresh segment:', err)
  }
}

async function refreshAsr() {
  if (isRefreshingAsr.value) return

  isRefreshingAsr.value = true

  try {
    await refreshAsrData()
  } catch (err) {
    console.error('Failed to refresh ASR data:', err)
  } finally {
    isRefreshingAsr.value = false
  }
}

// Image methods
async function fetchImages() {
  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/images`)
    images.value = response.images || []

    // Initialize edit objects
    images.value.forEach(image => {
      imageEdits.value[image.index] = image.line_text
      promptEdits.value[image.index] = ''
    })
  } catch (err) {
    console.error('Failed to fetch images:', err)
  }
}

async function generateImages() {
  if (isGeneratingImages.value) return

  isGeneratingImages.value = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/images`, {
      method: 'POST'
    })

    console.log('Image generation queued:', response)

    // Poll for completion
    await pollForImages()
  } catch (err) {
    console.error('Failed to generate images:', err)
    error.value = 'Failed to generate images'
  } finally {
    isGeneratingImages.value = false
  }
}

async function pollForImages() {
  const maxAttempts = 30 // 30 seconds max
  let attempts = 0

  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 1000)) // Wait 1 second

    try {
      await fetchImages()

      // Check if we have images now
      if (images.value.length > 0) {
        console.log('Images generated successfully')
        return
      }
    } catch (err) {
      console.error('Error polling for images:', err)
    }

    attempts++
  }

  console.warn('Image generation polling timed out')
}

async function regenerateImage(index) {
  if (isRegenerating.value[index]) return

  isRegenerating.value[index] = true

  try {
    const requestBody = {}

    // Add overrides if they exist
    if (imageEdits.value[index] && imageEdits.value[index] !== images.value.find(img => img.index === index)?.line_text) {
      requestBody.line_text = imageEdits.value[index]
    }

    if (promptEdits.value[index]) {
      requestBody.prompt = promptEdits.value[index]
    }

    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/images/${index}`, {
      method: 'POST',
      body: requestBody
    })

    console.log('Image regeneration queued:', response)

    // Poll for completion
    await pollForImages()
  } catch (err) {
    console.error('Failed to regenerate image:', err)
    error.value = 'Failed to regenerate image'
  } finally {
    isRegenerating.value[index] = false
  }
}

function handleImageError(event) {
  console.error('Image failed to load:', event.target.src)
  event.target.style.display = 'none'
}

// Load sections and images when component mounts
onMounted(() => {
  fetchSections()
  fetchImages()
})
</script>
