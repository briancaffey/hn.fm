<template>
  <div class="min-h-screen flex items-center justify-center bg-background">
    <div class="text-center space-y-6">
      <div class="space-y-2">
        <h1 class="text-6xl font-bold text-foreground">{{ error?.statusCode || '500' }}</h1>
        <h2 class="text-2xl font-semibold text-foreground">
          {{ error?.statusMessage || 'Something went wrong' }}
        </h2>
        <p class="text-muted-foreground max-w-md mx-auto">
          {{ error?.message || 'An unexpected error occurred. Please try again or go back to the home page.' }}
        </p>
      </div>

      <div class="flex justify-center space-x-4">
        <Button @click="handleError">
          <Icon name="lucide:refresh-cw" class="h-4 w-4 mr-2" />
          Try Again
        </Button>
        <Button variant="outline" @click="navigateTo('/')">
          <Icon name="lucide:home" class="h-4 w-4 mr-2" />
          Go Home
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  error: Object
})

const handleError = () => {
  clearError({ redirect: '/' })
}
</script>
