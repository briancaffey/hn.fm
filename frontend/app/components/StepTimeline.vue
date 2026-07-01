<script setup lang="ts">
import { ref, computed, reactive, onBeforeUnmount } from 'vue'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Icon } from '#components'

interface Step {
  id: number
  item_id: number
  run: number
  seg: number | null
  stage: string
  step_key: string
  status: 'running' | 'ok' | 'error' | 'stale' | 'superseded'
  started_at: string | null
  finished_at: string | null
  seconds: number | null
  model: string | null
  tokens_in: number | null
  tokens_out: number | null
  llm_calls: number | null
  inputs: Record<string, unknown> | null
  outputs: Record<string, unknown> | null
  error: string | null
  supersedes: number | null
}

interface StepsResponse {
  item_id: number
  run: number
  seg: number
  steps: Step[]
  stale_count: number
  rerunnable: Record<string, boolean>
}

const props = defineProps<{
  itemId: number
  runId: number
  segId: number
}>()

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const stepsUrl = `${apiBase}/api/hn/items/${props.itemId}/runs/${props.runId}/segments/${props.segId}/steps`

const { data, pending, error: fetchError, refresh } = useAsyncData<StepsResponse>(
  `steps-${props.itemId}-${props.runId}-${props.segId}`,
  () => $fetch<StepsResponse>(stepsUrl),
  { server: false }
)

// ---------------------------------------------------------------------------
// Derived data
// ---------------------------------------------------------------------------

const STAGE_ORDER = ['scrape', 'summary', 'enrich', 'script', 'audio', 'images', 'media_plan', 'video']
const EDITABLE_FIELDS = ['prompt', 'line_text', 'text', 'script']

const steps = computed<Step[]>(() => (data.value?.steps || []).slice().sort((a, b) => a.id - b.id))
const staleCount = computed(() => data.value?.stale_count || 0)

const activeSteps = computed(() => steps.value.filter(s => s.status !== 'superseded'))

const stageGroups = computed(() => {
  const byStage = new Map<string, Step[]>()
  for (const step of steps.value) {
    const list = byStage.get(step.stage) || []
    list.push(step)
    byStage.set(step.stage, list)
  }
  const order = [
    ...STAGE_ORDER.filter(stage => byStage.has(stage)),
    ...[...byStage.keys()].filter(stage => !STAGE_ORDER.includes(stage))
  ]
  return order.map(stage => {
    const all = byStage.get(stage) || []
    return {
      stage,
      steps: all,
      active: all.filter(s => s.status !== 'superseded'),
      supersededCount: all.filter(s => s.status === 'superseded').length
    }
  })
})

const totalSeconds = computed(() =>
  activeSteps.value.reduce((sum, s) => sum + (s.seconds || 0), 0)
)

const totalTokens = computed(() =>
  activeSteps.value.reduce((sum, s) => sum + (s.tokens_in || 0) + (s.tokens_out || 0), 0)
)

// ---------------------------------------------------------------------------
// UI state
// ---------------------------------------------------------------------------

const showHistory = reactive<Record<string, boolean>>({})
const expandedSteps = reactive<Record<number, boolean>>({})
const editedInputs = reactive<Record<number, Record<string, string>>>({})
const regeneratePrompt = reactive<Record<number, boolean>>({})
const rerunning = reactive<Record<number, boolean>>({})
const isRebuildingStale = ref(false)
const isPolling = ref(false)
const actionError = ref<string | null>(null)
let stopped = false

onBeforeUnmount(() => {
  stopped = true
})

function visibleSteps(group: { steps: Step[]; active: Step[]; stage: string }): Step[] {
  return showHistory[group.stage] ? group.steps : group.active
}

function toggleHistory(stage: string) {
  showHistory[stage] = !showHistory[stage]
}

function toggleStep(step: Step) {
  expandedSteps[step.id] = !expandedSteps[step.id]
  if (expandedSteps[step.id] && !editedInputs[step.id]) {
    const edits: Record<string, string> = {}
    for (const field of editableFields(step)) {
      edits[field] = String(step.inputs?.[field] ?? '')
    }
    editedInputs[step.id] = edits
  }
}

function isRerunnable(step: Step): boolean {
  return !!data.value?.rerunnable?.[String(step.id)]
}

function editableFields(step: Step): string[] {
  if (!step.inputs) return []
  return EDITABLE_FIELDS.filter(field => typeof step.inputs?.[field] === 'string')
}

function isImageRootStep(step: Step): boolean {
  return /^images\/\d+\/root$/.test(step.step_key)
}

function fieldLabel(field: string): string {
  return field.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function dotClass(step: Step): string {
  switch (step.status) {
    case 'ok': return 'bg-green-500'
    case 'error': return 'bg-red-500'
    case 'stale': return 'bg-amber-500'
    case 'running': return 'bg-blue-500 animate-pulse'
    default: return 'bg-gray-400 dark:bg-gray-600'
  }
}

function formatSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return ''
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  const remaining = Math.round(seconds % 60)
  return `${minutes}m ${remaining}s`
}

function formatTokens(count: number | null | undefined): string {
  if (!count) return '0'
  if (count < 1000) return String(count)
  return `${(count / 1000).toFixed(1)}k`
}

function tokensBadge(step: Step): string {
  const parts = [`${formatTokens(step.tokens_in)}→${formatTokens(step.tokens_out)} tok`]
  if (step.model) parts.push(step.model)
  return parts.join(' · ')
}

function formatStepTime(step: Step): string {
  const timestamp = step.finished_at || step.started_at
  if (!timestamp) return ''
  try {
    const date = new Date(timestamp)
    const diffMs = Date.now() - date.getTime()
    if (diffMs >= 0 && diffMs < 24 * 60 * 60 * 1000) {
      const minutes = Math.floor(diffMs / 60000)
      if (minutes < 1) return 'just now'
      if (minutes < 60) return `${minutes}m ago`
      return `${Math.floor(minutes / 60)}h ago`
    }
    return date.toLocaleString()
  } catch {
    return ''
  }
}

function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

async function pollSteps() {
  if (isPolling.value) return
  isPolling.value = true

  const maxAttempts = 30 // 2s interval * 30 = 60s max
  let sawRunning = false

  try {
    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 2000))
      if (stopped) return

      try {
        await refresh()
        const hasRunning = steps.value.some(s => s.status === 'running')
        if (hasRunning) {
          sawRunning = true
        } else if (sawRunning || attempt >= 4) {
          // Work finished (or never showed up) — stop polling early
          return
        }
      } catch (err) {
        console.error('Error polling steps:', err)
      }
    }
    console.warn('Step polling timed out')
  } finally {
    isPolling.value = false
  }
}

async function rerunStep(step: Step) {
  if (rerunning[step.id]) return
  rerunning[step.id] = true
  actionError.value = null

  try {
    const body: Record<string, unknown> = {}
    const edits = editedInputs[step.id] || {}
    for (const field of editableFields(step)) {
      const original = String(step.inputs?.[field] ?? '')
      if (field in edits && edits[field] !== original) {
        body[field] = edits[field]
      }
    }
    if (isImageRootStep(step) && regeneratePrompt[step.id]) {
      body.regenerate_prompt = true
    }

    const response = await $fetch(`${apiBase}/api/steps/${step.id}/rerun`, {
      method: 'POST',
      body
    })
    console.log('Step rerun queued:', response)

    await pollSteps()
  } catch (err) {
    console.error('Failed to re-run step:', err)
    actionError.value = `Failed to re-run step ${step.step_key}`
  } finally {
    rerunning[step.id] = false
  }
}

async function rebuildStale() {
  if (isRebuildingStale.value) return
  isRebuildingStale.value = true
  actionError.value = null

  try {
    const response = await $fetch(
      `${apiBase}/api/hn/items/${props.itemId}/runs/${props.runId}/segments/${props.segId}/rebuild-stale`,
      { method: 'POST' }
    )
    console.log('Rebuild stale queued:', response)

    await pollSteps()
  } catch (err) {
    console.error('Failed to rebuild stale steps:', err)
    actionError.value = 'Failed to rebuild stale steps'
  } finally {
    isRebuildingStale.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Loading State -->
    <div v-if="pending && !data" class="text-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"/>
      <p class="mt-2 text-muted-foreground">Loading pipeline steps...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="fetchError" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded">
      Failed to load pipeline steps: {{ fetchError.message }}
    </div>

    <template v-else-if="data">
      <!-- Header Bar -->
      <div class="flex flex-wrap items-center justify-between gap-2 bg-muted/50 p-4 rounded-lg border">
        <div class="flex flex-wrap items-center gap-2">
          <Badge class="bg-blue-500 text-white border-blue-500 text-xs">
            {{ activeSteps.length }} Steps
          </Badge>
          <Badge class="bg-gray-500 text-white border-gray-500 text-xs">
            {{ formatSeconds(totalSeconds) || '0s' }} Total
          </Badge>
          <Badge class="bg-purple-500 text-white border-purple-500 text-xs">
            {{ formatTokens(totalTokens) }} Tokens
          </Badge>
          <Badge v-if="staleCount > 0" class="bg-amber-500 text-white border-amber-500 text-xs">
            {{ staleCount }} Stale
          </Badge>
          <Icon
            v-if="isPolling"
            name="lucide:refresh-cw"
            class="h-4 w-4 text-muted-foreground animate-spin"
          />
        </div>
        <Button
          v-if="staleCount > 0"
          size="sm"
          :disabled="isRebuildingStale"
          class="bg-amber-600 hover:bg-amber-700 text-white border-amber-600"
          @click="rebuildStale"
        >
          <span v-if="isRebuildingStale">Rebuilding...</span>
          <span v-else>🔧 Rebuild Stale</span>
        </Button>
      </div>

      <!-- Action Error -->
      <div v-if="actionError" class="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded">
        {{ actionError }}
      </div>

      <!-- Empty State -->
      <div v-if="steps.length === 0" class="text-center py-8 text-muted-foreground">
        <p>No pipeline steps recorded for this segment yet.</p>
      </div>

      <!-- Timeline -->
      <div v-else class="space-y-6">
        <div v-for="group in stageGroups" :key="group.stage">
          <div class="flex items-center gap-3 mb-2">
            <h3 class="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              {{ group.stage }}
            </h3>
            <button
              v-if="group.supersededCount > 0"
              type="button"
              class="text-xs text-muted-foreground hover:text-orange-600 transition-colors underline underline-offset-2"
              @click="toggleHistory(group.stage)"
            >
              {{ showHistory[group.stage] ? 'hide history' : `show history (${group.supersededCount})` }}
            </button>
          </div>

          <div class="ml-1.5 border-l pl-5 space-y-2">
            <div
              v-for="step in visibleSteps(group)"
              :key="step.id"
              class="relative"
              :class="{ 'opacity-60': step.status === 'superseded' }"
            >
              <!-- Status Dot -->
              <span
                class="absolute -left-[1.6rem] top-2.5 h-2.5 w-2.5 rounded-full border-2 border-card"
                :class="dotClass(step)"
              />

              <!-- Step Row -->
              <div
                class="flex flex-wrap items-center gap-2 py-1.5 px-2 rounded cursor-pointer hover:bg-muted/50 transition-colors"
                @click="toggleStep(step)"
              >
                <Icon
                  :name="expandedSteps[step.id] ? 'lucide:chevron-down' : 'lucide:chevron-right'"
                  class="h-3.5 w-3.5 text-muted-foreground shrink-0"
                />
                <span class="text-sm font-mono font-medium text-foreground">{{ step.step_key }}</span>
                <Badge v-if="step.status === 'error'" class="bg-red-500 text-white border-red-500 text-xs">
                  Error
                </Badge>
                <Badge v-else-if="step.status === 'stale'" class="bg-amber-500 text-white border-amber-500 text-xs">
                  Stale
                </Badge>
                <Badge v-else-if="step.status === 'running'" class="bg-blue-500 text-white border-blue-500 text-xs">
                  Running
                </Badge>
                <Badge v-else-if="step.status === 'superseded'" class="bg-gray-500 text-white border-gray-500 text-xs">
                  Superseded
                </Badge>
                <span v-if="step.seconds !== null" class="text-xs text-muted-foreground">
                  {{ formatSeconds(step.seconds) }}
                </span>
                <Badge
                  v-if="(step.llm_calls || 0) > 0"
                  class="bg-purple-500 text-white border-purple-500 text-xs font-mono"
                >
                  {{ tokensBadge(step) }}
                </Badge>
                <span class="text-xs text-muted-foreground ml-auto">
                  {{ formatStepTime(step) }}
                </span>
              </div>

              <!-- Expanded Detail -->
              <div v-if="expandedSteps[step.id]" class="mt-2 mb-3 ml-6 space-y-3">
                <!-- Error -->
                <div v-if="step.error" class="bg-destructive/10 border border-destructive text-destructive px-3 py-2 rounded text-sm">
                  <p class="font-medium mb-1">Error</p>
                  <pre class="whitespace-pre-wrap text-xs font-mono overflow-x-auto">{{ step.error }}</pre>
                </div>

                <!-- Rerun Controls -->
                <div v-if="isRerunnable(step)" class="bg-muted/30 p-3 rounded-lg border space-y-3">
                  <div
                    v-for="field in editableFields(step)"
                    :key="field"
                  >
                    <label class="text-sm font-medium text-muted-foreground mb-1 block">
                      {{ fieldLabel(field) }}:
                    </label>
                    <textarea
                      v-model="editedInputs[step.id]![field]"
                      class="w-full p-3 border rounded-lg bg-background text-sm font-mono"
                      rows="3"
                      :placeholder="`Enter ${fieldLabel(field).toLowerCase()}...`"
                    />
                  </div>
                  <label
                    v-if="isImageRootStep(step)"
                    class="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer"
                  >
                    <input
                      v-model="regeneratePrompt[step.id]"
                      type="checkbox"
                      class="h-4 w-4 rounded border accent-orange-600"
                    >
                    Regenerate prompt
                  </label>
                  <Button
                    size="sm"
                    :disabled="rerunning[step.id]"
                    class="bg-orange-600 hover:bg-orange-700 text-white border-orange-600"
                    @click="rerunStep(step)"
                  >
                    <span v-if="rerunning[step.id]">Re-running...</span>
                    <span v-else>🔄 Re-run</span>
                  </Button>
                </div>

                <!-- Inputs -->
                <div v-if="step.inputs && Object.keys(step.inputs).length > 0">
                  <p class="text-sm font-medium text-muted-foreground mb-1">Inputs</p>
                  <div class="bg-muted/50 p-3 rounded-lg">
                    <pre class="whitespace-pre-wrap text-xs text-foreground font-mono overflow-x-auto">{{ prettyJson(step.inputs) }}</pre>
                  </div>
                </div>

                <!-- Outputs -->
                <div v-if="step.outputs && Object.keys(step.outputs).length > 0">
                  <p class="text-sm font-medium text-muted-foreground mb-1">Outputs</p>
                  <div class="bg-muted/50 p-3 rounded-lg">
                    <pre class="whitespace-pre-wrap text-xs text-foreground font-mono overflow-x-auto">{{ prettyJson(step.outputs) }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
