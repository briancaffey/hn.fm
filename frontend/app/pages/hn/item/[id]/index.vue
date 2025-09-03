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
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"/>
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

      <!-- Runs Section -->
      <div class="mt-8">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-2xl font-bold">Runs</h2>
          <Button
            :disabled="isStartingRun"
            variant="default"
            @click="startNewRun"
          >
            {{ isStartingRun ? 'Starting...' : 'Start New Run' }}
          </Button>
        </div>

        <div v-if="deleteMessage" class="bg-green-100 border border-green-300 text-green-800 px-4 py-3 rounded mb-4">
          {{ deleteMessage }}
        </div>

        <div v-if="runsLoading" class="text-center py-4">
          <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto"/>
          <p class="mt-2 text-sm text-muted-foreground">Loading runs...</p>
        </div>

        <div v-else-if="runsError" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
          {{ runsError }}
        </div>

        <div v-else-if="runs.length === 0" class="text-center py-8 text-muted-foreground">
          No runs yet. Start a new run to process this item's content.
        </div>

        <div v-else class="bg-card border rounded-lg overflow-hidden">
          <table class="min-w-full divide-y divide-border">
            <thead class="bg-muted/50">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Run ID
                </th>
                <th class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Summary
                </th>
                <th class="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody class="bg-card divide-y divide-border">
              <tr v-for="run in runs" :key="run.run" class="hover:bg-muted/50 transition-colors">
                <td class="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                  {{ run.run }}
                </td>
                <td class="px-6 py-4 text-sm text-foreground">
                  <div class="max-w-md">
                    {{ truncateSummary(run.summary) }}
                  </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-foreground">
                  <div class="flex gap-2">
                    <NuxtLink
                      :to="`/hn/item/${item.id}/run/${run.run}`"
                      class="text-primary hover:text-primary/80 font-medium"
                    >
                      View Details
                    </NuxtLink>
                    <Button
                      variant="destructive"
                      size="sm"
                      @click="deleteRun(run.run)"
                      :disabled="deletingRuns.has(run.run)"
                      class="ml-2 bg-red-600 hover:bg-red-700 text-white border-red-600"
                    >
                      <span v-if="deletingRuns.has(run.run)">Deleting...</span>
                      <span v-else>🗑️</span>
                    </Button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
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
import { Button } from '~/components/ui/button'

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

// Runs functionality
const runs = ref([])
const runsLoading = ref(false)
const runsError = ref(null)
const isStartingRun = ref(false)
const deletingRuns = ref(new Set())
const deleteMessage = ref('')

// Fetch runs when item is loaded
watch(item, async (newItem) => {
  if (newItem) {
    await fetchRuns()
  }
}, { immediate: true })

async function fetchRuns() {
  if (!item.value) return

  try {
    runsLoading.value = true
    runsError.value = null

    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${item.value.id}/runs?offset=0&limit=20`)
    runs.value = response.runs || []
  } catch (err) {
    console.error('Failed to fetch runs:', err)
    runsError.value = 'Failed to load runs: ' + err.message
  } finally {
    runsLoading.value = false
  }
}

async function startNewRun() {
  if (!item.value) return

  try {
    isStartingRun.value = true
    runsError.value = null

    await $fetch(`${config.public.apiBase}/api/hn/items/${item.value.id}/runs`, { method: 'POST' })

    // Refresh runs list
    await fetchRuns()
  } catch (err) {
    console.error('Failed to start new run:', err)
    runsError.value = 'Failed to start new run: ' + err.message
  } finally {
    isStartingRun.value = false
  }
}

function truncateSummary(summary) {
  if (!summary) return ''
  return summary.length > 200 ? summary.substring(0, 200) + '...' : summary
}

function formatTime(timestamp) {
  if (!timestamp) return 'Unknown'

  const date = new Date(timestamp * 1000)
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString()
}

async function deleteRun(runId) {
  if (deletingRuns.value.has(runId)) return

  deletingRuns.value.add(runId)
  deleteMessage.value = ''

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${item.value.id}/runs/${runId}`, {
      method: 'DELETE'
    })

    deleteMessage.value = `Run ${runId} deleted successfully!`

    // Reload the runs list
    await fetchRuns()

    // Clear message after 3 seconds
    setTimeout(() => {
      deleteMessage.value = ''
    }, 3000)

  } catch (err) {
    console.error('Failed to delete run:', err)
    deleteMessage.value = `Failed to delete run ${runId}. Please try again.`
  } finally {
    deletingRuns.value.delete(runId)
  }
}
</script>
