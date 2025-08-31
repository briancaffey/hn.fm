<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Card } from '~/components/ui/card'
import { Input } from '~/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { Badge } from '~/components/ui/badge'
import { Pagination, PaginationContent, PaginationItem, PaginationNext, PaginationPrevious } from '~/components/ui/pagination'
import { Icon } from '#components'
</script>

<template>
  <div class="space-y-6">
    <!-- Page Header -->
    <div class="space-y-2">
      <h1 class="text-3xl font-bold text-foreground">Articles</h1>
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

    <!-- Articles Grid -->
    <div class="grid gap-6">
      <!-- Article Card 1 -->
      <Card class="p-6">
        <div class="flex items-start justify-between">
          <div class="space-y-3 flex-1">
            <div class="flex items-center space-x-2">
              <Badge variant="secondary">Tech</Badge>
              <Badge variant="outline">Processing</Badge>
            </div>
            <h3 class="text-lg font-semibold text-foreground">
              The Future of AI in Software Development
            </h3>
            <p class="text-muted-foreground line-clamp-2">
              Exploring how artificial intelligence is revolutionizing the way we write, debug, and maintain code.
              From automated testing to intelligent code completion, AI tools are becoming indispensable.
            </p>
            <div class="flex items-center space-x-4 text-sm text-muted-foreground">
              <span>Score: 847</span>
              <span>Comments: 234</span>
              <span>2 hours ago</span>
            </div>
          </div>
          <div class="flex flex-col space-y-2 ml-4">
            <Button size="sm" variant="outline">
              <Icon name="lucide:play" class="h-4 w-4" />
            </Button>
            <Button size="sm" variant="outline">
              <Icon name="lucide:image" class="h-4 w-4" />
            </Button>
            <Button size="sm" variant="outline">
              <Icon name="lucide:more-horizontal" class="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      <!-- Article Card 2 -->
      <Card class="p-6">
        <div class="flex items-start justify-between">
          <div class="space-y-3 flex-1">
            <div class="flex items-center space-x-2">
              <Badge variant="secondary">Science</Badge>
              <Badge variant="default">Completed</Badge>
            </div>
            <h3 class="text-lg font-semibold text-foreground">
              Breakthrough in Quantum Computing
            </h3>
            <p class="text-muted-foreground line-clamp-2">
              Researchers achieve quantum supremacy with a new 1000-qubit processor, opening new possibilities
              for cryptography, drug discovery, and complex simulations.
            </p>
            <div class="flex items-center space-x-4 text-sm text-muted-foreground">
              <span>Score: 1,203</span>
              <span>Comments: 456</span>
              <span>5 hours ago</span>
            </div>
          </div>
          <div class="flex flex-col space-y-2 ml-4">
            <Button size="sm" variant="outline">
              <Icon name="lucide:headphones" class="h-4 w-4" />
            </Button>
            <Button size="sm" variant="outline">
              <Icon name="lucide:video" class="h-4 w-4" />
            </Button>
            <Button size="sm" variant="outline">
              <Icon name="lucide:more-horizontal" class="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      <!-- Article Card 3 -->
      <Card class="p-6">
        <div class="flex items-start justify-between">
          <div class="space-y-3 flex-1">
            <div class="flex items-center space-x-2">
              <Badge variant="secondary">Business</Badge>
              <Badge variant="secondary">Pending</Badge>
            </div>
            <h3 class="text-lg font-semibold text-foreground">
              The Rise of Remote-First Companies
            </h3>
            <p class="text-muted-foreground line-clamp-2">
              How companies are adapting to the new normal of distributed workforces, with insights into
              productivity, culture, and the future of office spaces.
            </p>
            <div class="flex items-center space-x-4 text-sm text-muted-foreground">
              <span>Score: 623</span>
              <span>Comments: 189</span>
              <span>8 hours ago</span>
            </div>
          </div>
          <div class="flex flex-col space-y-2 ml-4">
            <Button size="sm" variant="outline">
              <Icon name="lucide:play" class="h-4 w-4" />
            </Button>
            <Button size="sm" variant="outline">
              <Icon name="lucide:image" class="h-4 w-4" />
            </Button>
            <Button size="sm" variant="outline">
              <Icon name="lucide:more-horizontal" class="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>

    <!-- Pagination -->
    <div class="flex justify-center">
      <Pagination :items-per-page="10" :total="100">
        <PaginationContent>
          <PaginationItem :value="0">
            <PaginationPrevious />
          </PaginationItem>
          <PaginationItem :value="1" :is-active="true">
            <button class="px-3 py-2">1</button>
          </PaginationItem>
          <PaginationItem :value="2">
            <button class="px-3 py-2">2</button>
          </PaginationItem>
          <PaginationItem :value="3">
            <button class="px-3 py-2">3</button>
          </PaginationItem>
          <PaginationItem :value="4">
            <PaginationNext />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  </div>
</template>
