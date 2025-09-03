<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
import { Button } from '~/components/ui/button'
import { Icon } from '#components'

interface PipelineStats {
  total_items: number
  processing_items: number
  completed_items: number
  failed_items: number
  pending_items: number
}

interface ContentItem {
  status: string
}

const stats = ref<PipelineStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

// Get runtime config for API base URL
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const fetchStats = async () => {
  try {
    loading.value = true
    error.value = null

    // Fetch content list to get basic stats
    const contentData = await $fetch(`${apiBase}/api/content?per_page=100`) as { items: ContentItem[] }

    // Calculate stats from content data
    const total = contentData.items.length
    const processing = contentData.items.filter((item: ContentItem) => item.status === 'processing').length
    const completed = contentData.items.filter((item: ContentItem) => item.status === 'completed').length
    const failed = contentData.items.filter((item: ContentItem) => item.status === 'failed').length
    const pending = contentData.items.filter((item: ContentItem) => item.status === 'pending').length

    stats.value = {
      total_items: total,
      processing_items: processing,
      completed_items: completed,
      failed_items: failed,
      pending_items: pending
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch pipeline stats'
    console.error('Error fetching pipeline stats:', err)
  } finally {
    loading.value = false
  }
}

const refreshStats = () => {
  fetchStats()
}

onMounted(() => {
  fetchStats()

  // Auto-refresh every 30 seconds
  setInterval(fetchStats, 30000)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-2xl font-bold text-foreground">Pipeline Dashboard</h2>
        <p class="text-muted-foreground">Overview of content processing pipeline</p>
      </div>
      <Button variant="outline" size="sm" :disabled="loading" class="cursor-pointer" @click="refreshStats">
        <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" :class="{ 'animate-spin': loading }" />
        Refresh
      </Button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"/>
      <span class="ml-2 text-muted-foreground">Loading pipeline stats...</span>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-center py-8">
      <div class="text-destructive mb-2">
        <Icon name="lucide:alert-circle" class="h-8 w-8 mx-auto" />
      </div>
      <p class="text-muted-foreground">{{ error }}</p>
      <Button variant="outline" class="mt-4 cursor-pointer" @click="refreshStats">
        <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
        Try Again
      </Button>
    </div>

    <!-- Stats Grid -->
    <div v-else-if="stats" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <!-- Total Items -->
      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Total Items</CardTitle>
          <Icon name="lucide:file-text" class="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div class="text-2xl font-bold">{{ stats.total_items }}</div>
          <p class="text-xs text-muted-foreground">All content items</p>
        </CardContent>
      </Card>

      <!-- Processing Items -->
      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Processing</CardTitle>
          <Icon name="lucide:loader" class="h-4 w-4 text-blue-600 animate-spin" />
        </CardHeader>
        <CardContent>
          <div class="text-2xl font-bold text-blue-600">{{ stats.processing_items }}</div>
          <p class="text-xs text-muted-foreground">Currently processing</p>
        </CardContent>
      </Card>

      <!-- Completed Items -->
      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Completed</CardTitle>
          <Icon name="lucide:check-circle" class="h-4 w-4 text-green-600" />
        </CardHeader>
        <CardContent>
          <div class="text-2xl font-bold text-green-600">{{ stats.completed_items }}</div>
          <p class="text-xs text-muted-foreground">Successfully processed</p>
        </CardContent>
      </Card>

      <!-- Failed Items -->
      <Card>
        <CardHeader class="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle class="text-sm font-medium">Failed</CardTitle>
          <Icon name="lucide:x-circle" class="h-4 w-4 text-red-600" />
        </CardHeader>
        <CardContent>
          <div class="text-2xl font-bold text-red-600">{{ stats.failed_items }}</div>
          <p class="text-xs text-muted-foreground">Processing failed</p>
        </CardContent>
      </Card>
    </div>

    <!-- Quick Actions -->
    <Card>
      <CardHeader>
        <CardTitle class="flex items-center gap-2">
          <Icon name="lucide:zap" class="h-5 w-5 text-orange-600" />
          Quick Actions
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" class="cursor-pointer" @click="navigateTo('/hn/items')">
            <Icon name="lucide:list" class="h-4 w-4 mr-2" />
            View All Items
          </Button>
          <Button variant="outline" size="sm" class="cursor-pointer" @click="navigateTo('/services')">
            <Icon name="lucide:settings" class="h-4 w-4 mr-2" />
            Service Status
          </Button>
          <Button variant="outline" size="sm" class="cursor-pointer" @click="refreshStats">
            <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
            Refresh Stats
          </Button>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
