<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Icon } from '#components'
import PaginationBar from '~/components/PaginationBar.vue'
import { usePaginatedFetch } from '~/composables/usePaginatedFetch'

interface Story {
  id: number
  type: string | null
  by: string | null
  time: number | null
  url: string | null
  title: string | null
  text: string | null
  score: number | null
  descendants: number | null
  kids: number[] | null
  runs_count: number
  segments_count: number
  videos_count: number
  latest_activity: string | null
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const {
  rows,
  pending,
  error,
  page,
  limit,
  total,
  totalPages,
  hasNextPage,
  hasPreviousPage,
  setPage,
  nextPage,
  previousPage,
  sort,
  dir,
  filters,
  toggleSort,
  setSearch,
  setFilter,
  refresh,
} = usePaginatedFetch<Story>({
  endpoint: '/api/stories',
  syncQuery: true,
  defaultSort: 'id',
  filters: { has_video: undefined, has_runs: undefined },
})

function firstPage() {
  setPage(1)
}
function lastPage() {
  setPage(totalPages.value)
}

// ── columns ─────────────────────────────────────────────────────────────────

interface Column {
  label: string
  sortKey?: string
  thClass?: string
}

const columns: Column[] = [
  { label: 'Score', sortKey: 'score', thClass: 'w-16 text-right' },
  { label: 'Title', sortKey: 'id' },
  { label: 'By', thClass: 'w-32' },
  { label: 'Age', sortKey: 'time', thClass: 'w-20' },
  { label: 'Comments', sortKey: 'comments', thClass: 'w-24 text-right' },
  { label: 'Runs', sortKey: 'runs', thClass: 'w-16 text-right' },
  { label: 'Segs', sortKey: 'segments', thClass: 'w-16 text-right' },
  { label: 'Videos', sortKey: 'videos', thClass: 'w-20 text-right' },
  { label: 'Latest', sortKey: 'latest', thClass: 'w-24' },
  { label: 'Actions', thClass: 'w-36' },
]

function sortIndicator(key?: string): string {
  if (!key || sort.value !== key) return ''
  return dir.value === 'asc' ? '▲' : '▼'
}

// ── search ──────────────────────────────────────────────────────────────────

const searchInput = ref('')
function onSearch(value: string | number) {
  setSearch(String(value ?? ''))
}

// ── filter chips ────────────────────────────────────────────────────────────

type ChipKey = 'all' | 'has_video' | 'no_video' | 'ungenerated'

const chips: { key: ChipKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'has_video', label: 'Has video' },
  { key: 'no_video', label: 'No video' },
  { key: 'ungenerated', label: 'Un-generated' },
]

const activeChip = computed<ChipKey>(() => {
  if (filters.has_video === true) return 'has_video'
  if (filters.has_video === false) return 'no_video'
  if (filters.has_runs === false) return 'ungenerated'
  return 'all'
})

function applyChip(chip: ChipKey) {
  setFilter('has_video', chip === 'has_video' ? true : chip === 'no_video' ? false : undefined)
  setFilter('has_runs', chip === 'ungenerated' ? false : undefined)
}

// ── queue actions ───────────────────────────────────────────────────────────

const queueBusy = ref<'top' | 'new' | null>(null)
const queueFeedback = ref('')

async function queueStories(kind: 'top' | 'new') {
  queueBusy.value = kind
  queueFeedback.value = ''
  try {
    const res = await $fetch<{ queued_count?: number; skipped_count?: number }>(
      `${apiBase}/api/hn/queue-${kind}?limit=20`,
      { method: 'POST' },
    )
    queueFeedback.value = `Queued ${res?.queued_count ?? 0} · skipped ${res?.skipped_count ?? 0}`
    await refresh()
  } catch {
    queueFeedback.value = `Failed to queue ${kind} stories`
  } finally {
    queueBusy.value = null
  }
}

// ── fetch item by ID ────────────────────────────────────────────────────────

const fetchItemId = ref<string | number>('')
const fetchBusy = ref(false)
const fetchFeedback = ref('')

async function fetchItemById() {
  const id = Number(fetchItemId.value)
  if (!id) return
  fetchBusy.value = true
  fetchFeedback.value = ''
  try {
    const res = await $fetch<{ status?: string }>(
      `${apiBase}/api/hn/process-item?item_id=${id}`,
      { method: 'POST' },
    )
    fetchFeedback.value = res?.status === 'exists'
      ? `Item ${id} already exists`
      : `Item ${id} queued for fetching`
    fetchItemId.value = ''
    setTimeout(() => refresh(), 1000)
  } catch {
    fetchFeedback.value = `Failed to fetch item ${id}`
  } finally {
    fetchBusy.value = false
  }
}

// ── per-row generate ────────────────────────────────────────────────────────

const generating = ref(new Set<number>())
const rowFeedback = ref<Record<number, 'queued' | 'error'>>({})

async function generate(itemId: number) {
  if (generating.value.has(itemId)) return
  generating.value.add(itemId)
  try {
    await $fetch(`${apiBase}/api/hn/single-task-pipeline`, {
      method: 'POST',
      body: { item_id: itemId },
    })
    rowFeedback.value[itemId] = 'queued'
  } catch {
    rowFeedback.value[itemId] = 'error'
  } finally {
    generating.value.delete(itemId)
    setTimeout(() => {
      // Rebuilt without the key rather than deleted: a dynamic delete on a
      // reactive object is both a lint error and a deopt.
      const { [itemId]: _removed, ...rest } = rowFeedback.value
      rowFeedback.value = rest
    }, 4000)
  }
}

// ── helpers ─────────────────────────────────────────────────────────────────

function domain(url: string | null): string {
  if (!url) return ''
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

function relTime(ms: number): string {
  const s = Math.max(0, Math.floor((Date.now() - ms) / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h`
  const d = Math.floor(h / 24)
  if (d < 30) return `${d}d`
  const mo = Math.floor(d / 30)
  if (mo < 12) return `${mo}mo`
  return `${Math.floor(mo / 12)}y`
}

function ageFromUnix(time: number | null): string {
  if (!time) return '—'
  return relTime(time * 1000)
}

function ageFromIso(iso: string | null): string {
  if (!iso) return '—'
  const ms = new Date(iso).getTime()
  if (Number.isNaN(ms)) return '—'
  return relTime(ms)
}

function goToItem(id: number) {
  navigateTo(`/hn/item/${id}`)
}
</script>

<template>
  <div class="h-full flex flex-col">
    <!-- Toolbar -->
    <div class="shrink-0 border-b bg-card px-4 py-3 space-y-2.5">
      <div class="flex flex-wrap items-center gap-3">
        <h1 class="text-lg font-bold text-primary">Stories</h1>

        <div class="relative w-64">
          <Icon
            name="lucide:search"
            class="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            v-model="searchInput"
            type="search"
            placeholder="Search titles…"
            class="h-8 pl-8"
            @update:model-value="onSearch"
          />
        </div>

        <!-- Filter chips -->
        <div class="flex items-center gap-1">
          <button
            v-for="chip in chips"
            :key="chip.key"
            type="button"
            class="rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
            :class="activeChip === chip.key
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-border bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground'"
            @click="applyChip(chip.key)"
          >
            {{ chip.label }}
          </button>
        </div>

        <div class="ml-auto flex flex-wrap items-center gap-2">
          <span v-if="queueFeedback" class="text-xs text-muted-foreground">
            {{ queueFeedback }}
          </span>
          <Button
            size="sm"
            class="h-8 bg-primary text-primary-foreground hover:bg-primary/90"
            :disabled="queueBusy !== null"
            @click="queueStories('top')"
          >
            <Icon v-if="queueBusy === 'top'" name="lucide:loader-2" class="mr-1 h-3.5 w-3.5 animate-spin" />
            Queue Top 20
          </Button>
          <Button
            size="sm"
            variant="outline"
            class="h-8 border-running-border bg-running-bg text-running hover:bg-running-bg/70"
            :disabled="queueBusy !== null"
            @click="queueStories('new')"
          >
            <Icon v-if="queueBusy === 'new'" name="lucide:loader-2" class="mr-1 h-3.5 w-3.5 animate-spin" />
            Queue New 20
          </Button>

          <!-- Fetch item by ID -->
          <div class="flex items-center gap-1.5">
            <Input
              v-model="fetchItemId"
              type="number"
              placeholder="Item ID"
              class="h-8 w-28 tabular-nums"
              :disabled="fetchBusy"
              @keyup.enter="fetchItemById"
            />
            <Button
              size="sm"
              variant="outline"
              class="h-8"
              :disabled="!fetchItemId || fetchBusy"
              @click="fetchItemById"
            >
              <Icon v-if="fetchBusy" name="lucide:loader-2" class="mr-1 h-3.5 w-3.5 animate-spin" />
              Fetch
            </Button>
          </div>
          <span v-if="fetchFeedback" class="text-xs text-muted-foreground">
            {{ fetchFeedback }}
          </span>
        </div>
      </div>

      <div
        v-if="error"
        class="rounded border border-destructive bg-destructive/10 px-3 py-1.5 text-xs text-destructive"
      >
        Failed to load stories. Is the API running?
      </div>
    </div>

    <!-- Table -->
    <div class="min-h-0 flex-1 overflow-auto">
      <table class="w-full text-sm" :class="pending && rows.length ? 'opacity-60' : ''">
        <thead class="sticky top-0 z-10 bg-card shadow-[inset_0_-1px_0_hsl(var(--border))]">
          <tr>
            <th
              v-for="col in columns"
              :key="col.label"
              class="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground"
              :class="[col.thClass, col.sortKey ? 'cursor-pointer select-none hover:text-foreground' : '']"
              @click="col.sortKey && toggleSort(col.sortKey)"
            >
              <span :class="sort === col.sortKey ? 'text-primary' : ''">
                {{ col.label }}
                <span v-if="sortIndicator(col.sortKey)" class="text-[10px]">{{ sortIndicator(col.sortKey) }}</span>
              </span>
            </th>
          </tr>
        </thead>

        <tbody class="divide-y divide-border">
          <!-- loading skeleton -->
          <template v-if="pending && rows.length === 0">
            <tr v-for="n in 12" :key="`skeleton-${n}`">
              <td v-for="col in columns" :key="col.label" class="px-3 py-2">
                <div class="h-4 animate-pulse rounded bg-muted" />
              </td>
            </tr>
          </template>

          <tr
            v-for="story in rows"
            :key="story.id"
            class="cursor-pointer transition-colors hover:bg-muted/60"
            @click="goToItem(story.id)"
          >
            <!-- Score -->
            <td class="px-3 py-2 text-right tabular-nums text-foreground">
              {{ story.score ?? 0 }}
            </td>

            <!-- Title + domain -->
            <td class="max-w-0 px-3 py-2">
              <div class="flex items-baseline gap-2">
                <NuxtLink
                  :to="`/hn/item/${story.id}`"
                  class="truncate font-semibold text-foreground hover:text-primary"
                  @click.stop
                >
                  {{ story.title || `Item ${story.id}` }}
                </NuxtLink>
                <a
                  v-if="story.url"
                  :href="story.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="shrink-0 truncate text-xs text-muted-foreground hover:text-primary"
                  @click.stop
                >
                  {{ domain(story.url) }}
                </a>
              </div>
            </td>

            <!-- By -->
            <td class="max-w-32 truncate px-3 py-2 text-muted-foreground">
              {{ story.by || '—' }}
            </td>

            <!-- Age -->
            <td class="whitespace-nowrap px-3 py-2 tabular-nums text-muted-foreground" :title="story.time ? new Date(story.time * 1000).toLocaleString() : ''">
              {{ ageFromUnix(story.time) }}
            </td>

            <!-- Comments -->
            <td class="px-3 py-2 text-right tabular-nums text-muted-foreground">
              {{ story.descendants ?? 0 }}
            </td>

            <!-- Runs -->
            <td class="px-3 py-2 text-right tabular-nums" :class="story.runs_count > 0 ? 'text-foreground' : 'text-muted-foreground/50'">
              {{ story.runs_count }}
            </td>

            <!-- Segs -->
            <td class="px-3 py-2 text-right tabular-nums" :class="story.segments_count > 0 ? 'text-foreground' : 'text-muted-foreground/50'">
              {{ story.segments_count }}
            </td>

            <!-- Videos -->
            <td class="px-3 py-2 text-right tabular-nums">
              <span
                v-if="story.videos_count > 0"
                class="inline-flex items-center rounded-full bg-ok-bg px-2 py-0.5 text-xs font-medium text-ok"
              >
                {{ story.videos_count }}
              </span>
              <span v-else class="text-muted-foreground/50">0</span>
            </td>

            <!-- Latest -->
            <td class="whitespace-nowrap px-3 py-2 tabular-nums text-muted-foreground" :title="story.latest_activity || ''">
              {{ ageFromIso(story.latest_activity) }}
            </td>

            <!-- Actions -->
            <td class="whitespace-nowrap px-3 py-2" @click.stop>
              <div class="flex items-center gap-1.5">
                <Button
                  size="sm"
                  variant="outline"
                  class="h-7 px-2 text-xs"
                  :disabled="generating.has(story.id)"
                  @click="generate(story.id)"
                >
                  <Icon
                    v-if="generating.has(story.id)"
                    name="lucide:loader-2"
                    class="mr-1 h-3 w-3 animate-spin"
                  />
                  Generate
                </Button>
                <span v-if="rowFeedback[story.id] === 'queued'" class="text-xs text-ok">
                  Queued
                </span>
                <span v-else-if="rowFeedback[story.id] === 'error'" class="text-xs text-destructive">
                  Failed
                </span>
                <NuxtLink
                  v-if="story.videos_count > 0"
                  :to="`/hn/item/${story.id}`"
                  class="rounded px-1.5 py-0.5 text-sm text-ok hover:bg-ok-bg "
                  title="Watch videos"
                >
                  ▶
                </NuxtLink>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- empty state -->
      <div v-if="!pending && rows.length === 0" class="py-16 text-center text-muted-foreground">
        <Icon name="lucide:inbox" class="mx-auto mb-2 h-8 w-8 opacity-50" />
        <p>No stories found. Try queuing some top stories!</p>
      </div>
    </div>

    <!-- Pagination -->
    <div class="shrink-0 border-t bg-card px-4 py-2">
      <PaginationBar
        :page="page"
        :total="total"
        :limit="limit"
        :total-pages="totalPages"
        :has-next-page="hasNextPage"
        :has-previous-page="hasPreviousPage"
        :set-page="setPage"
        :next-page="nextPage"
        :previous-page="previousPage"
        :first-page="firstPage"
        :last-page="lastPage"
      />
    </div>
  </div>
</template>
