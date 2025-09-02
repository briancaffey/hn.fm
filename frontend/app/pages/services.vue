<script setup lang="ts">
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Icon } from '#components'

// Define the service interface
interface Service {
  name: string
  url: string
  status: 'online' | 'offline' | 'error'
  response_time: number
  details?: unknown
  error_message?: string
}

interface ServicesResponse {
  all_healthy: boolean
  timestamp: string
  services: Service[]
}

// Get runtime config for API base URL
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

// Fetch services data
const { data: servicesData, pending, refresh } = await useAsyncData<ServicesResponse>('services', () =>
  $fetch(`${apiBase}/api/services/status`)
)

// Auto-refresh every 30 seconds
onMounted(() => {
  const interval = setInterval(() => {
    refresh()
  }, 30000)

  onUnmounted(() => {
    clearInterval(interval)
  })
})

// Helper functions
const getStatusColor = (status: string) => {
  const colors = {
    'online': 'bg-green-500',
    'offline': 'bg-red-500',
    'error': 'bg-yellow-500'
  }
  return colors[status as keyof typeof colors] || 'bg-gray-500'
}

const getStatusBadgeVariant = (status: string): 'default' | 'destructive' | 'secondary' | 'outline' => {
  const variants: Record<string, 'default' | 'destructive' | 'secondary' | 'outline'> = {
    'online': 'default',
    'offline': 'destructive',
    'error': 'secondary'
  }
  return variants[status] || 'outline'
}

const formatDetails = (details: unknown) => {
  if (typeof details === 'object') {
    try {
      return JSON.stringify(details, null, 2)
    } catch {
      return Object.entries(details as Record<string, unknown>)
        .map(([key, value]) => `${key}: ${value}`)
        .join('\n')
    }
  }
  return String(details)
}

const formatTimestamp = (timestamp: string) => {
  return new Date(timestamp).toLocaleString()
}
</script>

<template>
  <div class="container mx-auto px-4 py-8 max-w-7xl">
    <div class="space-y-8">
      <!-- Page Header -->
      <div class="space-y-2">
        <h1 class="text-3xl font-bold text-foreground">Services Status</h1>
        <p class="text-muted-foreground">
          Monitor the health and availability of all pipeline services.
        </p>
      </div>

    <!-- Overall Status -->
    <Card>
      <CardHeader>
        <div class="flex items-center justify-between">
          <div>
            <CardTitle>Overall Status</CardTitle>
            <p class="text-sm text-muted-foreground">
              Last checked: {{ servicesData?.timestamp ? formatTimestamp(servicesData.timestamp) : '-' }}
            </p>
          </div>
          <div class="flex items-center space-x-3">
            <div
              :class="[
                'w-4 h-4 rounded-full',
                servicesData?.all_healthy ? 'bg-green-500' : 'bg-red-500'
              ]"
            />
            <span
              :class="[
                'text-lg font-medium',
                servicesData?.all_healthy ? 'text-green-600' : 'text-red-600'
              ]"
            >
              {{ pending ? 'Checking...' : (servicesData?.all_healthy ? 'All Services Healthy' : 'Some Services Unhealthy') }}
            </span>
          </div>
        </div>
      </CardHeader>
    </Card>

    <!-- Loading State -->
    <div v-if="pending" class="text-center py-12">
      <div class="flex items-center justify-center space-x-2">
        <Icon name="lucide:loader-2" class="h-6 w-6 animate-spin text-muted-foreground" />
        <span class="text-muted-foreground">Loading services status...</span>
      </div>
    </div>

    <!-- Services Grid -->
    <div v-else-if="servicesData?.services" class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
      <Card v-for="service in servicesData.services" :key="service.name" class="service-card h-fit">
        <CardHeader class="pb-3">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center space-x-3 min-w-0 flex-1">
              <div
                :class="[
                  'w-3 h-3 rounded-full flex-shrink-0',
                  getStatusColor(service.status)
                ]"
              />
              <CardTitle class="text-lg truncate">{{ service.name }}</CardTitle>
            </div>
            <Badge :variant="getStatusBadgeVariant(service.status)" class="flex-shrink-0">
              {{ service.status }}
            </Badge>
          </div>
        </CardHeader>

        <CardContent class="space-y-4">
          <!-- Service Details -->
          <div class="space-y-3 text-sm">
            <div class="space-y-1">
              <span class="font-medium text-muted-foreground">URL:</span>
              <div class="bg-muted/50 p-2 rounded border">
                <code class="text-xs text-foreground break-all block">{{ service.url }}</code>
              </div>
            </div>

            <div class="flex justify-between items-center">
              <span class="font-medium text-muted-foreground">Response Time:</span>
              <span class="text-foreground font-mono">{{ service.response_time.toFixed(3) }}s</span>
            </div>
          </div>

          <!-- Service Details -->
          <div v-if="service.details" class="space-y-2">
            <span class="text-sm font-medium text-muted-foreground">Details:</span>
            <div class="bg-muted p-3 rounded-md border max-h-48 overflow-y-auto">
              <pre class="text-xs text-muted-foreground whitespace-pre-wrap break-words">{{ formatDetails(service.details) }}</pre>
            </div>
          </div>

          <!-- Error Message -->
          <div v-if="service.error_message" class="space-y-2">
            <span class="text-sm font-medium text-destructive">Error:</span>
            <div class="bg-destructive/10 p-3 rounded-md border max-h-32 overflow-y-auto">
              <pre class="text-xs text-destructive whitespace-pre-wrap break-words">{{ service.error_message }}</pre>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- No Data State -->
    <div v-else-if="!pending" class="text-center py-12">
      <Icon name="lucide:alert-circle" class="h-12 w-12 mx-auto text-muted-foreground mb-4" />
      <h3 class="text-lg font-medium text-foreground mb-2">No Services Found</h3>
      <p class="text-muted-foreground">Unable to load services status. Please try again.</p>
    </div>

      <!-- Refresh Button -->
      <div class="flex justify-center">
        <Button
          :disabled="pending"
          variant="outline"
          class="inline-flex items-center space-x-2"
          @click="refresh"
        >
          <Icon
            :name="pending ? 'lucide:loader-2' : 'lucide:refresh-cw'"
            :class="['h-4 w-4', pending && 'animate-spin']"
          />
          <span>{{ pending ? 'Refreshing...' : 'Refresh Services' }}</span>
        </Button>
      </div>
    </div>
  </div>
</template>
