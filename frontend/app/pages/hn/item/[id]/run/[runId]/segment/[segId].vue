<template>
  <div class="min-h-screen bg-background">
    <!-- Navigation -->
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
      <!-- Back Button -->
      <div class="mb-6">
        <NuxtLink
          :to="`/hn/item/${itemId}/run/${runId}`"
          class="text-primary hover:text-primary/80 font-medium"
        >
          ← Back to Run {{ runId }}
        </NuxtLink>
      </div>

      <!-- Loading State -->
      <div v-if="isLoading" class="text-center py-8">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"/>
        <p class="mt-2 text-muted-foreground">Loading segment details...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="!!error" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded mb-4">
        {{ error }}
      </div>

      <!-- Success Message -->
      <div v-if="deleteMessage" class="bg-green-100 border border-green-300 text-green-800 px-4 py-3 rounded mb-4">
        {{ deleteMessage }}
      </div>

      <!-- Main Content -->
      <div v-else-if="!!item && !!segment" class="space-y-6">
        <!-- Item Info -->
        <div class="bg-card border rounded-lg p-6">
          <h1 class="text-3xl font-bold mb-4">{{ item.title || 'No Title' }}</h1>

          <div class="flex flex-wrap gap-2 mb-4 items-center justify-between">
            <div class="flex flex-wrap gap-2">
              <Badge class="bg-orange-500 text-white border-orange-500 text-sm">
                Item ID: {{ item.id }}
              </Badge>
              <Badge class="bg-blue-500 text-white border-blue-500 text-sm">
                Run: {{ segment.run }}
              </Badge>
              <Badge class="bg-purple-500 text-white border-purple-500 text-sm">
                Segment: {{ segment.seg }}
              </Badge>
              <Badge class="bg-green-500 text-white border-green-500 text-sm">
                {{ formatDateTime(segment.created_at) }}
              </Badge>
            </div>
            <Button
              variant="destructive"
              size="sm"
              :disabled="isDeleting"
              class="ml-auto bg-red-600 hover:bg-red-700 text-white border-red-600"
              @click="deleteSegment"
            >
              <span v-if="isDeleting">Deleting...</span>
              <span v-else>🗑️ Delete Segment</span>
            </Button>
          </div>

          <div v-if="item.url" class="mb-4">
            <a
              :href="item.url"
              target="_blank"
              rel="noopener noreferrer"
              class="text-primary hover:text-primary/80 font-medium break-all"
            >
              🔗 {{ item.url }}
            </a>
          </div>
        </div>

        <!-- Script Section -->
        <div class="bg-card border rounded-lg p-6">
          <h2 class="text-2xl font-bold mb-4">Script</h2>
          <div class="bg-muted/50 p-4 rounded-lg">
            <pre class="whitespace-pre-wrap text-sm text-foreground font-mono overflow-x-auto">{{ segment.script }}</pre>
          </div>
        </div>

        <!-- Audio Section -->
        <div class="bg-card border rounded-lg p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-2xl font-bold">Audio</h2>
            <Button
              variant="outline"
              size="sm"
              @click="toggleAudioExpanded"
              class="flex items-center gap-2"
            >
              <Icon :name="audioExpanded ? 'lucide:chevron-up' : 'lucide:chevron-down'" class="h-4 w-4" />
              {{ audioExpanded ? 'Collapse' : 'Expand' }}
            </Button>
          </div>

          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <Badge v-if="segment.audio_ready" class="bg-green-500 text-white border-green-500 text-xs">
                Audio Ready
              </Badge>
              <Badge v-else class="bg-yellow-500 text-white border-yellow-500 text-xs">
                No Audio
              </Badge>
              <Badge v-if="sections.length > 0" class="bg-blue-500 text-white border-blue-500 text-xs">
                {{ sections.length }} Sections
              </Badge>
            </div>
            <div class="flex gap-2">
              <Button
                v-if="segment.script && !isGeneratingAudio"
                size="sm"
                @click="generateAudio"
                class="bg-blue-600 hover:bg-blue-700 text-white border-blue-600"
              >
                <span v-if="isGeneratingAudio">Generating...</span>
                <span v-else>🎵 Generate Audio</span>
              </Button>
              <Button
                v-if="segment.audio_ready && !isRegeneratingAudio"
                size="sm"
                @click="regenerateAudio"
                class="bg-orange-600 hover:bg-orange-700 text-white border-orange-600"
              >
                <span v-if="isRegeneratingAudio">Regenerating...</span>
                <span v-else>🔄 Regenerate All</span>
              </Button>
            </div>
          </div>

          <!-- Expanded Audio Details -->
          <div v-if="audioExpanded" class="space-y-4">
            <!-- Combined Audio Player -->
            <div v-if="segment.audio_ready && segment.audio_combined_path" class="space-y-2">
              <h3 class="text-lg font-semibold">Combined Audio</h3>
              <div class="bg-muted/50 p-4 rounded-lg">
                <audio
                  controls
                  class="w-full"
                  :src="getCombinedAudioUrl()"
                >
                  Your browser does not support the audio element.
                </audio>
              </div>
            </div>

            <!-- Individual Sections -->
            <div v-if="sections.length > 0" class="space-y-4">
              <h3 class="text-lg font-semibold">Audio Sections</h3>
              <div class="space-y-3">
                <div
                  v-for="(section, index) in sections"
                  :key="section.section"
                  class="bg-muted/30 p-4 rounded-lg border"
                >
                  <div class="flex items-start justify-between mb-2">
                    <div class="flex items-center gap-2">
                      <Badge class="bg-purple-500 text-white border-purple-500 text-xs">
                        Section {{ section.section }}
                      </Badge>
                      <Badge v-if="section.cleaned" class="bg-green-500 text-white border-green-500 text-xs">
                        Cleaned
                      </Badge>
                      <Badge v-if="section.duration_ms" class="bg-gray-500 text-white border-gray-500 text-xs">
                        {{ formatDuration(section.duration_ms) }}
                      </Badge>
                    </div>
                    <div class="flex gap-2">
                      <Button
                        v-if="section.audio_path && !isRegeneratingSection[section.section]"
                        size="sm"
                        variant="outline"
                        @click="regenerateSection(section.section)"
                        class="text-orange-600 border-orange-600 hover:bg-orange-50"
                      >
                        <span v-if="isRegeneratingSection[section.section]">Regenerating...</span>
                        <span v-else>🔄</span>
                      </Button>
                    </div>
                  </div>

                  <!-- Section Text (Editable) -->
                  <div class="mb-3">
                    <label class="text-sm font-medium text-muted-foreground mb-1 block">
                      Text/Prompt:
                    </label>
                    <div v-if="!editingSection[section.section]" class="bg-background p-3 rounded border">
                      <p class="text-sm whitespace-pre-wrap">{{ section.text }}</p>
                      <Button
                        size="sm"
                        variant="ghost"
                        @click="startEditingSection(section.section)"
                        class="mt-2 text-blue-600 hover:text-blue-700"
                      >
                        ✏️ Edit
                      </Button>
                    </div>
                    <div v-else class="space-y-2">
                      <textarea
                        v-model="editingText[section.section]"
                        class="w-full p-3 border rounded-lg bg-background text-sm"
                        rows="3"
                        placeholder="Enter section text..."
                      />
                      <div class="flex gap-2">
                        <Button
                          size="sm"
                          @click="saveSectionText(section.section)"
                          :disabled="isSavingSection[section.section]"
                          class="bg-green-600 hover:bg-green-700 text-white"
                        >
                          <span v-if="isSavingSection[section.section]">Saving...</span>
                          <span v-else">💾 Save</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          @click="cancelEditingSection(section.section)"
                        >
                          ❌ Cancel
                        </Button>
                      </div>
                    </div>
                  </div>

                  <!-- Section Audio Player -->
                  <div v-if="section.audio_path" class="bg-muted/50 p-3 rounded">
                    <audio
                      controls
                      class="w-full"
                      :src="getSectionAudioUrl(section.section)"
                    >
                      Your browser does not support the audio element.
                    </audio>
                  </div>
                  <div v-else class="text-center py-4 text-muted-foreground">
                    <p class="text-sm">No audio generated for this section yet.</p>
                  </div>
                </div>
              </div>
            </div>

            <!-- No Sections Message -->
            <div v-else-if="segment.audio_ready && sections.length === 0" class="text-center py-8 text-muted-foreground">
              <p>No individual sections found. Audio may be generated as a single file.</p>
            </div>
          </div>
        </div>

        <!-- Images Section -->
        <div class="bg-card border rounded-lg p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-2xl font-bold">Images</h2>
            <Button
              variant="outline"
              size="sm"
              @click="toggleImagesExpanded"
              class="flex items-center gap-2"
            >
              <Icon :name="imagesExpanded ? 'lucide:chevron-up' : 'lucide:chevron-down'" class="h-4 w-4" />
              {{ imagesExpanded ? 'Collapse' : 'Expand' }}
            </Button>
          </div>

          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <Badge v-if="segment.images_ready" class="bg-green-500 text-white border-green-500 text-xs">
                {{ imageCount }} Images
              </Badge>
              <Badge v-else class="bg-yellow-500 text-white border-yellow-500 text-xs">
                No Images
              </Badge>
            </div>
            <div class="flex gap-2">
              <Button
                v-if="segment.script && !isGeneratingImages"
                size="sm"
                @click="generateImages"
                class="bg-green-600 hover:bg-green-700 text-white border-green-600"
              >
                <span v-if="isGeneratingImages">Generating...</span>
                <span v-else>🖼️ Generate Images</span>
              </Button>
              <Button
                v-if="segment.images_ready && !isRegeneratingImages"
                size="sm"
                @click="regenerateImages"
                class="bg-orange-600 hover:bg-orange-700 text-white border-orange-600"
              >
                <span v-if="isRegeneratingImages">Regenerating...</span>
                <span v-else>🔄 Regenerate All</span>
              </Button>
            </div>
          </div>

          <!-- Expanded Images Details -->
          <div v-if="imagesExpanded" class="space-y-4">
            <!-- Individual Images -->
            <div v-if="images.length > 0" class="space-y-4">
              <h3 class="text-lg font-semibold">Generated Images</h3>
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div
                  v-for="(image, index) in images"
                  :key="image.index"
                  class="bg-muted/30 p-4 rounded-lg border"
                >
                  <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center gap-2">
                      <Badge class="bg-purple-500 text-white border-purple-500 text-xs">
                        Image {{ image.index }}
                      </Badge>
                      <Badge v-if="image.duration_ms" class="bg-gray-500 text-white border-gray-500 text-xs">
                        {{ formatDuration(image.duration_ms) }}
                      </Badge>
                    </div>
                    <div class="flex gap-2">
                      <Button
                        v-if="image.image_path && !isRegeneratingImage[image.index]"
                        size="sm"
                        variant="outline"
                        @click="regenerateImage(image.index)"
                        class="text-orange-600 border-orange-600 hover:bg-orange-50"
                      >
                        <span v-if="isRegeneratingImage[image.index]">Regenerating...</span>
                        <span v-else>🔄</span>
                      </Button>
                    </div>
                  </div>

                  <!-- Image Display -->
                  <div v-if="image.image_path" class="mb-3">
                    <img
                      :src="getImageUrl(image.index)"
                      :alt="`Image ${image.index}`"
                      class="w-full h-48 object-cover rounded border"
                      @error="handleImageError"
                    />
                  </div>
                  <div v-else class="mb-3 bg-muted/50 p-8 rounded text-center text-muted-foreground">
                    <p class="text-sm">No image generated yet.</p>
                  </div>

                  <!-- Line Text (Editable) -->
                  <div class="mb-3">
                    <label class="text-sm font-medium text-muted-foreground mb-1 block">
                      Line Text:
                    </label>
                    <div v-if="!editingImageLine[image.index]" class="bg-background p-3 rounded border">
                      <p class="text-sm whitespace-pre-wrap">{{ image.line_text }}</p>
                      <Button
                        size="sm"
                        variant="ghost"
                        @click="startEditingImageLine(image.index)"
                        class="mt-2 text-blue-600 hover:text-blue-700"
                      >
                        ✏️ Edit
                      </Button>
                    </div>
                    <div v-else class="space-y-2">
                      <textarea
                        v-model="editingImageLineText[image.index]"
                        class="w-full p-3 border rounded-lg bg-background text-sm"
                        rows="2"
                        placeholder="Enter line text..."
                      />
                      <div class="flex gap-2">
                        <Button
                          size="sm"
                          @click="saveImageLineText(image.index)"
                          :disabled="isSavingImageLine[image.index]"
                          class="bg-green-600 hover:bg-green-700 text-white"
                        >
                          <span v-if="isSavingImageLine[image.index]">Saving...</span>
                          <span v-else">💾 Save</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          @click="cancelEditingImageLine(image.index)"
                        >
                          ❌ Cancel
                        </Button>
                      </div>
                    </div>
                  </div>

                  <!-- Prompt (Editable) -->
                  <div class="mb-3">
                    <label class="text-sm font-medium text-muted-foreground mb-1 block">
                      Prompt:
                    </label>
                    <div v-if="!editingImagePrompt[image.index]" class="bg-background p-3 rounded border">
                      <p class="text-sm whitespace-pre-wrap">{{ image.prompt }}</p>
                      <Button
                        size="sm"
                        variant="ghost"
                        @click="startEditingImagePrompt(image.index)"
                        class="mt-2 text-blue-600 hover:text-blue-700"
                      >
                        ✏️ Edit
                      </Button>
                    </div>
                    <div v-else class="space-y-2">
                      <textarea
                        v-model="editingImagePromptText[image.index]"
                        class="w-full p-3 border rounded-lg bg-background text-sm"
                        rows="3"
                        placeholder="Enter prompt..."
                      />
                      <div class="flex gap-2">
                        <Button
                          size="sm"
                          @click="saveImagePrompt(image.index)"
                          :disabled="isSavingImagePrompt[image.index]"
                          class="bg-green-600 hover:bg-green-700 text-white"
                        >
                          <span v-if="isSavingImagePrompt[image.index]">Saving...</span>
                          <span v-else">💾 Save</span>
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          @click="cancelEditingImagePrompt(image.index)"
                        >
                          ❌ Cancel
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- No Images Message -->
            <div v-else-if="segment.images_ready && images.length === 0" class="text-center py-8 text-muted-foreground">
              <p>No images found.</p>
            </div>
          </div>
        </div>

        <!-- Video Section -->
        <div class="bg-card border rounded-lg p-6">
          <h2 class="text-2xl font-bold mb-4">Video</h2>
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <Badge v-if="segment.video_ready" class="bg-green-500 text-white border-green-500 text-xs">
                Video Ready
              </Badge>
              <Badge v-else class="bg-yellow-500 text-white border-yellow-500 text-xs">
                No Video
              </Badge>
            </div>
            <Button
              v-if="segment.script && segment.audio_ready && segment.images_ready && !isGeneratingVideo"
              size="sm"
              @click="generateVideo"
              class="bg-purple-600 hover:bg-purple-700 text-white border-purple-600"
            >
              <span v-if="isGeneratingVideo">Generating...</span>
              <span v-else>🎬 Generate Video</span>
            </Button>
          </div>

          <div v-if="segment.video_ready && segment.video_path">
            <video
              controls
              width="100%"
              class="w-full max-w-4xl mx-auto rounded-lg border bg-black"
              :src="getVideoUrl(segment.video_path)"
            >
              <track
                v-if="segment.subtitles_path"
                kind="subtitles"
                srclang="en"
                label="English"
                :src="getVideoUrl(segment.subtitles_path)"
                default
              />
              Your browser does not support the video tag.
            </video>
          </div>
          <div v-else class="text-center py-8 text-muted-foreground">
            <p v-if="!segment.script">Generate script first to create video.</p>
            <p v-else-if="!segment.audio_ready">Generate audio first to create video.</p>
            <p v-else-if="!segment.images_ready">Generate images first to create video.</p>
            <p v-else>Video not generated yet. Click 'Generate Video' to create it.</p>
          </div>
        </div>
      </div>

      <!-- Not Found -->
      <div v-else class="text-center py-8 text-muted-foreground">
        Segment not found
      </div>
    </main>

    <!-- Footer -->
    <footer class="border-t bg-card mt-auto">
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

<script setup>
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Icon } from '#components'

// Define page meta
definePageMeta({
  layout: false
})

const route = useRoute()
const config = useRuntimeConfig()
const colorMode = useColorMode()

// Extract parameters with better error handling
const itemId = computed(() => {
  const id = route.params.id
  console.log('Raw item ID param:', id, 'Type:', typeof id)
  return parseInt(Array.isArray(id) ? id[0] : id)
})

const runId = computed(() => {
  const id = route.params.runId
  console.log('Raw run ID param:', id, 'Type:', typeof id)
  return parseInt(Array.isArray(id) ? id[0] : id)
})

const segId = computed(() => {
  const id = route.params.segId
  console.log('Raw segment ID param:', id, 'Type:', typeof id)
  return parseInt(Array.isArray(id) ? id[0] : id)
})

// Reactive data
const isLoading = ref(false)
const error = ref(null)
const deleteMessage = ref('')
const isDeleting = ref(false)

// Audio data
const isGeneratingAudio = ref(false)
const isRegeneratingAudio = ref(false)
const audioExpanded = ref(false)
const isRegeneratingSection = ref({})
const editingSection = ref({})
const editingText = ref({})
const isSavingSection = ref({})

// Image data
const isGeneratingImages = ref(false)
const isRegeneratingImages = ref(false)
const imagesExpanded = ref(false)
const isRegeneratingImage = ref({})
const editingImageLine = ref({})
const editingImageLineText = ref({})
const isSavingImageLine = ref({})
const editingImagePrompt = ref({})
const editingImagePromptText = ref({})
const isSavingImagePrompt = ref({})
const imageCount = ref(0)

// Video data
const isGeneratingVideo = ref(false)

// Fetch data
const { data: itemData, pending: itemLoading, error: itemError } = await useAsyncData(
  `item-${itemId.value}`,
  () => $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}`)
)

const { data: segmentData, pending: segmentLoading, error: segmentError, refresh: refreshSegment } = await useAsyncData(
  `segment-${itemId.value}-${runId.value}-${segId.value}`,
  () => $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}`)
)

const { data: sectionsData, pending: sectionsLoading, error: sectionsError, refresh: refreshSections } = await useAsyncData(
  `sections-${itemId.value}-${runId.value}-${segId.value}`,
  () => $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/sections`),
  {
    default: () => ({ sections: [] })
  }
)

const { data: imagesData, pending: imagesLoading, error: imagesError, refresh: refreshImages } = await useAsyncData(
  `images-${itemId.value}-${runId.value}-${segId.value}`,
  () => $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/images`),
  {
    default: () => ({ images: [] })
  }
)

// Computed properties
const item = computed(() => itemData.value)
const segment = computed(() => segmentData.value)
const sections = computed(() => sectionsData.value?.sections || [])
const images = computed(() => imagesData.value?.images || [])

// Set loading state
isLoading.value = itemLoading.value || segmentLoading.value || sectionsLoading.value || imagesLoading.value

// Set error state
if (itemError.value) {
  error.value = `Failed to load item: ${itemError.value.message}`
} else if (segmentError.value) {
  error.value = `Failed to load segment: ${segmentError.value.message}`
} else if (sectionsError.value) {
  error.value = `Failed to load sections: ${sectionsError.value.message}`
} else if (imagesError.value) {
  error.value = `Failed to load images: ${imagesError.value.message}`
}

// Audio methods
async function generateAudio() {
  if (isGeneratingAudio.value) return

  isGeneratingAudio.value = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/audio`, {
      method: 'POST'
    })

    console.log('Audio generation queued:', response)

    // Poll for completion
    await pollForAudio()
  } catch (err) {
    console.error('Failed to generate audio:', err)
    error.value = 'Failed to generate audio'
  } finally {
    isGeneratingAudio.value = false
  }
}

async function pollForAudio() {
  const maxAttempts = 30 // 30 seconds max
  let attempts = 0

  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 1000)) // Wait 1 second

    try {
      await refreshSegment()

      // Check if audio is ready now
      if (segment.value?.audio_ready) {
        console.log('Audio generated successfully')
        return
      }
    } catch (err) {
      console.error('Error polling for audio:', err)
    }

    attempts++
  }

  console.warn('Audio generation polling timed out')
}

// Audio UI methods
function toggleAudioExpanded() {
  audioExpanded.value = !audioExpanded.value
}

function getCombinedAudioUrl() {
  if (!segment.value?.audio_combined_path) return ''

  // Convert path to API URL
  // Example: outputs/hn/item/45106314/runs/1/segments/1/audio/segment.wav
  // -> /api/audio/45106314/1/1/segment.wav

  const match = segment.value.audio_combined_path.match(/\/item\/(\d+)\/runs\/(\d+)\/segments\/(\d+)\/audio\/(.+)$/)
  if (match) {
    const [, itemId, runId, segId, filename] = match
    return `${config.public.apiBase}/api/audio/${itemId}/${runId}/${segId}/${filename}`
  }

  return segment.value.audio_combined_path
}

function getSectionAudioUrl(sectionNumber) {
  return `${config.public.apiBase}/api/audio/${itemId.value}/${runId.value}/${segId.value}/section_${sectionNumber}.wav`
}

function formatDuration(durationMs) {
  if (!durationMs) return 'Unknown'

  const seconds = Math.floor(durationMs / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60

  if (minutes > 0) {
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
  }
  return `${seconds}s`
}

// Regenerate all audio
async function regenerateAudio() {
  if (isRegeneratingAudio.value) return

  isRegeneratingAudio.value = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/audio`, {
      method: 'POST'
    })

    console.log('Audio regeneration queued:', response)

    // Poll for completion
    await pollForAudio()
  } catch (err) {
    console.error('Failed to regenerate audio:', err)
    error.value = 'Failed to regenerate audio'
  } finally {
    isRegeneratingAudio.value = false
  }
}

// Regenerate individual section
async function regenerateSection(sectionNumber) {
  if (isRegeneratingSection.value[sectionNumber]) return

  isRegeneratingSection.value[sectionNumber] = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/sections/${sectionNumber}/audio`, {
      method: 'POST'
    })

    console.log('Section audio regeneration queued:', response)

    // Poll for completion
    await pollForSection(sectionNumber)
  } catch (err) {
    console.error('Failed to regenerate section audio:', err)
    error.value = 'Failed to regenerate section audio'
  } finally {
    isRegeneratingSection.value[sectionNumber] = false
  }
}

async function pollForSection(sectionNumber) {
  const maxAttempts = 30 // 30 seconds max
  let attempts = 0

  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 1000)) // Wait 1 second

    try {
      await refreshSections()

      // Check if section has audio now
      const section = sections.value.find(s => s.section === sectionNumber)
      if (section?.audio_path) {
        console.log('Section audio generated successfully')
        return
      }
    } catch (err) {
      console.error('Error polling for section audio:', err)
    }

    attempts++
  }

  console.warn('Section audio generation polling timed out')
}

// Section text editing
function startEditingSection(sectionNumber) {
  const section = sections.value.find(s => s.section === sectionNumber)
  if (section) {
    editingSection.value[sectionNumber] = true
    editingText.value[sectionNumber] = section.text
  }
}

function cancelEditingSection(sectionNumber) {
  editingSection.value[sectionNumber] = false
  editingText.value[sectionNumber] = ''
}

async function saveSectionText(sectionNumber) {
  if (isSavingSection.value[sectionNumber]) return

  isSavingSection.value[sectionNumber] = true

  try {
    // TODO: Implement API endpoint for updating section text
    // For now, just update locally
    const sectionIndex = sections.value.findIndex(s => s.section === sectionNumber)
    if (sectionIndex !== -1) {
      sections.value[sectionIndex].text = editingText.value[sectionNumber]
    }

    editingSection.value[sectionNumber] = false
    editingText.value[sectionNumber] = ''

    console.log('Section text updated locally (API endpoint needed)')
  } catch (err) {
    console.error('Failed to save section text:', err)
    error.value = 'Failed to save section text'
  } finally {
    isSavingSection.value[sectionNumber] = false
  }
}

// Image methods
async function generateImages() {
  if (isGeneratingImages.value) return

  isGeneratingImages.value = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/images`, {
      method: 'POST'
    })

    console.log('Image generation queued:', response)

    // Poll for completion
    await pollForImages()
  } catch (err) {
    console.error('Failed to generate images:', err)
    error.value = 'Failed to generate images'
  } finally {
    isGeneratingImages.value = false
  }
}

async function pollForImages() {
  const maxAttempts = 60 // 60 seconds max (image generation takes longer)
  let attempts = 0

  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 2000)) // Wait 2 seconds

    try {
      await refreshSegment()

      // Check if images are ready now
      if (segment.value?.images_ready) {
        console.log('Images generated successfully')
        return
      }
    } catch (err) {
      console.error('Error polling for images:', err)
    }

    attempts++
  }

  console.warn('Image generation polling timed out')
}

// Image UI methods
function toggleImagesExpanded() {
  imagesExpanded.value = !imagesExpanded.value
}

function getImageUrl(imageIndex) {
  return `${config.public.apiBase}/api/images/${itemId.value}/${runId.value}/${segId.value}/${imageIndex}/image.png`
}

function handleImageError(event) {
  console.error('Image failed to load:', event.target.src)
  // You could set a fallback image or show an error state
}

// Regenerate all images
async function regenerateImages() {
  if (isRegeneratingImages.value) return

  isRegeneratingImages.value = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/images`, {
      method: 'POST'
    })

    console.log('Image regeneration queued:', response)

    // Poll for completion
    await pollForImages()
  } catch (err) {
    console.error('Failed to regenerate images:', err)
    error.value = 'Failed to regenerate images'
  } finally {
    isRegeneratingImages.value = false
  }
}

// Regenerate individual image
async function regenerateImage(imageIndex) {
  if (isRegeneratingImage.value[imageIndex]) return

  isRegeneratingImage.value[imageIndex] = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/images/${imageIndex}`, {
      method: 'POST'
    })

    console.log('Image regeneration queued:', response)

    // Poll for completion
    await pollForImage(imageIndex)
  } catch (err) {
    console.error('Failed to regenerate image:', err)
    error.value = 'Failed to regenerate image'
  } finally {
    isRegeneratingImage.value[imageIndex] = false
  }
}

async function pollForImage(imageIndex) {
  const maxAttempts = 30 // 30 seconds max
  let attempts = 0

  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 1000)) // Wait 1 second

    try {
      await refreshImages()

      // Check if image has been regenerated
      const image = images.value.find(img => img.index === imageIndex)
      if (image?.image_path) {
        console.log('Image regenerated successfully')
        return
      }
    } catch (err) {
      console.error('Error polling for image:', err)
    }

    attempts++
  }

  console.warn('Image regeneration polling timed out')
}

// Image line text editing
function startEditingImageLine(imageIndex) {
  const image = images.value.find(img => img.index === imageIndex)
  if (image) {
    editingImageLine.value[imageIndex] = true
    editingImageLineText.value[imageIndex] = image.line_text
  }
}

function cancelEditingImageLine(imageIndex) {
  editingImageLine.value[imageIndex] = false
  editingImageLineText.value[imageIndex] = ''
}

async function saveImageLineText(imageIndex) {
  if (isSavingImageLine.value[imageIndex]) return

  isSavingImageLine.value[imageIndex] = true

  try {
    // TODO: Implement API endpoint for updating image line text
    // For now, just update locally
    const imageIndexInArray = images.value.findIndex(img => img.index === imageIndex)
    if (imageIndexInArray !== -1) {
      images.value[imageIndexInArray].line_text = editingImageLineText.value[imageIndex]
    }

    editingImageLine.value[imageIndex] = false
    editingImageLineText.value[imageIndex] = ''

    console.log('Image line text updated locally (API endpoint needed)')
  } catch (err) {
    console.error('Failed to save image line text:', err)
    error.value = 'Failed to save image line text'
  } finally {
    isSavingImageLine.value[imageIndex] = false
  }
}

// Image prompt editing
function startEditingImagePrompt(imageIndex) {
  const image = images.value.find(img => img.index === imageIndex)
  if (image) {
    editingImagePrompt.value[imageIndex] = true
    editingImagePromptText.value[imageIndex] = image.prompt
  }
}

function cancelEditingImagePrompt(imageIndex) {
  editingImagePrompt.value[imageIndex] = false
  editingImagePromptText.value[imageIndex] = ''
}

async function saveImagePrompt(imageIndex) {
  if (isSavingImagePrompt.value[imageIndex]) return

  isSavingImagePrompt.value[imageIndex] = true

  try {
    // TODO: Implement API endpoint for updating image prompt
    // For now, just update locally
    const imageIndexInArray = images.value.findIndex(img => img.index === imageIndex)
    if (imageIndexInArray !== -1) {
      images.value[imageIndexInArray].prompt = editingImagePromptText.value[imageIndex]
    }

    editingImagePrompt.value[imageIndex] = false
    editingImagePromptText.value[imageIndex] = ''

    console.log('Image prompt updated locally (API endpoint needed)')
  } catch (err) {
    console.error('Failed to save image prompt:', err)
    error.value = 'Failed to save image prompt'
  } finally {
    isSavingImagePrompt.value[imageIndex] = false
  }
}

// Video methods
function getVideoUrl(videoPath) {
  if (!videoPath) return ''

  // Convert absolute path to API URL
  // Example: outputs/hn/item/45106314/runs/1/segments/1/video/segment.mp4
  // -> /api/video/45106314/1/1/segment.mp4

  const match = videoPath.match(/\/item\/(\d+)\/runs\/(\d+)\/segments\/(\d+)\/video\/(.+)$/)
  if (match) {
    const [, itemId, runId, segId, filename] = match
    return `${config.public.apiBase}/api/video/${itemId}/${runId}/${segId}/${filename}`
  }

  // Fallback to original path if pattern doesn't match
  return videoPath
}

async function generateVideo() {
  if (isGeneratingVideo.value) return

  isGeneratingVideo.value = true

  try {
    const response = await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}/video`, {
      method: 'POST'
    })

    console.log('Video generation queued:', response)

    // Poll for completion
    await pollForVideo()
  } catch (err) {
    console.error('Failed to generate video:', err)
    error.value = 'Failed to generate video'
  } finally {
    isGeneratingVideo.value = false
  }
}

async function pollForVideo() {
  const maxAttempts = 60 // 60 seconds max (video generation takes longer)
  let attempts = 0

  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 2000)) // Wait 2 seconds

    try {
      await refreshSegment()

      // Check if video is ready now
      if (segment.value?.video_ready) {
        console.log('Video generated successfully')
        return
      }
    } catch (err) {
      console.error('Error polling for video:', err)
    }

    attempts++
  }

  console.warn('Video generation polling timed out')
}

// Delete methods
async function deleteSegment() {
  if (isDeleting.value) return

  if (!confirm('Are you sure you want to delete this segment? This action cannot be undone.')) {
    return
  }

  isDeleting.value = true

  try {
    await $fetch(`${config.public.apiBase}/api/hn/items/${itemId.value}/runs/${runId.value}/segments/${segId.value}`, {
      method: 'DELETE'
    })

    deleteMessage.value = 'Segment deleted successfully'

    // Redirect back to run page after a short delay
    setTimeout(() => {
      navigateTo(`/hn/item/${itemId.value}/run/${runId.value}`)
    }, 2000)
  } catch (err) {
    console.error('Failed to delete segment:', err)
    error.value = 'Failed to delete segment'
  } finally {
    isDeleting.value = false
  }
}

// Utility functions
function formatDateTime(dateString) {
  if (!dateString) return 'Unknown'

  try {
    const date = new Date(dateString)
    return date.toLocaleString()
  } catch (err) {
    console.error('Error formatting date:', err)
    return 'Invalid Date'
  }
}

// Watch for image count changes
watch(() => images.value?.length, (newCount) => {
  if (newCount !== undefined) {
    imageCount.value = newCount
  }
}, { immediate: true })

// Load images when component mounts
onMounted(() => {
  if (images.value?.length) {
    imageCount.value = images.value.length
  }
})
</script>