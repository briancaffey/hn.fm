<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '#components'
import { Button } from '~/components/ui/button'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import StatTile from '~/components/kit/StatTile.vue'
import StageBadge from '~/components/kit/StageBadge.vue'
import LoadingRows from '~/components/kit/LoadingRows.vue'
import InfoHint from '~/components/kit/InfoHint.vue'
import { stageMeta } from '~/composables/usePipelineVocab'

/**
 * Where the pipeline's time and tokens actually go.
 *
 * Same source as the diagnostics section printed at the back of each digest —
 * `pipeline_steps` — so the page and the document can never disagree about
 * what something cost.
 */
useHead({ title: 'hn.fm · Diagnostics' })

interface Stage {
  stage: string
  steps: number
  calls: number
  tokens_in: number
  tokens_out: number
  seconds: number
  errors: number
}
interface Diag {
  days: number
  stages: Stage[]
  models: Array<{ model: string, calls: number, tokens_in: number, tokens_out: number }>
  totals: Stage
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const data = ref<Diag | null>(null)
const loading = ref(true)
const days = ref(7)

async function load() {
  loading.value = true
  try {
    data.value = await $fetch<Diag>(`${apiBase}/api/diagnostics?days=${days.value}`)
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(days, load)

const maxSeconds = computed(() =>
  Math.max(1, ...(data.value?.stages || []).map(s => s.seconds)))
const maxTokens = computed(() =>
  Math.max(1, ...(data.value?.stages || []).map(s => s.tokens_in + s.tokens_out)))

function fmtSec(s: number) {
  if (s < 60) return `${s.toFixed(0)}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
  return `${Math.floor(s / 3600)}h ${Math.round((s % 3600) / 60)}m`
}
const n = (v: number) => v.toLocaleString()
</script>

<template>
  <PageShell>
    <PageHeader
      title="Diagnostics"
      subtitle="Where the pipeline's time and tokens actually go, by stage and by model."
      hint="Read from the audit trail — the same source as the diagnostics section printed at the back of every digest, so the two can never disagree. Use it to find which stage dominates before optimising the one you assume is slow."
      :meta="data ? [`last ${data.days} days`, `${n(data.totals.steps)} steps`] : []"
    >
      <template #actions>
        <select v-model.number="days" class="h-8 rounded-md border bg-card px-2 text-xs" aria-label="Window">
          <option :value="1">Last 24 hours</option>
          <option :value="7">Last 7 days</option>
          <option :value="30">Last 30 days</option>
        </select>
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <LoadingRows v-if="loading && !data" :rows="4" height="h-24" />

    <template v-else-if="data">
      <section class="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatTile label="Steps" :value="n(data.totals.steps)" hint="Units of pipeline work recorded in the audit trail." />
        <StatTile label="LLM calls" :value="n(data.totals.calls)" hint="Model invocations. The cheapest lever on cost is making fewer of these, not faster ones." />
        <StatTile label="Tokens in" :value="n(data.totals.tokens_in)" hint="Prompt tokens. Dominated by whatever stage feeds the model the most source text." />
        <StatTile label="Tokens out" :value="n(data.totals.tokens_out)" hint="Generated tokens. Usually an order of magnitude below tokens in." />
        <StatTile
          label="Errors" :value="n(data.totals.errors)"
          :tone="data.totals.errors ? 'danger' : 'default'"
          hint="Failed steps. A soft failure — one motion clip, say — does not stop the run around it."
        />
      </section>

      <section class="mt-6 rounded-lg border bg-card">
        <div class="flex items-center gap-1.5 border-b px-4 py-2.5">
          <h2 class="text-sm font-semibold">Time by stage</h2>
          <InfoHint text="Wall clock summed across every step of that stage. The answer is usually not the stage you would guess — Story Briefs and media planning tend to dominate while the LLM text stages are cheap." />
          <span class="ml-auto text-xs text-muted-foreground">{{ fmtSec(data.totals.seconds) }} total</span>
        </div>
        <div class="space-y-2.5 p-4">
          <div v-for="s in data.stages" :key="s.stage" class="grid grid-cols-[10rem_1fr_5rem] items-center gap-3">
            <div class="flex items-center gap-2">
              <StageBadge :stage="s.stage" :show-label="false" />
              <span class="truncate text-xs">{{ stageMeta(s.stage).label }}</span>
            </div>
            <div class="h-2.5 rounded-full bg-muted">
              <div class="h-2.5 rounded-full bg-primary" :style="{ width: `${(s.seconds / maxSeconds) * 100}%` }" />
            </div>
            <span class="text-right text-xs tabular-nums text-muted-foreground">{{ fmtSec(s.seconds) }}</span>
          </div>
        </div>
      </section>

      <section class="mt-4 rounded-lg border bg-card">
        <div class="flex items-center gap-1.5 border-b px-4 py-2.5">
          <h2 class="text-sm font-semibold">Tokens by stage</h2>
          <InfoHint text="Prompt plus generated tokens. A stage can be slow and cheap (rendering) or fast and expensive (a long brief)." />
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-xs">
            <thead class="border-b text-left text-muted-foreground">
              <tr>
                <th class="px-4 py-2 font-medium">Stage</th>
                <th class="px-3 py-2 text-right font-medium">Steps</th>
                <th class="px-3 py-2 text-right font-medium">Calls</th>
                <th class="px-3 py-2 text-right font-medium">In</th>
                <th class="px-3 py-2 text-right font-medium">Out</th>
                <th class="px-3 py-2 text-right font-medium">Errors</th>
                <th class="w-40 px-4 py-2 font-medium">Share</th>
              </tr>
            </thead>
            <tbody class="divide-y">
              <tr v-for="s in data.stages" :key="s.stage" class="hover:bg-muted/40">
                <td class="px-4 py-2">{{ stageMeta(s.stage).label }}</td>
                <td class="px-3 py-2 text-right tabular-nums">{{ n(s.steps) }}</td>
                <td class="px-3 py-2 text-right tabular-nums">{{ n(s.calls) }}</td>
                <td class="px-3 py-2 text-right tabular-nums">{{ n(s.tokens_in) }}</td>
                <td class="px-3 py-2 text-right tabular-nums">{{ n(s.tokens_out) }}</td>
                <td class="px-3 py-2 text-right tabular-nums" :class="s.errors ? 'text-danger' : 'text-muted-foreground'">{{ s.errors }}</td>
                <td class="px-4 py-2">
                  <div class="h-1.5 rounded-full bg-muted">
                    <div class="h-1.5 rounded-full bg-running" :style="{ width: `${((s.tokens_in + s.tokens_out) / maxTokens) * 100}%` }" />
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="mt-4 rounded-lg border bg-card">
        <div class="flex items-center gap-1.5 border-b px-4 py-2.5">
          <h2 class="text-sm font-semibold">Models</h2>
          <InfoHint text="Every model the pipeline called in this window. More than one row usually means a fallback fired." />
        </div>
        <div class="divide-y">
          <div v-for="m in data.models" :key="m.model" class="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
            <span class="font-mono text-xs">{{ m.model }}</span>
            <span class="text-xs tabular-nums text-muted-foreground">
              {{ n(m.calls) }} calls · {{ n(m.tokens_in) }} in / {{ n(m.tokens_out) }} out
            </span>
          </div>
        </div>
      </section>
    </template>
  </PageShell>
</template>
