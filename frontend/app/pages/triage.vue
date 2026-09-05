<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Icon } from '#components'
import PaginationBar from '~/components/PaginationBar.vue'
import PageShell from '~/components/kit/PageShell.vue'
import InfoHint from '~/components/kit/InfoHint.vue'
import TriageRow from '~/components/TriageRow.vue'
import type { TriageItem } from '~/components/TriageRow.vue'
import { usePaginatedFetch } from '~/composables/usePaginatedFetch'

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
  filters,
  setSearch,
  setFilter,
  refresh,
} = usePaginatedFetch<TriageItem>({
  endpoint: '/api/triage',
  syncQuery: true,
  defaultLimit: 25,
  filters: {
    verdict: undefined,
    include_generated: undefined,
    include_rejected: undefined,
    bucket: undefined,
  },
})

function firstPage() {
  setPage(1)
}
function lastPage() {
  setPage(totalPages.value)
}

// ── search ──────────────────────────────────────────────────────────────────

const searchInput = ref('')
function onSearch(value: string | number) {
  setSearch(String(value ?? ''))
}

// ── verdict filter chips ────────────────────────────────────────────────────

const verdictChips: { value: string | undefined; label: string }[] = [
  { value: undefined, label: 'All' },
  { value: 'great', label: 'Great' },
  { value: 'good', label: 'Good' },
  { value: 'marginal', label: 'Marginal' },
  { value: 'unsuitable', label: 'Unsuitable' },
]

function applyVerdict(value: string | undefined) {
  setFilter('verdict', value)
}

// ── "needs better source" bucket ────────────────────────────────────────────
// High interest, low producibility: worth making, but the scrape was too thin.
// A fix-the-scrape queue, not a reject pile (plans/09).

const needsSourceOn = computed(() => filters.bucket === 'needs_better_source')

function toggleNeedsSource() {
  setFilter('bucket', needsSourceOn.value ? undefined : 'needs_better_source')
}

// ── include toggles ─────────────────────────────────────────────────────────

function toggleInclude(key: 'include_generated' | 'include_rejected') {
  setFilter(key, filters[key] ? undefined : true)
}

// ── pull / score actions ────────────────────────────────────────────────────

const actionBusy = ref<'top' | 'new' | 'score' | null>(null)
const actionFeedback = ref('')
const lastActionAt = ref<number | null>(null)

async function pullStories(kind: 'top' | 'new') {
  actionBusy.value = kind
  actionFeedback.value = ''
  try {
    const res = await $fetch<{ queued_count?: number; skipped_count?: number }>(
      `${apiBase}/api/hn/queue-${kind}?limit=20`,
      { method: 'POST' },
    )
    actionFeedback.value = `Queued ${res?.queued_count ?? 0} · skipped ${res?.skipped_count ?? 0}`
    lastActionAt.value = Date.now()
    await refresh()
  } catch {
    actionFeedback.value = `Failed to pull ${kind} stories`
  } finally {
    actionBusy.value = null
  }
}

async function scoreBacklog() {
  actionBusy.value = 'score'
  actionFeedback.value = ''
  try {
    const res = await $fetch<{ queued_count?: number; queued_ids?: number[] }>(
      `${apiBase}/api/triage/score-existing?limit=25`,
      { method: 'POST' },
    )
    actionFeedback.value = `Scoring queued for ${res?.queued_count ?? 0} stories`
    lastActionAt.value = Date.now()
  } catch {
    actionFeedback.value = 'Failed to queue backlog scoring'
  } finally {
    actionBusy.value = null
  }
}

// ── gentle polling: only while a recent pull/score may still be landing ─────

const POLL_MS = 15_000
const POLL_WINDOW_MS = 2 * 60_000
let pollTimer: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  pollTimer = setInterval(() => {
    if (
      lastActionAt.value
      && Date.now() - lastActionAt.value < POLL_WINDOW_MS
      && document.visibilityState === 'visible'
    ) {
      refresh()
    }
  }, POLL_MS)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

// ── rank numbering ──────────────────────────────────────────────────────────

const rankBase = computed(() => (page.value - 1) * limit.value)
</script>

<template>
  <PageShell variant="board">
    <template #header>
      <div class="shrink-0 border-b bg-card px-[var(--page-gutter)] py-3 space-y-2.5">
      <div class="flex flex-wrap items-center gap-3">
        <div>
          <div class="flex items-baseline gap-1.5">
            <h1 class="text-base font-semibold leading-tight">Triage</h1>
            <InfoHint
              side="right"
              text="The decision queue. Every scored story, ranked. Interest is how much a reader would care; producibility is how much there is to actually build from, and it gets capped automatically when the scrape came back thin — so a great headline with no article behind it cannot rank well. Your thumbs override the model's call and feed back into future scoring."
            />
          </div>
          <p class="text-xs text-muted-foreground">Ranked by interest × producibility. Sorted best-first.</p>
        </div>

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

        <!-- Verdict filter chips -->
        <div class="flex items-center gap-1">
          <button
            v-for="chip in verdictChips"
            :key="chip.label"
            type="button"
            class="rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
            :class="filters.verdict === chip.value
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-border bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground'"
            @click="applyVerdict(chip.value)"
          >
            {{ chip.label }}
          </button>
        </div>

        <!-- Needs-better-source bucket -->
        <button
          type="button"
          class="flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
          :class="needsSourceOn
            ? 'border-stale-border bg-stale text-background'
            : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'"
          title="High interest, low producibility — worth making, but the scrape was too thin"
          @click="toggleNeedsSource"
        >
          <Icon name="lucide:file-search" class="h-3 w-3" />
          Needs source
        </button>

        <!-- Include toggles -->
        <div class="flex items-center gap-1">
          <button
            type="button"
            class="flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
            :class="filters.include_generated
              ? 'border-ok-border bg-ok-bg text-ok'
              : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'"
            @click="toggleInclude('include_generated')"
          >
            <Icon :name="filters.include_generated ? 'lucide:eye' : 'lucide:eye-off'" class="h-3 w-3" />
            Show generated
          </button>
          <button
            type="button"
            class="flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors"
            :class="filters.include_rejected
              ? 'border-danger-border bg-danger-bg text-danger'
              : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'"
            @click="toggleInclude('include_rejected')"
          >
            <Icon :name="filters.include_rejected ? 'lucide:eye' : 'lucide:eye-off'" class="h-3 w-3" />
            Show rejected
          </button>
        </div>

        <div class="ml-auto flex flex-wrap items-center gap-2">
          <span v-if="actionFeedback" class="text-xs text-muted-foreground">
            {{ actionFeedback }}
          </span>
          <Button
            size="sm"
            class="h-8 bg-primary text-primary-foreground hover:bg-primary/90"
            :disabled="actionBusy !== null"
            @click="pullStories('top')"
          >
            <Icon v-if="actionBusy === 'top'" name="lucide:loader-2" class="mr-1 h-3.5 w-3.5 animate-spin" />
            Pull Top 20
          </Button>
          <Button
            size="sm"
            variant="outline"
            class="h-8 border-running-border bg-running-bg text-running hover:bg-running-bg/70"
            :disabled="actionBusy !== null"
            @click="pullStories('new')"
          >
            <Icon v-if="actionBusy === 'new'" name="lucide:loader-2" class="mr-1 h-3.5 w-3.5 animate-spin" />
            Pull New 20
          </Button>
          <Button
            size="sm"
            variant="outline"
            class="h-8"
            :disabled="actionBusy !== null"
            @click="scoreBacklog"
          >
            <Icon v-if="actionBusy === 'score'" name="lucide:loader-2" class="mr-1 h-3.5 w-3.5 animate-spin" />
            <Icon v-else name="lucide:sparkles" class="mr-1 h-3.5 w-3.5" />
            Score backlog
          </Button>
        </div>
      </div>

      <div
        v-if="error"
        class="rounded border border-destructive bg-destructive/10 px-3 py-1.5 text-xs text-destructive"
      >
        Failed to load the triage queue. Is the API running?
      </div>
      </div>
    </template>

    <!-- Ranked list -->
    <div class="min-h-0 flex-1 overflow-auto">
      <div class="space-y-2 p-4" :class="pending && rows.length ? 'opacity-60' : ''">
        <!-- loading skeleton -->
        <template v-if="pending && rows.length === 0">
          <div v-for="n in 8" :key="`skeleton-${n}`" class="rounded-lg border bg-card px-3 py-2.5">
            <div class="flex items-start gap-3">
              <div class="h-14 w-16 shrink-0 animate-pulse rounded bg-muted" />
              <div class="flex-1 space-y-2 py-1">
                <div class="h-4 w-2/3 animate-pulse rounded bg-muted" />
                <div class="h-3 w-1/3 animate-pulse rounded bg-muted" />
                <div class="h-3 w-1/2 animate-pulse rounded bg-muted" />
              </div>
              <div class="h-8 w-48 shrink-0 animate-pulse rounded bg-muted" />
            </div>
          </div>
        </template>

        <TriageRow
          v-for="(item, index) in rows"
          :key="item.item_id"
          :item="item"
          :rank="rankBase + index + 1"
          @refresh="refresh"
        />

        <!-- empty state -->
        <div v-if="!pending && rows.length === 0" class="py-16 text-center text-muted-foreground">
          <Icon name="lucide:inbox" class="mx-auto mb-2 h-8 w-8 opacity-50" />
          <p>No scored stories yet — Pull Top 20 to start.</p>
        </div>
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
  </PageShell>
</template>
