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
            <h1 class="text-xl font-bold text-foreground">HN.fm</h1>
            <div class="hidden md:flex space-x-6">
              <NuxtLink
                to="/"
                class="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                active-class="text-foreground"
              >
                Home
              </NuxtLink>
              <NuxtLink
                to="/items"
                class="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                active-class="text-foreground"
              >
                Items
              </NuxtLink>
              <NuxtLink
                to="/services"
                class="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                active-class="text-foreground"
              >
                Services
              </NuxtLink>
            </div>
          </div>
          <div class="flex items-center space-x-2">
            <div class="flex items-center space-x-2">
              <Icon
                :name="colorMode.value === 'dark' ? 'lucide:moon' : 'lucide:sun'"
                class="h-4 w-4 text-muted-foreground"
              />
              <select
                v-model="colorMode.preference"
                class="px-3 py-2 text-sm border border-input bg-background text-foreground rounded-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
            <Button variant="outline" size="sm">
              <Icon name="lucide:settings" class="h-4 w-4" />
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
