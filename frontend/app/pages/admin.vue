<template>
  <div class="container mx-auto px-4 py-8">
    <div class="max-w-4xl mx-auto">
      <h1 class="text-3xl font-bold mb-8">Admin</h1>

      <!-- Danger Zone -->
      <div class="bg-white rounded-lg border border-red-300 shadow p-6">
        <h2 class="text-xl font-semibold text-red-600 mb-2">Danger Zone</h2>
        <p class="text-gray-600 mb-6">Irreversible and destructive actions</p>

        <div class="flex items-center justify-between">
          <div>
            <h3 class="text-lg font-medium text-black">Delete All Data</h3>
            <p class="text-gray-600 mt-1">
              Permanently delete all content, processing history, and cached data from Redis.
              This action cannot be undone.
            </p>
          </div>

          <Button
            :disabled="isDeleting"
            class="ml-4 bg-red-600 hover:bg-red-700 text-white"
            @click="deleteAllData"
          >
            <Trash2 class="w-4 h-4 mr-2" />
            {{ isDeleting ? 'Deleting...' : 'Delete All Data' }}
          </Button>
        </div>

        <!-- Success Message -->
        <div v-if="successMessage" class="mt-4 p-4 bg-green-100 border border-green-300 rounded">
          <div class="flex">
            <CheckCircle class="w-5 h-5 text-green-600 mr-2" />
            <div>
              <h4 class="text-sm font-medium text-green-800">Success!</h4>
              <p class="text-sm text-green-700 mt-1">{{ successMessage }}</p>
            </div>
          </div>
        </div>

        <!-- Error Message -->
        <div v-if="errorMessage" class="mt-4 p-4 bg-red-100 border border-red-300 rounded">
          <div class="flex">
            <AlertCircle class="w-5 h-5 text-red-600 mr-2" />
            <div>
              <h4 class="text-sm font-medium text-red-800">Error</h4>
              <p class="text-sm text-red-700 mt-1">{{ errorMessage }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button } from '@/components/ui/button'
import { Trash2, CheckCircle, AlertCircle } from 'lucide-vue-next'

// Type definitions
interface DeleteAllDataResponse {
  message: string
  deleted_keys: number
}

// Page metadata
definePageMeta({
  title: 'Admin'
})

// Reactive state
const isDeleting = ref(false)
const successMessage = ref('')
const errorMessage = ref('')

// Clear messages when component mounts
onMounted(() => {
  successMessage.value = ''
  errorMessage.value = ''
})

// Get runtime config for API base URL
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

// Delete all data function
const deleteAllData = async () => {
  // Clear previous messages
  successMessage.value = ''
  errorMessage.value = ''

  isDeleting.value = true

  try {
    const response = await $fetch<DeleteAllDataResponse>(`${apiBase}/api/admin/delete-all-data`, {
      method: 'DELETE'
    })

    successMessage.value = `${response.message} (${response.deleted_keys} keys deleted)`

  } catch (error: unknown) {
    console.error('Failed to delete all data:', error)
    const errorData = error as { data?: { detail?: string } }
    errorMessage.value = errorData.data?.detail || 'Failed to delete all data. Please try again.'
  } finally {
    isDeleting.value = false
  }
}
</script>
