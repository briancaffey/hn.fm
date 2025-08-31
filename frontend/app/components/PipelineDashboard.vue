<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Icon } from '#components'

interface PipelineStats {
  total_items: number
  processing_items: number
  completed_items: number
  failed_items: number
  pending_items: number
  service_locks: Record<string, boolean>
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
    const contentData = await $fetch(`${apiBase}/api/content?per_page=100`)

    // Calculate stats from content data
    const total = contentData.items.length
    const processing = contentData.items.filter(item => item.status === 'processing').length
    const completed = contentData.items.filter(item => item.status === 'completed').length
    const failed = contentData.items.filter(item => item.status === 'failed').length
    const pending = contentData.items.filter(item => item.status === 'pending').length

    // Try to get service lock status
    let serviceLocks = {}
    try {
      const lockData = await $fetch(`${apiBase}/api/enhanced-pipeline/service-locks`)
      if (lockData.services) {
        serviceLocks = Object.fromEntries(
          Object.entries(lockData.services).map(([key, value]: [string, any]) => [key, value.is_locked])
        )
      }
    } catch (err) {
      console.log('Service locks not available:', err)
    }

    stats.value = {
      total_items: total,
      processing_items: processing,
      completed_items: completed,
      failed_items: failed,
      pending_items: pending,
      service_locks: serviceLocks
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch pipeline stats'
    console.error('Error fetching pipeline stats:', err)
  } finally {
    loading.value = false
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'processing':
      return 'text-blue-600'
    case 'completed':
      return 'text-green-600'
    case 'failed':
      return 'text-red-600'
    case 'pending':
      return 'text-yellow-600'
    default:
      return 'text-gray-600'
  }
}

const getServiceStatusColor = (isLocked: boolean) => {
  return isLocked ? 'text-red-600' : 'text-green-600'
}

const getServiceStatusIcon = (isLocked: boolean) => {
  return isLocked ? 'lucide:lock' : 'lucide:unlock'
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
      <Button @click="refreshStats" variant="outline" size="sm" :disabled="loading">
        <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" :class="{ 'animate-spin': loading }" />
        Refresh
      </Button>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      <span class="ml-2 text-muted-foreground">Loading pipeline stats...</span>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-center py-8">
      <div class="text-destructive mb-2">
        <Icon name="lucide:alert-circle" class="h-8 w-8 mx-auto" />
      </div>
      <p class="text-muted-foreground">{{ error }}</p>
      <Button @click="refreshStats" variant="outline" class="mt-4">
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
          <Icon name="lucide:loader-2" class="h-4 w-4 text-blue-600 animate-spin" />
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

    <!-- Service Status -->
    <Card v-if="stats && Object.keys(stats.service_locks).length > 0">
      <CardHeader>
        <CardTitle class="flex items-center gap-2">
          <Icon name="lucide:server" class="h-5 w-5" />
          Service Status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          <div
            v-for="(isLocked, serviceName) in stats.service_locks"
            :key="serviceName"
            class="flex items-center gap-2 p-3 border rounded-lg"
          >
            <Icon
              :name="getServiceStatusIcon(isLocked)"
              class="h-4 w-4"
              :class="getServiceStatusColor(isLocked)"
            />
            <div>
              <p class="text-sm font-medium">{{ serviceName }}</p>
              <p class="text-xs text-muted-foreground">
                {{ isLocked ? 'Locked' : 'Available' }}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>

    <!-- Quick Actions -->
    <Card>
      <CardHeader>
        <CardTitle class="flex items-center gap-2">
          <Icon name="lucide:zap" class="h-5 w-5" />
          Quick Actions
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div class="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" @click="navigateTo('/items')">
            <Icon name="lucide:list" class="h-4 w-4 mr-2" />
            View All Items
          </Button>
          <Button variant="outline" size="sm" @click="navigateTo('/services')">
            <Icon name="lucide:settings" class="h-4 w-4 mr-2" />
            Service Status
          </Button>
          <Button variant="outline" size="sm" @click="refreshStats">
            <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
            Refresh Stats
          </Button>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
