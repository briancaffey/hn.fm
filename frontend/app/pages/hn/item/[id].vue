<template>
  <div class="container mx-auto px-4 py-8">
    <div class="mb-6">
      <NuxtLink
        to="/hn/items"
        class="text-primary hover:text-primary/80 font-medium"
      >
        ← Back to Items
      </NuxtLink>
    </div>

    <div v-if="isLoading" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
      <p class="mt-2 text-muted-foreground">Loading item...</p>
    </div>

    <div v-else-if="!!error" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
      {{ error }}
    </div>

    <div v-else-if="!!item" class="bg-card border rounded-lg p-6">
      <h1 class="text-3xl font-bold mb-6">{{ item.title || 'No Title' }}</h1>

      <!-- Compact badge layout for item details -->
      <div class="space-y-4">
        <!-- All badges on one line -->
        <div class="flex flex-wrap gap-2">
          <Badge class="bg-orange-500 text-white border-orange-500 text-sm">
            ID: {{ item.id }}
          </Badge>
          <Badge class="bg-white text-orange-500 border-orange-500 text-sm">
            {{ item.type || 'story' }}
          </Badge>
          <Badge class="bg-orange-500 text-white border-orange-500 text-sm">
            by {{ item.by || 'Unknown' }}
          </Badge>
          <Badge class="bg-white text-orange-500 border-orange-500 text-sm">
            {{ item.score || 0 }} points
          </Badge>
          <Badge class="bg-orange-500 text-white border-orange-500 text-sm">
            {{ formatTime(item.time) }}
          </Badge>
          <Badge v-if="item.kids && item.kids.length > 0" class="bg-white text-orange-500 border-orange-500 text-sm">
            {{ item.kids.length }} comment{{ item.kids.length !== 1 ? 's' : '' }}
          </Badge>
          <Badge v-if="item.url" class="bg-orange-500 text-white border-orange-500 text-sm">
            <a
              :href="item.url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-white hover:text-orange-100 break-all"
            >
              🔗 {{ item.url }}
            </a>
          </Badge>
        </div>

        <!-- Text content if present -->
        <div v-if="item.text" class="mt-4">
          <p class="text-foreground whitespace-pre-wrap">{{ item.text }}</p>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-8 text-muted-foreground">
      Item not found
    </div>
  </div>
</template>

<script setup>
import { Badge } from '~/components/ui/badge'

const route = useRoute()
const config = useRuntimeConfig()

// Debug logging
console.log('Route params:', route.params)
console.log('Route path:', route.path)
console.log('Item ID:', route.params.id)

// Use useAsyncData for fetching item with proper SSR handling
const { data: item, pending: isLoading, error } = await useAsyncData(
  `hn-item-${route.params.id}`,
  async () => {
    const itemId = parseInt(route.params.id)
    console.log('Fetching item with ID:', itemId)
    try {
      const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId}`)
      console.log('API response:', response)
      return response
    } catch (err) {
      console.error('API error:', err)
      throw err
    }
  },
  {
    default: () => null
  }
)

function formatTime(timestamp) {
  if (!timestamp) return 'Unknown'

  const date = new Date(timestamp * 1000)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}
</script>
