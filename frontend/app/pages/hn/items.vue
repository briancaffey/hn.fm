<template>
  <div class="container mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold">Hacker News Items</h1>
      <Button
        :disabled="isQueueing"
        variant="default"
        @click="queueTopStories"
      >
        {{ isQueueing ? 'Queueing...' : 'Queue Top (20)' }}
      </Button>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"/>
      <p class="mt-2 text-muted-foreground">Loading items...</p>
    </div>

    <div v-else-if="error" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
      {{ error }}
    </div>

    <div v-else>
      <div class="bg-card border rounded-lg overflow-hidden">
        <table class="min-w-full divide-y divide-border">
          <thead class="bg-muted/50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                #
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Title
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                By
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Score
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Time
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                ID
              </th>
            </tr>
          </thead>
          <tbody class="bg-card divide-y divide-border">
            <tr v-for="(item, index) in items" :key="item.id" class="hover:bg-muted/50 transition-colors">
              <td class="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">
                {{ (pagination.page.value - 1) * pagination.limit.value + index + 1 }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <a
                  v-if="item.url"
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-primary hover:text-primary/80 font-medium"
                >
                  {{ item.title || 'No title' }}
                </a>
                <span v-else class="text-foreground font-medium">
                  {{ item.title || 'No title' }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                {{ item.by || 'Unknown' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                {{ item.score || 0 }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                {{ formatTime(item.time) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                <NuxtLink
                  :to="`/hn/item/${item.id}`"
                  class="text-primary hover:text-primary/80"
                >
                  {{ item.id }}
                </NuxtLink>
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

// Fetch data on mount
onMounted(() => {
  fetchItems(1)
})
</script>
