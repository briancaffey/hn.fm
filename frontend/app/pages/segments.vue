<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { usePagination } from '~/composables/usePagination'
import PaginationBar from '~/components/PaginationBar.vue'
import SegmentCard from '~/components/SegmentCard.vue'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import EmptyState from '~/components/kit/EmptyState.vue'
import LoadingRows from '~/components/kit/LoadingRows.vue'
import { Button } from '~/components/ui/button'
import { Icon } from '#components'

useHead({ title: 'hn.fm · Segments' })
definePageMeta({ ssr: false })

interface Segment {
  item_id: number
  run: number
  seg: number
  audio_ready?: boolean
  images_ready?: boolean
  video_ready?: boolean
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const segments = ref<Segment[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)

const pagination = usePagination({
  initialPage: 1,
  initialLimit: 20,
  onPageChange: () => fetchSegments(),
})

async function fetchSegments() {
  isLoading.value = true
  error.value = null
  try {
    const res = await $fetch<{ segments?: Segment[], pagination?: { total?: number } }>(
      `${apiBase}/api/segments?offset=${pagination.offset.value}&limit=${pagination.limit.value}`,
    )
    segments.value = res.segments || []
    if (res.pagination?.total !== undefined) pagination.setTotal(res.pagination.total)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error'
    segments.value = []
  } finally {
    isLoading.value = false
  }
}
onMounted(fetchSegments)

const finished = computed(() => segments.value.filter(s => s.video_ready).length)
</script>

<template>
  <PageShell>
    <PageHeader
      title="Segments"
      subtitle="Every piece of content the pipeline has produced, newest first."
      hint="A segment is one finished take from one run of one story: its own script, audio, images and video. A story can have several runs, and a run several segments — that is how you get a 16:9 and a 9:16 cut, or two different treatments, of the same material."
      :meta="isLoading ? [] : [
        `${pagination.total.value} total`,
        `${finished} with video on this page`,
      ]"
    >
      <template #actions>
        <Button variant="outline" size="sm" :disabled="isLoading" @click="fetchSegments()">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" :class="isLoading ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <LoadingRows v-if="isLoading && !segments.length" :rows="4" height="h-40" />

    <div
      v-else-if="error"
      class="rounded-lg border border-danger-border bg-danger-bg px-4 py-3 text-sm text-danger"
    >
      <p class="font-medium">Could not load segments</p>
      <p class="mt-0.5 text-xs">{{ error }}</p>
      <Button variant="outline" size="sm" class="mt-3" @click="fetchSegments()">Try again</Button>
    </div>

    <EmptyState
      v-else-if="!segments.length"
      icon="lucide:layers"
      title="No segments yet"
      body="Segments appear once a story has been generated. Pick something from Triage and start a run, or queue fresh stories from Stories."
    >
      <template #action>
        <Button as-child size="sm"><NuxtLink to="/triage">Go to Triage</NuxtLink></Button>
      </template>
    </EmptyState>

    <template v-else>
      <div class="grid gap-3">
        <SegmentCard
          v-for="s in segments"
          :key="`${s.item_id}-${s.run}-${s.seg}`"
          :segment="s"
        />
      </div>
      <div class="mt-6">
        <PaginationBar
          :page="pagination.page" :total="pagination.total" :limit="pagination.limit"
          :total-pages="pagination.totalPages" :has-next-page="pagination.hasNextPage"
          :has-previous-page="pagination.hasPreviousPage" :set-page="pagination.setPage"
          :next-page="pagination.nextPage" :previous-page="pagination.previousPage"
          :first-page="pagination.firstPage" :last-page="pagination.lastPage"
        />
      </div>
    </template>
  </PageShell>
</template>
