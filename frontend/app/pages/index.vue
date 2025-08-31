<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
import { Icon } from '#components'
</script>

<template>
  <div class="space-y-8">
    <!-- Hero Section -->
    <section class="text-center space-y-4">
      <h1 class="text-4xl font-bold text-foreground">
        Welcome to HN.fm
      </h1>
      <p class="text-xl text-muted-foreground max-w-2xl mx-auto">
        Your gateway to curated Hacker News content, transformed into engaging audio and visual experiences.
      </p>
      <div class="flex justify-center space-x-4">
        <Button size="lg">
          <Icon name="lucide:play" class="h-4 w-4 mr-2" />
          Get Started
        </Button>
        <Button variant="outline" size="lg">
          <Icon name="lucide:info" class="h-4 w-4 mr-2" />
          Learn More
        </Button>
      </div>
    </section>

    <!-- Features Grid -->
    <section class="grid md:grid-cols-3 gap-6">
      <Card class="p-6">
        <CardHeader>
          <CardTitle class="flex items-center space-x-2">
            <Icon name="lucide:headphones" class="h-5 w-5 text-primary" />
            <span>Audio Generation</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p class="text-muted-foreground">
            Transform articles into high-quality audio content with natural-sounding voices.
          </p>
        </CardContent>
      </Card>

      <Card class="p-6">
        <CardHeader>
          <CardTitle class="flex items-center space-x-2">
            <Icon name="lucide:image" class="h-5 w-5 text-primary" />
            <span>Visual Content</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p class="text-muted-foreground">
            Generate compelling images and videos to accompany your content.
          </p>
        </CardContent>
      </Card>

      <Card class="p-6">
        <CardHeader>
          <CardTitle class="flex items-center space-x-2">
            <Icon name="lucide:zap" class="h-5 w-5 text-primary" />
            <span>Smart Curation</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p class="text-muted-foreground">
            AI-powered content selection and processing for the best Hacker News stories.
          </p>
        </CardContent>
      </Card>
    </section>

    <!-- Stats Section -->
    <section class="bg-muted/50 rounded-lg p-8">
      <div class="grid md:grid-cols-4 gap-6 text-center">
        <div>
          <div class="text-3xl font-bold text-foreground">1,234</div>
          <div class="text-sm text-muted-foreground">Articles Processed</div>
        </div>
        <div>
          <div class="text-3xl font-bold text-foreground">567</div>
          <div class="text-sm text-muted-foreground">Audio Files</div>
        </div>
        <div>
          <div class="text-3xl font-bold text-foreground">89</div>
          <div class="text-sm text-muted-foreground">Videos Created</div>
        </div>
        <div>
          <div class="text-3xl font-bold text-foreground">42</div>
          <div class="text-sm text-muted-foreground">Active Users</div>
        </div>
      </div>
    </section>
  </div>
</template>
