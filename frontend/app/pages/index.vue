<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Icon } from '#components'
</script>

<template>
  <div class="flex items-center justify-center min-h-[calc(100vh-200px)]">
    <div class="text-center space-y-8 max-w-2xl mx-auto px-4">
      <div class="space-y-6">
        <h1 class="text-6xl font-bold text-foreground">
          <span class="text-orange-600">hn</span>.fm
        </h1>
        <p class="text-xl text-muted-foreground">
          Transform Hacker News stories into engaging audio and visual content.
        </p>
        <p class="text-lg text-muted-foreground">
          Coming soon...
        </p>
      </div>

      <div class="flex justify-center space-x-4">
        <Button size="lg" variant="outline">
          <Icon name="lucide:github" class="h-4 w-4 mr-2" />
          GitHub
        </Button>
        <Button size="lg">
          <Icon name="lucide:zap" class="h-4 w-4 mr-2" />
          Get Started
        </Button>
      </div>
    </div>
  </div>
</template>
