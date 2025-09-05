<template>
  <div class="container mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold text-orange-600">Hacker News Items</h1>
      <Button
        :disabled="isQueueing"
        variant="default"
        class="bg-orange-600 hover:bg-orange-700 text-white"
        @click="queueTopStories"
      >
        {{ isQueueing ? 'Queueing...' : 'Queue Top (20)' }}
      </Button>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600 mx-auto"/>
      <p class="mt-2 text-muted-foreground">Loading items...</p>
    </div>

    <div v-else-if="error" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
      {{ error }}
    </div>

    <div v-else>
      <div class="bg-card border rounded-lg overflow-hidden">
        <table class="min-w-full divide-y divide-border">
          <thead class="bg-orange-50 dark:bg-orange-950/20">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-orange-700 dark:text-orange-300 uppercase tracking-wider">
                #
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-orange-700 dark:text-orange-300 uppercase tracking-wider">
                Title
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-orange-700 dark:text-orange-300 uppercase tracking-wider">
                URL
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-orange-700 dark:text-orange-300 uppercase tracking-wider">
                By
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-orange-700 dark:text-orange-300 uppercase tracking-wider">
                Score
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-orange-700 dark:text-orange-300 uppercase tracking-wider">
                Time
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-orange-700 dark:text-orange-300 uppercase tracking-wider">
                ID
              </th>
            </tr>
          </thead>
          <tbody class="bg-card divide-y divide-border">
                        <tr
              v-for="(item, index) in items"
              :key="item.id"
              class="hover:bg-orange-50 dark:hover:bg-orange-950/10 transition-colors cursor-pointer"
              @click="navigateToItem(item.id)"
            >
              <td class="px-6 py-4 whitespace-nowrap text-base text-muted-foreground">
                {{ (pagination.page.value - 1) * pagination.limit.value + index + 1 }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span class="text-foreground font-medium text-base">
                  {{ item.title || 'No title' }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <a
                  v-if="item.url"
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-2 text-orange-600 hover:text-orange-700 font-medium text-base"
                  @click.stop
                >
                  <Icon name="lucide:external-link" class="h-4 w-4" />
                  {{ getUrlHost(item.url) }}
                </a>
                <span v-else class="text-muted-foreground text-base">
                  No URL
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-base text-foreground">
                {{ item.by || 'Unknown' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-base text-foreground">
                <span class="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300">
                  {{ item.score || 0 }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-base text-foreground">
                {{ formatTime(item.time) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-base text-foreground">
                <span class="font-mono text-orange-600 dark:text-orange-400">
                  {{ item.id }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="items.length === 0" class="text-center py-8 text-muted-foreground">
        No items found. Try queuing some top stories!
      </div>

      <!-- Pagination -->
      <div v-if="pagination" class="mt-6">
        <Pagination
          :page="pagination.page"
          :total="pagination.total"
          :limit="pagination.limit"
          :total-pages="pagination.totalPages"
          :has-next-page="pagination.hasNextPage"
          :has-previous-page="pagination.hasPreviousPage"
          :set-page="pagination.setPage"
          :next-page="pagination.nextPage"
          :previous-page="pagination.previousPage"
          :first-page="pagination.firstPage"
          :last-page="pagination.lastPage"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { usePagination } from '~/composables/usePagination'
import Pagination from '~/components/Pagination.vue'

// Disable SSR for this page
definePageMeta({
  ssr: false
})

const config = useRuntimeConfig()

// Simple reactive state
const items = ref([])
const isLoading = ref(true)
const error = ref(null)
const isQueueing = ref(false)

// Initialize pagination
const pagination = usePagination({
  initialPage: 1,
  initialLimit: 20,
  onPageChange: (page) => {
    // Fetch data when page changes
    fetchItems(page)
  }
})

// Fetch data
async function fetchItems(page = 1) {
  try {
    isLoading.value = true
    error.value = null

    const limit = pagination.limit.value
    const offset = pagination.offset.value

    console.log('Fetching items from:', `${config.public.apiBase}/api/hn/items?offset=${offset}&limit=${limit}`)

    const response = await $fetch(`${config.public.apiBase}/api/hn/items?offset=${offset}&limit=${limit}`)
    console.log('API response:', response)

    items.value = response.items || []

    // Update pagination with total count
    if (response.pagination?.total !== undefined) {
      pagination.setTotal(response.pagination.total)
    }
  } catch (err) {
    console.error('API error:', err)
    error.value = 'Failed to fetch items: ' + err.message
  } finally {
    isLoading.value = false
  }
}

// Queue top stories
async function queueTopStories() {
  try {
    isQueueing.value = true
    error.value = null

    await $fetch(`${config.public.apiBase}/api/hn/queue-top?limit=20`, { method: 'POST' })

    // Refetch the list after queuing
    await fetchItems(pagination.page.value)
  } catch (err) {
    error.value = 'Failed to queue top stories: ' + err.message
  } finally {
    isQueueing.value = false
  }
}

// Format time
function formatTime(timestamp) {
  if (!timestamp) return 'Unknown'

  const date = new Date(timestamp * 1000)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}

// Extract host from URL
function getUrlHost(url) {
  if (!url) return 'No URL'

  try {
    const urlObj = new URL(url)
    return urlObj.hostname
  } catch (error) {
    return 'Invalid URL'
  }
}

// Navigate to item detail page
function navigateToItem(itemId) {
  navigateTo(`/hn/item/${itemId}`)
}

// Fetch data on mount
onMounted(() => {
  fetchItems(1)
})
</script>
