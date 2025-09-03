<template>
  <div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold mb-6">API Test</h1>

    <div v-if="isLoading" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
      <p class="mt-2 text-gray-600">Testing API...</p>
    </div>

    <div v-else-if="error" class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
      {{ error }}
    </div>

    <div v-else-if="result" class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
      <h2 class="font-bold">API Response:</h2>
      <pre class="mt-2 text-sm">{{ JSON.stringify(result, null, 2) }}</pre>
    </div>

    <button
      @click="testAPI"
      class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
    >
      Test API
    </button>
  </div>
</template>

<script setup>
const config = useRuntimeConfig()

// Use useAsyncData for testing API
const { data: result, pending: isLoading, error, refresh: testAPI } = await useAsyncData(
  'test-api',
  () => $fetch(`${config.public.apiBase}/api/hn/items?offset=0&limit=5`),
  {
    default: () => null,
    server: false
  }
)
</script>
