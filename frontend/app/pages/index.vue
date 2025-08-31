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
const processingResults = ref<any>(null)

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

  } catch (error: any) {
    console.error('Failed to process top stories:', error)
    processingStatus.value = `Error: ${error.data?.detail || error.message || 'Unknown error'}`
  } finally {
    isProcessing.value = false
  }
}

// Function to refresh stats
async function refreshStats() {
  try {
    const stats = await $fetch(`${apiBase}/api/hn/stats`)
    // Update the stats display if needed
    console.log('Updated HN stats:', stats)
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
    <section class="text-center space-y-4">
      <h1 class="text-4xl font-bold text-foreground">
        Welcome to HN.fm
      </h1>
      <p class="text-xl text-muted-foreground max-w-2xl mx-auto">
        Your gateway to curated Hacker News content, transformed into engaging audio and visual experiences.
      </p>
      <div class="flex justify-center space-x-4">
        <Button
          size="lg"
          @click="processTopStories"
          :disabled="isProcessing"
          class="min-w-[200px]"
        >
          <Icon
            :name="isProcessing ? 'lucide:loader-2' : 'lucide:zap'"
            class="h-4 w-4 mr-2"
            :class="{ 'animate-spin': isProcessing }"
          />
          {{ isProcessing ? 'Processing...' : 'Process Top Stories' }}
        </Button>
        <Button variant="outline" size="lg">
          <Icon name="lucide:info" class="h-4 w-4 mr-2" />
          Learn More
        </Button>
      </div>

      <!-- Processing Status -->
      <div v-if="processingStatus" class="mt-4">
        <div class="text-sm text-muted-foreground">
          {{ processingStatus }}
        </div>
      </div>

      <!-- Processing Results -->
      <div v-if="processingResults" class="mt-6 max-w-2xl mx-auto">
        <Card class="p-4">
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

    <!-- Pipeline Dashboard -->
    <section>
      <PipelineDashboard />
    </section>

    <!-- Features Grid -->
    <section class="grid md:grid-cols-3 gap-6">
      <Card class="p-6">
        <CardHeader>
          <CardTitle class="flex items-center space-x-2">
            <Icon name="lucide:headphones" class="h-5 w-5 text-primary" />
            <span>Audio Generation</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p class="text-muted-foreground">
            Transform articles into high-quality audio content with natural-sounding voices.
          </p>
        </CardContent>
      </Card>

      <Card class="p-6">
        <CardHeader>
          <CardTitle class="flex items-center space-x-2">
            <Icon name="lucide:image" class="h-5 w-5 text-primary" />
            <span>Visual Content</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p class="text-muted-foreground">
            Generate compelling images and videos to accompany your content.
          </p>
        </CardContent>
      </Card>

      <Card class="p-6">
        <CardHeader>
          <CardTitle class="flex items-center space-x-2">
            <Icon name="lucide:zap" class="h-5 w-5 text-primary" />
            <span>Smart Curation</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p class="text-muted-foreground">
            AI-powered content selection and processing for the best Hacker News stories.
          </p>
        </CardContent>
      </Card>
    </section>

    <!-- Stats Section -->
    <section class="bg-muted/50 rounded-lg p-8">
      <div class="grid md:grid-cols-4 gap-6 text-center">
        <div>
          <div class="text-3xl font-bold text-foreground">1,234</div>
          <div class="text-sm text-muted-foreground">Items Processed</div>
        </div>
        <div>
          <div class="text-3xl font-bold text-foreground">567</div>
          <div class="text-sm text-muted-foreground">Audio Files</div>
        </div>
        <div>
          <div class="text-3xl font-bold text-foreground">89</div>
          <div class="text-sm text-muted-foreground">Videos Created</div>
        </div>
        <div>
          <div class="text-3xl font-bold text-foreground">42</div>
          <div class="text-sm text-muted-foreground">Active Users</div>
        </div>
      </div>
    </section>
  </div>
</template>
