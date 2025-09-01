<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Button } from '~/components/ui/button'
import { Card, CardContent } from '~/components/ui/card'
import { Badge } from '~/components/ui/badge'
import { Icon } from '#components'

interface ContentItem {
  id: string
  title: string
  url: string
  content_type: string
  status: string
  created_at: string
  updated_at: string
  metadata: Record<string, unknown>
  hn_story_data?: {
    score?: number
    descendants?: number
    by?: string
  }
}

interface ContentListResponse {
  items: ContentItem[]
  total: number
  page: number
  per_page: number
  has_next: boolean
  has_prev: boolean
}

const contentItems = ref<ContentItem[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const deleting = ref<string | null>(null)

// Get runtime config for API base URL
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const fetchContent = async () => {
  try {
    loading.value = true
    error.value = null

    const data: ContentListResponse = await $fetch(`${apiBase}/api/content?per_page=20`)
    contentItems.value = data.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch content'
    console.error('Error fetching content:', err)
  } finally {
    loading.value = false
  }
}

const deleteContent = async (itemId: string) => {
  try {
    deleting.value = itemId

    await $fetch(`${apiBase}/api/content/${itemId}`, {
      method: 'DELETE'
    })

    // Remove the item from the list
    contentItems.value = contentItems.value.filter(item => item.id !== itemId)
  } catch (err) {
    console.error('Error deleting content:', err)
    // Silently handle errors - item will remain in the list if deletion fails
  } finally {
    deleting.value = null
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
  const now = new Date()
  const diffInHours = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60))

  if (diffInHours < 1) {
    return 'Just now'
  } else if (diffInHours < 24) {
    return `${diffInHours} hour${diffInHours > 1 ? 's' : ''} ago`
  } else {
    const diffInDays = Math.floor(diffInHours / 24)
    return `${diffInDays} day${diffInDays > 1 ? 's' : ''} ago`
  }
}

const navigateToItem = (itemId: string) => {
  navigateTo(`/items/${itemId}`)
}

onMounted(() => {
  fetchContent()
})
</script>

<template>
  <div class="space-y-4">
    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"/>
      <span class="ml-2 text-muted-foreground">Loading content...</span>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-center py-8">
      <div class="text-destructive mb-2">
        <Icon name="lucide:alert-circle" class="h-8 w-8 mx-auto" />
      </div>
      <p class="text-muted-foreground">{{ error }}</p>
      <Button variant="outline" class="mt-4 cursor-pointer" @click="fetchContent">
        <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
        Try Again
      </Button>
    </div>

    <!-- Content List -->
    <div v-else-if="contentItems.length > 0" class="space-y-3">
      <div v-for="item in contentItems" :key="item.id" class="group">
        <Card class="transition-all duration-200 hover:shadow-md hover:border-orange-500/50 cursor-pointer border-l-4 border-l-orange-500/20" @click="navigateToItem(item.id)">
          <CardContent class="p-4">
            <div class="flex items-start justify-between gap-4">
              <!-- Main Content -->
              <div class="flex-1 min-w-0 space-y-2">
                <!-- Title and Status Row -->
                <div class="flex items-start justify-between gap-2">
                  <div class="flex-1 min-w-0">
                    <h3 class="text-base font-semibold leading-tight group-hover:text-orange-600 transition-colors line-clamp-2">
                      {{ item.title }}
                    </h3>
                  </div>
                  <div class="flex items-center gap-1 flex-shrink-0">
                    <Badge :variant="getStatusVariant(item.status)" class="text-xs">
                      {{ item.status }}
                    </Badge>
                  </div>
                </div>

                <!-- URL and Metadata Row -->
                <div class="space-y-1">
                  <div class="text-sm">
                    <a
                      :href="item.url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="text-orange-600 hover:text-orange-700 hover:underline break-all cursor-pointer text-xs"
                      @click.stop
                    >
                      <Icon name="lucide:external-link" class="h-3 w-3 inline mr-1" />
                      {{ item.url }}
                    </a>
                  </div>

                  <!-- Compact Metadata -->
                  <div class="flex items-center gap-3 text-xs text-muted-foreground">
                    <span>
                      <Icon name="lucide:clock" class="h-3 w-3 inline mr-1" />
                      {{ formatDate(item.updated_at) }}
                    </span>
                    <span v-if="item.hn_story_data?.score !== undefined">
                      <Icon name="lucide:arrow-up" class="h-3 w-3 inline mr-1" />
                      {{ item.hn_story_data.score }}
                    </span>
                    <span v-if="item.hn_story_data?.descendants !== undefined">
                      <Icon name="lucide:message-circle" class="h-3 w-3 inline mr-1" />
                      {{ item.hn_story_data.descendants }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Action Buttons -->
              <div class="flex items-center gap-1 flex-shrink-0">
                <Button
                  size="sm"
                  variant="ghost"
                  class="h-7 w-7 p-0 cursor-pointer"
                  title="View Details"
                  @click.stop="() => navigateTo(`/items/${item.id}`)"
                >
                  <Icon name="lucide:eye" class="h-3 w-3" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  class="h-7 w-7 p-0 cursor-pointer"
                  title="Play"
                  @click.stop
                >
                  <Icon name="lucide:play" class="h-3 w-3" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  class="h-7 w-7 p-0 cursor-pointer text-destructive hover:text-destructive hover:bg-destructive/10"
                  :disabled="deleting === item.id"
                  :title="deleting === item.id ? 'Deleting...' : 'Delete Content'"
                  @click.stop="deleteContent(item.id)"
                >
                  <Icon
                    name="lucide:trash-2"
                    class="h-3 w-3"
                    :class="{ 'animate-spin': deleting === item.id }"
                  />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-8">
      <div class="text-muted-foreground mb-2">
        <Icon name="lucide:inbox" class="h-12 w-12 mx-auto" />
      </div>
      <h3 class="text-lg font-semibold mb-2">No content found</h3>
      <p class="text-muted-foreground">Start by processing some Hacker News articles.</p>
    </div>
  </div>
</template>
