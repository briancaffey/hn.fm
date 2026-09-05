<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Icon } from '#components'

const props = defineProps<{
  item: TriageItem
  rank: number
}>()

const emit = defineEmits<{
  (e: 'refresh'): void
}>()

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

// ── helpers ─────────────────────────────────────────────────────────────────

function domain(url: string | null): string {
  if (!url) return ''
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

function ageFromUnix(time: number | null): string {
  if (!time) return '—'
  const s = Math.max(0, Math.floor((Date.now() - time * 1000) / 1000))
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

function scoreClass(s: number | null | undefined) {
  if (s == null) return 'text-muted-foreground/50'
  if (s >= 70) return 'text-ok'
  if (s >= 40) return 'text-warn'
  return 'text-muted-foreground'
}

const interestClass = computed(() => scoreClass(props.item.interest))
const producibilityClass = computed(() => scoreClass(props.item.producibility))

// "Worth it, needs a better source": high interest, low producibility. A
// fix-the-scrape signal rather than a reject (plans/09).
const needsBetterSource = computed(() =>
  (props.item.flags || []).includes('needs_better_source'),
)

const verdictBadgeClass = computed(() => {
  switch (props.item.verdict) {
    case 'great': return 'bg-ok-bg text-ok border-ok-border'
    case 'good': return 'bg-running-bg text-running border-running-border'
    case 'marginal': return 'bg-warn-bg text-warn border-warn-border'
    default: return 'bg-danger-bg text-danger border-danger-border'
  }
})

/** What each verdict means, on hover. Derived from the two axes, not asked of
 *  the model — it was bad at bucketing its own scores. */
const VERDICT_HINT: Record<string, string> = {
  great: 'High on both axes. The pipeline would make this without hesitation.',
  good: 'Worth making. Solid on both interest and producibility.',
  marginal: 'Middling. Gets a Story Brief only if it ranks well enough.',
  unsuitable: 'Below the floor on interest or producibility — usually a thin scrape. No brief, no generation.',
}

const GEN_AI_TOPIC = /(^|[\s_/-])(ai|ml|llms?|gpt|genai|gen[\s_-]?ai|agents?|models?|diffusion|transformers?|neural|machine[\s_-]?learning|deep[\s_-]?learning|openai|anthropic|claude|inference|rag|embeddings?)($|[\s_/-])/i

function isGenAiTopic(topic: string): boolean {
  return GEN_AI_TOPIC.test(topic)
}

function meterClass(value: number): string {
  if (value >= 7) return 'bg-ok'
  if (value >= 4) return 'bg-warn'
  return 'bg-muted-foreground/50'
}

// ── expandable "why" ────────────────────────────────────────────────────────

const expanded = ref(false)

// ── human feedback ──────────────────────────────────────────────────────────

type HumanVerdict = 'starred' | 'approved' | 'rejected'

const feedbackBusy = ref(false)
const feedbackError = ref(false)
const noteOpen = ref(false)
const noteDraft = ref(props.item.human_note ?? '')

watch(
  () => props.item.human_note,
  (value) => {
    noteDraft.value = value ?? ''
  },
)

async function postFeedback(verdict: HumanVerdict | null) {
  feedbackBusy.value = true
  feedbackError.value = false
  try {
    const note = noteDraft.value.trim()
    await $fetch(`${apiBase}/api/hn/items/${props.item.item_id}/feedback`, {
      method: 'POST',
      body: { verdict, ...(note ? { note } : {}) },
    })
    emit('refresh')
  } catch {
    feedbackError.value = true
  } finally {
    feedbackBusy.value = false
  }
}

function toggleVerdict(verdict: HumanVerdict) {
  postFeedback(props.item.human_verdict === verdict ? null : verdict)
}

function saveNote() {
  postFeedback(props.item.human_verdict)
  noteOpen.value = false
}

const feedbackButtons: { verdict: HumanVerdict; emoji: string; label: string; activeClass: string }[] = [
  {
    verdict: 'starred',
    emoji: '⭐',
    label: 'Star',
    activeClass: 'border-warn-border bg-warn-bg text-warn',
  },
  {
    verdict: 'approved',
    emoji: '👍',
    label: 'Approve',
    activeClass: 'border-ok-border bg-ok-bg text-ok',
  },
  {
    verdict: 'rejected',
    emoji: '👎',
    label: 'Reject',
    activeClass: 'border-danger-border bg-danger-bg text-danger',
  },
]

// ── generate ────────────────────────────────────────────────────────────────

type GenMode = 'video' | 'audio'

const genBusy = ref<GenMode | null>(null)
const genQueued = ref(new Set<GenMode>())
const genError = ref(false)

async function generate(mode: GenMode) {
  if (genBusy.value || genQueued.value.has(mode)) return
  genBusy.value = mode
  genError.value = false
  try {
    await $fetch(`${apiBase}/api/hn/single-task-pipeline`, {
      method: 'POST',
      body: { item_id: props.item.item_id, mode },
    })
    genQueued.value.add(mode)
  } catch {
    genError.value = true
  } finally {
    genBusy.value = null
  }
}
</script>

<script lang="ts">
export interface TriageItem {
  item_id: number
  run: unknown
  suitability: number
  // Two axes (plans/09). `producibility` is null on rows scored before the
  // split — shown as "—" rather than a number we never measured.
  interest: number
  producibility: number | null
  verdict: 'great' | 'good' | 'marginal' | 'unsuitable'
  reasons: string[]
  flags: string[]
  topics: string[]
  visual_potential: number
  narrative_potential: number
  interest_match: number
  rank_score: number
  effective_rank: number
  model: string | null
  scored_at: string | null
  title: string | null
  url: string | null
  by: string | null
  time: number | null
  hn_score: number | null
  comments: number | null
  human_verdict: 'starred' | 'approved' | 'rejected' | null
  human_note: string | null
  segments_count: number
  videos_count: number
}
</script>

<template>
  <div class="rounded-lg border bg-card px-3 py-2.5 transition-colors hover:border-primary/40">
    <div class="flex items-start gap-3">
      <!-- Rank + the two axes -->
      <div class="flex w-16 shrink-0 flex-col items-center pt-0.5">
        <span class="text-[10px] font-medium tabular-nums text-muted-foreground">#{{ rank }}</span>
        <span
          class="text-2xl font-bold leading-tight tabular-nums"
          :class="interestClass"
          :title="`Interest ${item.interest}/100 — is the story worth attention`"
        >
          {{ item.interest }}
        </span>
        <span
          class="text-xs font-semibold leading-tight tabular-nums"
          :class="producibilityClass"
          :title="
            item.producibility == null
              ? 'Producibility not scored (run predates the two-axis split)'
              : `Producibility ${item.producibility}/100 — can we build it from what we retrieved`
          "
        >
          {{ item.producibility ?? '—' }}
        </span>
        <span
          class="mt-0.5 inline-flex rounded-full border px-1.5 py-0.5 text-[10px] font-medium capitalize"
          :class="verdictBadgeClass"
          :title="VERDICT_HINT[item.verdict] || ''"
        >
          {{ item.verdict }}
        </span>
        <span
          v-if="needsBetterSource"
          class="mt-1 inline-flex rounded-full border border-stale-border bg-stale-bg px-1.5 py-0.5 text-center text-[9px] font-medium leading-tight text-stale"
          title="Worth making, but the scrape was too thin — retry with a better source"
        >
          needs source
        </span>
      </div>

      <!-- Main -->
      <div class="min-w-0 flex-1">
        <!-- Title line -->
        <div class="flex items-baseline gap-2">
          <NuxtLink
            :to="`/hn/item/${item.item_id}`"
            class="truncate font-semibold text-foreground hover:text-primary"
          >
            {{ item.title || `Item ${item.item_id}` }}
          </NuxtLink>
          <a
            v-if="item.url"
            :href="item.url"
            target="_blank"
            rel="noopener noreferrer"
            class="shrink-0 truncate text-xs text-muted-foreground hover:text-primary"
          >
            {{ domain(item.url) }}
          </a>
          <span
            v-if="item.videos_count > 0"
            class="inline-flex shrink-0 items-center gap-1 rounded-full border border-ok-border bg-ok-bg px-1.5 py-0.5 text-[10px] font-medium text-ok"
          >
            <Icon name="lucide:check" class="h-2.5 w-2.5" />
            generated
          </span>
        </div>

        <!-- HN meta -->
        <div class="mt-0.5 text-xs text-muted-foreground">
          ▲ {{ item.hn_score ?? 0 }} · {{ item.comments ?? 0 }} comments ·
          {{ ageFromUnix(item.time) }} · by {{ item.by || '—' }}
        </div>

        <!-- Topic + flag chips -->
        <div v-if="item.topics?.length || item.flags?.length" class="mt-1.5 flex flex-wrap items-center gap-1">
          <span
            v-for="topic in item.topics || []"
            :key="`t-${topic}`"
            class="rounded-full border px-1.5 py-0.5 text-[10px]"
            :class="isGenAiTopic(topic)
              ? 'border-primary/40 bg-primary/10 text-primary'
              : 'border-border text-muted-foreground'"
          >
            {{ topic }}
          </span>
          <span
            v-for="flag in item.flags || []"
            :key="`f-${flag}`"
            class="rounded-full border border-warn-border bg-warn-bg px-1.5 py-0.5 text-[10px] font-medium text-warn"
          >
            ⚑ {{ flag }}
          </span>
        </div>

        <!-- Meters + expand -->
        <div class="mt-1.5 flex flex-wrap items-center gap-4 text-[10px] text-muted-foreground">
          <div class="flex items-center gap-1.5" :title="`Visual potential ${item.visual_potential}/10`">
            <span>Visual</span>
            <div class="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
              <div
                class="h-full rounded-full"
                :class="meterClass(item.visual_potential)"
                :style="{ width: `${Math.min(10, Math.max(0, item.visual_potential)) * 10}%` }"
              />
            </div>
            <span class="tabular-nums">{{ item.visual_potential }}/10</span>
          </div>
          <div class="flex items-center gap-1.5" :title="`Narrative potential ${item.narrative_potential}/10`">
            <span>Narrative</span>
            <div class="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
              <div
                class="h-full rounded-full"
                :class="meterClass(item.narrative_potential)"
                :style="{ width: `${Math.min(10, Math.max(0, item.narrative_potential)) * 10}%` }"
              />
            </div>
            <span class="tabular-nums">{{ item.narrative_potential }}/10</span>
          </div>
          <button
            type="button"
            class="flex items-center gap-0.5 text-muted-foreground transition-colors hover:text-foreground"
            @click="expanded = !expanded"
          >
            <Icon :name="expanded ? 'lucide:chevron-down' : 'lucide:chevron-right'" class="h-3 w-3" />
            why
          </button>
        </div>

        <!-- Expandable "why" -->
        <div v-if="expanded" class="mt-2 rounded-md bg-muted/50 px-3 py-2 text-xs">
          <ul class="list-disc space-y-0.5 pl-4 text-foreground/90">
            <li v-for="(reason, i) in item.reasons || []" :key="i">{{ reason }}</li>
            <li v-if="!item.reasons?.length" class="list-none -ml-4 text-muted-foreground">No reasons recorded.</li>
          </ul>
          <div class="mt-1.5 text-muted-foreground">
            {{ item.model || 'unknown model' }} · interest match
            <span class="tabular-nums">{{ (item.interest_match ?? 0).toFixed(2) }}</span>
          </div>
          <div v-if="item.human_note" class="mt-1.5 border-t border-border pt-1.5 text-foreground/90">
            <span class="font-medium">Your note:</span> {{ item.human_note }}
          </div>
        </div>
      </div>

      <!-- Right rail: human feedback + generate -->
      <div class="flex shrink-0 flex-col items-end gap-1.5">
        <div class="flex items-center gap-1">
          <button
            v-for="fb in feedbackButtons"
            :key="fb.verdict"
            type="button"
            class="rounded-md border px-2 py-1 text-xs font-medium transition-colors disabled:opacity-50"
            :class="item.human_verdict === fb.verdict
              ? fb.activeClass
              : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'"
            :disabled="feedbackBusy"
            :title="item.human_verdict === fb.verdict ? `Clear ${fb.label.toLowerCase()}` : fb.label"
            @click="toggleVerdict(fb.verdict)"
          >
            {{ fb.emoji }} {{ fb.label }}
          </button>
          <button
            type="button"
            class="rounded-md border px-1.5 py-1 text-xs transition-colors"
            :class="noteOpen || item.human_note
              ? 'border-primary text-primary'
              : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground'"
            title="Add a note"
            @click="noteOpen = !noteOpen"
          >
            <Icon name="lucide:sticky-note" class="h-3.5 w-3.5" />
          </button>
        </div>
        <span v-if="feedbackError" class="text-[10px] text-destructive">Feedback failed</span>

        <div v-if="noteOpen" class="flex items-center gap-1">
          <Input
            v-model="noteDraft"
            placeholder="Note…"
            class="h-7 w-48 text-xs"
            @keyup.enter="saveNote"
          />
          <Button size="sm" variant="outline" class="h-7 px-2 text-xs" :disabled="feedbackBusy" @click="saveNote">
            Save
          </Button>
        </div>

        <div class="flex items-center gap-1">
          <template v-if="item.videos_count === 0">
            <Button
              size="sm"
              variant="outline"
              class="h-7 px-2 text-xs"
              :disabled="genBusy !== null || genQueued.has('video')"
              @click="generate('video')"
            >
              <Icon v-if="genBusy === 'video'" name="lucide:loader-2" class="mr-1 h-3 w-3 animate-spin" />
              <span v-if="genQueued.has('video')" class="text-ok">Queued</span>
              <span v-else>🎬 Video</span>
            </Button>
            <Button
              size="sm"
              variant="outline"
              class="h-7 px-2 text-xs"
              :disabled="genBusy !== null || genQueued.has('audio')"
              @click="generate('audio')"
            >
              <Icon v-if="genBusy === 'audio'" name="lucide:loader-2" class="mr-1 h-3 w-3 animate-spin" />
              <span v-if="genQueued.has('audio')" class="text-ok">Queued</span>
              <span v-else>🎙️ Audio</span>
            </Button>
          </template>
          <span v-if="genError" class="text-[10px] text-destructive">Queue failed</span>
        </div>
      </div>
    </div>
  </div>
</template>
