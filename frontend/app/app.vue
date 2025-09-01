<script setup lang="ts">
import { Button } from '~/components/ui/button'

const colorMode = useColorMode()
</script>

<template>
  <div class="min-h-screen bg-background">
    <!-- Navigation Bar -->
    <nav class="border-b bg-card">
      <div class="container mx-auto px-4 py-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-4">
            <h1 class="text-xl font-bold text-foreground">
              <span class="text-orange-600">HN</span>.fm
            </h1>
            <div class="hidden md:flex space-x-6">
              <NuxtLink
                to="/"
                class="text-sm font-medium text-muted-foreground hover:text-orange-600 transition-colors"
                active-class="text-orange-600"
              >
                Home
              </NuxtLink>
              <NuxtLink
                to="/items"
                class="text-sm font-medium text-muted-foreground hover:text-orange-600 transition-colors"
                active-class="text-orange-600"
              >
                Items
              </NuxtLink>
              <NuxtLink
                to="/services"
                class="text-sm font-medium text-muted-foreground hover:text-orange-600 transition-colors"
                active-class="text-orange-600"
              >
                Services
              </NuxtLink>
              <NuxtLink
                to="/admin"
                class="text-sm font-medium text-muted-foreground hover:text-orange-600 transition-colors"
                active-class="text-orange-600"
              >
                Admin
              </NuxtLink>
            </div>
          </div>
          <div class="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              class="px-3"
              @click="colorMode.preference = colorMode.preference === 'dark' ? 'light' : 'dark'"
            >
              <Icon
                :name="colorMode.value === 'dark' ? 'lucide:sun' : 'lucide:moon'"
                class="h-4 w-4"
              />
            </Button>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="container mx-auto px-4 py-8">
      <NuxtPage />
    </main>
  </div>
</template>
