<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
import { Icon } from '#components'

// Get runtime config for API base URL
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

// State for processing
const isProcessing = ref(false)
const processingStatus = ref('')
const processingResults = ref<unknown>(null)
const stats = ref<unknown>(null)

// Function to process top stories
async function processTopStories() {
  if (isProcessing.value) return

  isProcessing.value = true
  processingStatus.value = 'Fetching top stories from Hacker News...'
  processingResults.value = null

  try {
    const response = await $fetch(`${apiBase}/api/hn/process-top-stories`, {
      method: 'POST',
      body: { limit: 50 }
    })

    processingResults.value = response
    processingStatus.value = 'Processing completed successfully!'

    // Refresh stats after processing
    await refreshStats()

  } catch (error: unknown) {
    console.error('Failed to process top stories:', error)
    const errorData = error as { data?: { detail?: string }; message?: string }
    processingStatus.value = `Error: ${errorData.data?.detail || errorData.message || 'Unknown error'}`
  } finally {
    isProcessing.value = false
  }
}

// Function to refresh stats
async function refreshStats() {
  try {
    stats.value = await $fetch(`${apiBase}/api/hn/stats`)
  } catch (error) {
    console.error('Failed to refresh stats:', error)
  }
}

// Load initial stats
onMounted(() => {
  refreshStats()
})
</script>

<template>
  <div class="space-y-8">
    <!-- Hero Section -->
    <section class="text-center space-y-6">
      <div class="space-y-4">
        <h1 class="text-4xl font-bold text-foreground">
          <span class="text-orange-600">HN</span>.fm
        </h1>
        <p class="text-lg text-muted-foreground max-w-2xl mx-auto">
          Transform Hacker News stories into engaging audio and visual content.
        </p>
      </div>

      <!-- Main Action -->
      <div class="flex justify-center">
        <Button
          size="lg"
          :disabled="isProcessing"
          class="min-w-[200px] cursor-pointer"
          @click="processTopStories"
        >
          <Icon
            :name="isProcessing ? 'lucide:loader' : 'lucide:zap'"
            class="h-4 w-4 mr-2"
            :class="{ 'animate-spin': isProcessing }"
          />
          {{ isProcessing ? 'Processing...' : 'Process Top Stories' }}
        </Button>
      </div>

      <!-- Processing Status -->
      <div v-if="processingStatus" class="max-w-2xl mx-auto">
        <div class="text-sm text-muted-foreground bg-muted/50 rounded-lg p-4">
          {{ processingStatus }}
        </div>
      </div>

      <!-- Processing Results -->
      <div v-if="processingResults" class="max-w-2xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle class="text-lg">Processing Results</CardTitle>
          </CardHeader>
          <CardContent>
            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span>Total Stories Fetched:</span>
                <span class="font-medium">{{ processingResults.summary.total_fetched }}</span>
              </div>
              <div class="flex justify-between">
                <span>Queued for Processing:</span>
                <span class="font-medium text-green-600">{{ processingResults.summary.queued_for_processing }}</span>
              </div>
              <div class="flex justify-between">
                <span>Already Processed:</span>
                <span class="font-medium text-blue-600">{{ processingResults.summary.skipped_already_processed }}</span>
              </div>
              <div v-if="processingResults.summary.failed_to_queue > 0" class="flex justify-between">
                <span>Failed to Queue:</span>
                <span class="font-medium text-red-600">{{ processingResults.summary.failed_to_queue }}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </section>

    <!-- Quick Actions -->
    <section class="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto">
      <Card class="p-6">
        <CardHeader>
          <CardTitle class="flex items-center space-x-2">
            <Icon name="lucide:list" class="h-5 w-5 text-orange-600" />
            <span>Browse Content</span>
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-4">
          <p class="text-muted-foreground">
            View and manage all processed Hacker News stories.
          </p>
          <Button variant="outline" class="w-full cursor-pointer" @click="navigateTo('/items')">
            <Icon name="lucide:arrow-right" class="h-4 w-4 mr-2" />
            View All Items
          </Button>
        </CardContent>
      </Card>

      <Card class="p-6">
        <CardHeader>
          <CardTitle class="flex items-center space-x-2">
            <Icon name="lucide:settings" class="h-5 w-5 text-orange-600" />
            <span>System Status</span>
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-4">
          <p class="text-muted-foreground">
            Monitor services and processing pipeline status.
          </p>
          <Button variant="outline" class="w-full cursor-pointer" @click="navigateTo('/services')">
            <Icon name="lucide:arrow-right" class="h-4 w-4 mr-2" />
            Check Services
          </Button>
        </CardContent>
      </Card>
    </section>

    <!-- Real Stats Section -->
    <section v-if="stats" class="bg-muted/50 rounded-lg p-8 max-w-4xl mx-auto">
      <h2 class="text-2xl font-bold text-center mb-6">System Overview</h2>
      <div class="grid md:grid-cols-3 gap-6 text-center">
        <div>
          <div class="text-3xl font-bold text-foreground">{{ stats.total_items || 0 }}</div>
          <div class="text-sm text-muted-foreground">Total Items</div>
        </div>
        <div>
          <div class="text-3xl font-bold text-foreground">{{ stats.processed_items || 0 }}</div>
          <div class="text-sm text-muted-foreground">Processed Items</div>
        </div>
        <div>
          <div class="text-3xl font-bold text-foreground">{{ stats.pending_items || 0 }}</div>
          <div class="text-sm text-muted-foreground">Pending Items</div>
        </div>
      </div>
    </section>

    <!-- Pipeline Dashboard -->
    <section>
      <PipelineDashboard />
    </section>
  </div>
</template>
