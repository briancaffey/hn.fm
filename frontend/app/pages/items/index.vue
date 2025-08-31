<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { Icon } from '#components'
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="space-y-2">
      <h1 class="text-3xl font-bold text-foreground">Items</h1>
      <p class="text-muted-foreground">
        Browse and manage your curated Hacker News content
      </p>
    </div>

    <!-- Filters and Search -->
    <div class="flex flex-col sm:flex-row gap-4">
      <div class="flex-1">
        <Input
          placeholder="Search articles..."
          class="max-w-sm"
        >
          <Icon name="lucide:search" class="h-4 w-4" />
        </Input>
      </div>
      <div class="flex gap-2">
        <Select>
          <SelectTrigger class="w-32">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline">
          <Icon name="lucide:filter" class="h-4 w-4 mr-2" />
          Filter
        </Button>
      </div>
    </div>

    <!-- Content List -->
    <ContentList />
  </div>
</template>
