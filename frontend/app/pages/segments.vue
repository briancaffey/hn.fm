<template>
  <div class="container mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold text-orange-600">Segments</h1>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600 mx-auto"/>
      <p class="mt-2 text-muted-foreground">Loading segments...</p>
    </div>

    <div v-else-if="error" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
      {{ error }}
    </div>

    <div v-else>
      <div v-if="segments.length === 0" class="text-center py-8 text-muted-foreground">
        No segments found.
      </div>

      <div v-else class="grid gap-4">
        <SegmentCard
          v-for="segment in segments"
          :key="`${segment.item_id}-${segment.run}-${segment.seg}`"
          :segment="segment"
        />
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
import SegmentCard from '~/components/SegmentCard.vue'

// Disable SSR for this page
definePageMeta({
  ssr: false
})

const config = useRuntimeConfig()

// Simple reactive state
const segments = ref([])
const isLoading = ref(true)
const error = ref(null)

// Ensure config is available
if (!config.public?.apiBase) {
  console.error('API base URL not configured')
  error.value = 'Configuration error: API base URL not found'
}

// Initialize pagination
const pagination = usePagination({
  initialPage: 1,
  initialLimit: 20,
  onPageChange: (page) => {
    // Fetch data when page changes
    fetchSegments(page)
  }
})

// Fetch data
async function fetchSegments(page = 1) {
  try {
    isLoading.value = true
    error.value = null

    // Check if API base is available
    if (!config.public?.apiBase) {
      throw new Error('API base URL not configured')
    }

    const limit = pagination.limit.value
    const offset = pagination.offset.value

    console.log('Fetching segments from:', `${config.public.apiBase}/api/segments?offset=${offset}&limit=${limit}`)

    const response = await $fetch(`${config.public.apiBase}/api/segments?offset=${offset}&limit=${limit}`)
    console.log('API response:', response)

    segments.value = response.segments || []

    // Update pagination with total count
    if (response.pagination?.total !== undefined) {
      pagination.setTotal(response.pagination.total)
    }
  } catch (err) {
    console.error('API error:', err)
    error.value = 'Failed to fetch segments: ' + (err.message || 'Unknown error')
    segments.value = [] // Ensure segments is always an array
  } finally {
    isLoading.value = false
  }
}

// Fetch data on mount
onMounted(async () => {
  try {
    await fetchSegments(1)
  } catch (err) {
    console.error('Failed to fetch segments on mount:', err)
    error.value = 'Failed to load segments. Please try refreshing the page.'
  }
})
</script>
