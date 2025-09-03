<template>
  <div class="container mx-auto px-4 py-8">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold">Hacker News Items</h1>
      <Button
        @click="queueTopStories"
        :disabled="isQueueing"
        variant="default"
      >
        {{ isQueueing ? 'Queueing...' : 'Queue Top (50)' }}
      </Button>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
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
            <tr v-for="item in items" :key="item.id" class="hover:bg-muted/50 transition-colors">
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
    </div>
  </div>
</template>

<script setup>
const config = useRuntimeConfig()

// Use useAsyncData for fetching items with proper SSR handling
const { data: itemsData, pending: isLoading, error, refresh: refreshItems } = await useAsyncData(
  'hn-items',
  () => $fetch(`${config.public.apiBase}/api/hn/items?offset=0&limit=50`),
  {
    default: () => ({ items: [], pagination: { offset: 0, limit: 50, count: 0 } }),
    server: false // Only fetch on client side to avoid SSR issues
  }
)

const items = computed(() => itemsData.value?.items || [])
const isQueueing = ref(false)

async function queueTopStories() {
  try {
    isQueueing.value = true
    error.value = null

    await $fetch(`${config.public.apiBase}/api/hn/queue-top?limit=50`, { method: 'POST' })

    // Refetch the list after queuing
    await refreshItems()
  } catch (err) {
    error.value = 'Failed to queue top stories: ' + err.message
  } finally {
    isQueueing.value = false
  }
}

function formatTime(timestamp) {
  if (!timestamp) return 'Unknown'

  const date = new Date(timestamp * 1000)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}
</script>
