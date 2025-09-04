<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Debug indicator -->
    <div class="bg-blue-100 border border-blue-300 text-blue-800 px-4 py-2 rounded mb-4">
      🐛 RUN DETAIL PAGE - Item: {{ itemId }}, Run: {{ runId }}
    </div>

    <div class="mb-6">
      <NuxtLink
        :to="`/hn/item/${itemId}`"
        class="text-primary hover:text-primary/80 font-medium"
      >
        ← Back to Item {{ itemId }}
      </NuxtLink>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"/>
      <p class="mt-2 text-muted-foreground">Loading run details...</p>
    </div>

    <div v-else-if="!!error" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
      {{ error }}
    </div>

    <div v-if="deleteMessage" class="bg-green-100 border border-green-300 text-green-800 px-4 py-3 rounded mb-4">
      {{ deleteMessage }}
    </div>

    <div v-else-if="!!item && !!run" class="space-y-6">
      <!-- Item Info -->
      <div class="bg-card border rounded-lg p-6">
        <h1 class="text-3xl font-bold mb-4">{{ item.title || 'No Title' }}</h1>

        <div class="flex flex-wrap gap-2 mb-4 items-center justify-between">
          <div class="flex flex-wrap gap-2">
            <Badge class="bg-orange-500 text-white border-orange-500 text-sm">
              Item ID: {{ item.id }}
            </Badge>
            <Badge class="bg-blue-500 text-white border-blue-500 text-sm">
              Run: {{ run.run }}
            </Badge>
            <Badge class="bg-green-500 text-white border-green-500 text-sm">
              {{ formatDateTime(run.created_at) }}
            </Badge>
          </div>
          <Button
            variant="destructive"
            size="sm"
            :disabled="isDeleting"
            class="ml-auto bg-red-600 hover:bg-red-700 text-white border-red-600"
            @click="deleteRun"
          >
            <span v-if="isDeleting">Deleting...</span>
            <span v-else>🗑️ Delete Run</span>
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

      <!-- Run Content with Accordions -->
      <div class="bg-card border rounded-lg p-6">
        <Accordion type="single" collapsible class="w-full">
          <AccordionItem value="run-content">
            <AccordionTrigger class="text-2xl font-bold">
              Run Content
            </AccordionTrigger>
            <AccordionContent>
              <Accordion type="single" collapsible class="w-full">
                <AccordionItem value="raw">
                  <AccordionTrigger class="text-lg font-semibold">
                    Raw Scraped Content
                  </AccordionTrigger>
                  <AccordionContent>
                    <div class="bg-muted/50 p-4 rounded-lg">
                      <pre class="whitespace-pre-wrap text-sm text-foreground font-mono overflow-x-auto">{{ run.content_raw }}</pre>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="clean">
                  <AccordionTrigger class="text-lg font-semibold">
                    Cleaned Content
                  </AccordionTrigger>
                  <AccordionContent>
                    <div class="bg-muted/50 p-4 rounded-lg">
                      <pre class="whitespace-pre-wrap text-sm text-foreground font-mono overflow-x-auto">{{ run.content_clean }}</pre>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="summary">
                  <AccordionTrigger class="text-lg font-semibold">
                    LLM Summary
                  </AccordionTrigger>
                  <AccordionContent>
                    <div class="bg-muted/50 p-4 rounded-lg">
                      <p class="text-foreground leading-relaxed">{{ run.summary }}</p>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="short-description">
                  <AccordionTrigger class="text-lg font-semibold">
                    Short Description
                  </AccordionTrigger>
                  <AccordionContent>
                    <div class="bg-muted/50 p-4 rounded-lg">
                      <p class="text-foreground leading-relaxed">{{ run.short_description }}</p>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="tags">
                  <AccordionTrigger class="text-lg font-semibold">
                    Tags
                  </AccordionTrigger>
                  <AccordionContent>
                    <div class="bg-muted/50 p-4 rounded-lg">
                      <div class="flex flex-wrap gap-2">
                        <Badge
                          v-for="tag in run.tags"
                          :key="tag"
                          class="bg-blue-100 text-blue-800 border-blue-200 text-sm"
                        >
                          #{{ tag }}
                        </Badge>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="emoji">
                  <AccordionTrigger class="text-lg font-semibold">
                    Emoji
                  </AccordionTrigger>
                  <AccordionContent>
                    <div class="bg-muted/50 p-4 rounded-lg">
                      <div class="flex gap-4 text-4xl">
                        <span v-for="emoji in run.emoji" :key="emoji">{{ emoji }}</span>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="haiku">
                  <AccordionTrigger class="text-lg font-semibold">
                    Haiku
                  </AccordionTrigger>
                  <AccordionContent>
                    <div class="bg-muted/50 p-4 rounded-lg">
                      <div class="text-center">
                        <p class="text-foreground leading-relaxed text-lg italic whitespace-pre-line">{{ run.haiku }}</p>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>

      <!-- Segments Section -->
      <div class="bg-card border rounded-lg p-6">
        <div class="flex items-center justify-between mb-6">
          <h2 class="text-2xl font-bold">Segments</h2>
          <Button
            :disabled="isCreatingSegment"
            class="bg-green-600 hover:bg-green-700 text-white border-green-600"
            @click="createSegment"
          >
            <span v-if="isCreatingSegment">Creating...</span>
            <span v-else>🎬 Start New Segment</span>
          </Button>
        </div>

        <div v-if="segmentsLoading" class="text-center py-4">
          <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto"/>
          <p class="mt-2 text-muted-foreground text-sm">Loading segments...</p>
        </div>

        <div v-else-if="segmentsError" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
          {{ segmentsError }}
        </div>

        <div v-else-if="segments.length === 0" class="text-center py-8 text-muted-foreground">
          <p>No segments yet. Create your first segment to get started!</p>
        </div>

        <div v-else class="space-y-4">
          <div
            v-for="segment in segments"
            :key="segment.seg"
            class="border rounded-lg p-4 hover:bg-muted/50 transition-colors"
          >
            <div class="flex items-center justify-between">
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-2">
                  <Badge class="bg-purple-500 text-white border-purple-500 text-sm">
                    Segment {{ segment.seg }}
                  </Badge>
                </div>
                <p class="text-sm text-muted-foreground mb-2">{{ segment.script_preview }}</p>
              </div>
              <div class="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  class="text-primary border-primary hover:bg-primary hover:text-white"
                  @click="viewSegment(segment.seg)"
                >
                  View
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Run Metadata -->
      <div class="bg-card border rounded-lg p-6">
        <h3 class="text-xl font-bold mb-4">Run Metadata</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-muted-foreground">Source URL</label>
            <p class="text-foreground break-all">{{ run.source_url }}</p>
          </div>
          <div>
            <label class="text-sm font-medium text-muted-foreground">Created At</label>
            <p class="text-foreground">{{ formatDateTime(run.created_at) }}</p>
          </div>
          <div>
            <label class="text-sm font-medium text-muted-foreground">Raw Content Length</label>
            <p class="text-foreground">{{ run.content_raw.length }} characters</p>
          </div>
          <div>
            <label class="text-sm font-medium text-muted-foreground">Clean Content Length</label>
            <p class="text-foreground">{{ run.content_clean.length }} characters</p>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-8 text-muted-foreground">
      Run not found
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

// Debug logging
console.log('Run detail page - Route params:', route.params)
console.log('Run detail page - Route path:', route.path)
console.log('Run detail page - Item ID:', itemId.value, 'Run ID:', runId.value)

// Data
const item = ref(null)
const run = ref(null)
const isLoading = ref(true)
const error = ref(null)
const isDeleting = ref(false)
const deleteMessage = ref('')

// Segments data
const segments = ref([])
const segmentsLoading = ref(false)
const segmentsError = ref(null)
const isCreatingSegment = ref(false)

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

const { data: runData, pending: runLoading, error: runError } = await useAsyncData(
  `hn-run-${itemId.value}-${runId.value}`,
  async () => {
    try {
      const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}`)
      return response
    } catch (err) {
      console.error('API error fetching run:', err)
      throw err
    }
  },
  {
    default: () => null
  }
)

// Set reactive data
item.value = itemData.value
run.value = runData.value
isLoading.value = itemLoading.value || runLoading.value
error.value = itemError.value || runError.value

// Watch for data changes
watch([itemData, runData], ([newItem, newRun]) => {
  item.value = newItem
  run.value = newRun
})

watch([itemLoading, runLoading], ([itemLoad, runLoad]) => {
  isLoading.value = itemLoad || runLoad
})

watch([itemError, runError], ([itemErr, runErr]) => {
  error.value = itemErr || runErr
})

// Fetch segments
async function fetchSegments() {
  segmentsLoading.value = true
  segmentsError.value = null

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments`)
    segments.value = response.segments || []
  } catch (err) {
    console.error('Failed to fetch segments:', err)
    segmentsError.value = 'Failed to load segments'
  } finally {
    segmentsLoading.value = false
  }
}

// Create a new segment
async function createSegment() {
  if (isCreatingSegment.value) return

  isCreatingSegment.value = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments`, {
      method: 'POST'
    })

    console.log('Segment created:', response)

    // Refresh segments list
    await fetchSegments()

  } catch (err) {
    console.error('Failed to create segment:', err)
    segmentsError.value = 'Failed to create segment'
  } finally {
    isCreatingSegment.value = false
  }
}

// View a segment
function viewSegment(segmentId) {
  navigateTo(`/hn/item/${itemId.value}/run/${runId.value}/segment/${segmentId}`)
}

// Load segments when component mounts
onMounted(() => {
  fetchSegments()
})

function formatDateTime(dateString) {
  if (!dateString) return 'Unknown'

  const date = new Date(dateString)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}

async function deleteRun() {
  if (isDeleting.value) return

  isDeleting.value = true
  deleteMessage.value = ''

  try {
    await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}`, {
      method: 'DELETE'
    })

    deleteMessage.value = 'Run deleted successfully!'

    // Redirect to item detail page after a short delay
    setTimeout(() => {
      navigateTo(`/hn/item/${itemId.value}`)
    }, 1000)

  } catch (err) {
    console.error('Failed to delete run:', err)
    deleteMessage.value = 'Failed to delete run. Please try again.'
  } finally {
    isDeleting.value = false
  }
}
</script>
