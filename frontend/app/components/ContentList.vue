<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Button } from '~/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
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
  metadata: Record<string, any>
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

// Get runtime config for API base URL
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const fetchContent = async () => {
  try {
    loading.value = true
    error.value = null

    const data: ContentListResponse = await $fetch(`${apiBase}/api/content?limit=20`)
    contentItems.value = data.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch content'
    console.error('Error fetching content:', err)
  } finally {
    loading.value = false
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

const getContentTypeIcon = (contentType: string) => {
  switch (contentType) {
    case 'article':
      return 'lucide:file-text'
    case 'video':
      return 'lucide:video'
    case 'podcast':
      return 'lucide:headphones'
    case 'news':
      return 'lucide:newspaper'
    default:
      return 'lucide:file'
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
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      <span class="ml-2 text-muted-foreground">Loading content...</span>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="text-center py-8">
      <div class="text-destructive mb-2">
        <Icon name="lucide:alert-circle" class="h-8 w-8 mx-auto" />
      </div>
      <p class="text-muted-foreground">{{ error }}</p>
      <Button @click="fetchContent" variant="outline" class="mt-4">
        <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
        Try Again
      </Button>
    </div>

    <!-- Content List -->
    <div v-else-if="contentItems.length > 0" class="space-y-4">
              <div v-for="item in contentItems" :key="item.id" class="group">
        <Card class="transition-all duration-200 hover:shadow-md hover:border-primary/50 cursor-pointer" @click="navigateToItem(item.id)">
          <CardHeader class="pb-3">
            <div class="flex items-start justify-between">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-2">
                  <Icon
                    :name="getContentTypeIcon(item.content_type)"
                    class="h-4 w-4 text-muted-foreground"
                  />
                  <Badge variant="outline" class="text-xs">
                    {{ item.content_type }}
                  </Badge>
                  <Badge :variant="getStatusVariant(item.status)">
                    {{ item.status }}
                  </Badge>
                </div>
                <CardTitle class="text-lg leading-tight group-hover:text-primary transition-colors">
                  {{ item.title }}
                </CardTitle>
              </div>
              <div class="flex flex-col gap-2 ml-4">
                <Button size="sm" variant="outline" class="h-8 w-8 p-0" @click.stop>
                  <Icon name="lucide:play" class="h-4 w-4" />
                </Button>
                <Button size="sm" variant="outline" class="h-8 w-8 p-0" @click.stop>
                  <Icon name="lucide:image" class="h-4 w-4" />
                </Button>
                <Button size="sm" variant="outline" class="h-8 w-8 p-0" @click.stop>
                  <Icon name="lucide:more-horizontal" class="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>

          <CardContent class="pt-0">
            <div class="space-y-3">
              <!-- HN Story Data -->
              <div v-if="item.hn_story_data" class="flex items-center gap-4 text-sm text-muted-foreground">
                <span v-if="item.hn_story_data.score !== undefined">
                  <Icon name="lucide:arrow-up" class="h-3 w-3 inline mr-1" />
                  Score: {{ item.hn_story_data.score }}
                </span>
                <span v-if="item.hn_story_data.descendants !== undefined">
                  <Icon name="lucide:message-circle" class="h-3 w-3 inline mr-1" />
                  {{ item.hn_story_data.descendants }} comments
                </span>
                <span v-if="item.hn_story_data.by">
                  by {{ item.hn_story_data.by }}
                </span>
              </div>

              <!-- Timestamps -->
              <div class="flex items-center gap-4 text-sm text-muted-foreground">
                <span>
                  <Icon name="lucide:clock" class="h-3 w-3 inline mr-1" />
                  Updated {{ formatDate(item.updated_at) }}
                </span>
                <span>
                  <Icon name="lucide:calendar" class="h-3 w-3 inline mr-1" />
                  Created {{ formatDate(item.created_at) }}
                </span>
              </div>

              <!-- URL -->
              <div class="text-sm">
                <a
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-primary hover:underline break-all"
                >
                  <Icon name="lucide:external-link" class="h-3 w-3 inline mr-1" />
                  {{ item.url }}
                </a>
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
