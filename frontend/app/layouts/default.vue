<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Icon } from '#components'

const colorMode = useColorMode()
</script>

<template>
  <div class="min-h-screen bg-background flex flex-col">
    <!-- Navigation Bar -->
    <nav class="border-b bg-card">
      <div class="container mx-auto px-4 py-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-4">
            <h1 class="text-xl font-bold text-foreground">
              <span class="text-orange-600">hn</span>.fm
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
                to="/hn/items"
                class="text-sm font-medium text-muted-foreground hover:text-orange-600 transition-colors"
                active-class="text-orange-600"
              >
                Items
              </NuxtLink>
              <NuxtLink
                to="/segments"
                class="text-sm font-medium text-muted-foreground hover:text-orange-600 transition-colors"
                active-class="text-orange-600"
              >
                Segments
              </NuxtLink>
              <NuxtLink
                to="/services"
                class="text-sm font-medium text-muted-foreground hover:text-orange-600 transition-colors"
                active-class="text-orange-600"
              >
                Services
              </NuxtLink>
              <NuxtLink
                to="/observability"
                class="text-sm font-medium text-muted-foreground hover:text-orange-600 transition-colors"
                active-class="text-orange-600"
              >
                Observability
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
    <main class="flex-1 container mx-auto px-4 py-8">
      <slot />
    </main>

    <!-- Footer -->
    <footer class="border-t bg-card">
      <div class="container mx-auto px-4 py-8">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-8">
          <!-- Brand Section -->
          <div class="space-y-4">
            <h3 class="text-lg font-semibold text-foreground">
              <span class="text-orange-600">hn</span>.fm
            </h3>
            <p class="text-sm text-muted-foreground">
              Converting Hacker News discussions into engaging audio content.
            </p>
          </div>

          <!-- Links Section -->
          <div class="space-y-4">
            <h4 class="text-sm font-semibold text-foreground">Links</h4>
            <ul class="space-y-2">
              <li>
                <a
                  href="https://github.com/briancaffey/hn.fm"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-sm text-muted-foreground hover:text-orange-600 transition-colors flex items-center gap-2"
                >
                  <Icon name="lucide:github" class="h-4 w-4" />
                  GitHub Repository
                </a>
              </li>
              <li>
                <a
                  href="https://youtube.com/hn_fm"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-sm text-muted-foreground hover:text-orange-600 transition-colors flex items-center gap-2"
                >
                  <Icon name="lucide:youtube" class="h-4 w-4" />
                  YouTube Channel
                </a>
              </li>
              <li>
                <a
                  href="https://news.ycombinator.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-sm text-muted-foreground hover:text-orange-600 transition-colors flex items-center gap-2"
                >
                  <Icon name="lucide:external-link" class="h-4 w-4" />
                  Hacker News
                </a>
              </li>
            </ul>
          </div>

          <!-- Navigation Section -->
          <div class="space-y-4">
            <h4 class="text-sm font-semibold text-foreground">Navigation</h4>
            <ul class="space-y-2">
              <li>
                <NuxtLink
                  to="/"
                  class="text-sm text-muted-foreground hover:text-orange-600 transition-colors"
                >
                  Home
                </NuxtLink>
              </li>
              <li>
                <NuxtLink
                  to="/hn/items"
                  class="text-sm text-muted-foreground hover:text-orange-600 transition-colors"
                >
                  Items
                </NuxtLink>
              </li>
              <li>
                <NuxtLink
                  to="/segments"
                  class="text-sm text-muted-foreground hover:text-orange-600 transition-colors"
                >
                  Segments
                </NuxtLink>
              </li>
              <li>
                <NuxtLink
                  to="/services"
                  class="text-sm text-muted-foreground hover:text-orange-600 transition-colors"
                >
                  Services
                </NuxtLink>
              </li>
            </ul>
          </div>

          <!-- Contact Section -->
          <div class="space-y-4">
            <h4 class="text-sm font-semibold text-foreground">Contact</h4>
            <ul class="space-y-2">
              <li>
                <a
                  href="mailto:hello@hn.fm"
                  class="text-sm text-muted-foreground hover:text-orange-600 transition-colors flex items-center gap-2"
                >
                  <Icon name="lucide:mail" class="h-4 w-4" />
                  hello@hn.fm
                </a>
              </li>
              <li>
                <a
                  href="https://twitter.com/hn_fm"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-sm text-muted-foreground hover:text-orange-600 transition-colors flex items-center gap-2"
                >
                  <Icon name="lucide:twitter" class="h-4 w-4" />
                  @hn_fm
                </a>
              </li>
            </ul>
          </div>
        </div>

        <!-- Bottom Section -->
        <div class="border-t mt-8 pt-6">
          <div class="flex flex-col md:flex-row justify-between items-center gap-4">
            <p class="text-xs text-muted-foreground">
              © {{ new Date().getFullYear() }} hn.fm. All rights reserved.
            </p>
            <div class="flex items-center gap-4">
              <a
                href="/privacy"
                class="text-xs text-muted-foreground hover:text-orange-600 transition-colors"
              >
                Privacy Policy
              </a>
              <a
                href="/terms"
                class="text-xs text-muted-foreground hover:text-orange-600 transition-colors"
              >
                Terms of Service
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>
