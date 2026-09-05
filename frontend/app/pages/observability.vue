<template>
  <PageShell>
    <PageHeader
      title="Observability"
      subtitle="Where a render spends its time and tokens, stage by stage."
      hint="Each record is one finished render. Use it to answer where the cost actually goes — media planning and video assembly dominate, and the LLM stages are cheap by comparison. Only finalized full-pipeline runs appear here."
      :meta="loading ? [] : [`${records.length} renders`, `${totalTokens.toLocaleString()} tokens total`]"
    >
      <template #actions>
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <LoadingRows v-if="loading && !records.length" :rows="3" height="h-28" />

    <EmptyState
      v-else-if="!records.length"
      icon="lucide:activity"
      title="No renders measured yet"
      body="A record appears here when a full pipeline run finishes. Start one from Triage, then come back to see where its time went."
    >
      <template #action>
        <Button as-child size="sm"><NuxtLink to="/triage">Go to Triage</NuxtLink></Button>
      </template>
    </EmptyState>

    <template v-else>
      <!-- aggregate cards -->
      <div class="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <div v-for="c in cards" :key="c.label" class="rounded-lg border bg-card p-3">
          <div class="text-[11px] uppercase tracking-wide text-muted-foreground">{{ c.label }}</div>
          <div class="mt-1 text-2xl font-semibold" :class="c.cls">{{ c.value }}</div>
          <div v-if="c.sub" class="text-[11px] text-muted-foreground">{{ c.sub }}</div>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <!-- where the time goes -->
        <div class="rounded-lg border bg-card p-4">
          <h2 class="mb-3 font-semibold">Where the time goes <span class="text-xs font-normal text-muted-foreground">(avg / render)</span></h2>
          <div class="mb-3 flex h-7 w-full overflow-hidden rounded">
            <div
v-for="s in STAGES" :key="s"
              :style="{ width: pct(avgStage[s], avgTotal) + '%', background: COLORS[s] }"
              :title="`${s}: ${fmt(avgStage[s])} (${pct(avgStage[s], avgTotal)}%)`"/>
          </div>
          <div class="space-y-1.5">
            <div v-for="s in STAGES" :key="s" class="flex items-center gap-2 text-xs">
              <span class="inline-block h-3 w-3 rounded-sm" :style="{ background: COLORS[s] }"/>
              <span class="w-28 capitalize">{{ s.replace('_',' ') }}</span>
              <div class="h-2 flex-1 rounded bg-muted">
                <div class="h-2 rounded" :style="{ width: pct(avgStage[s], maxAvgStage) + '%', background: COLORS[s] }"/>
              </div>
              <span class="w-20 text-right tabular-nums">{{ fmt(avgStage[s]) }}</span>
              <span class="w-10 text-right text-muted-foreground tabular-nums">{{ pct(avgStage[s], avgTotal) }}%</span>
            </div>
          </div>
        </div>

        <!-- tokens per stage -->
        <div class="rounded-lg border bg-card p-4">
          <h2 class="mb-3 font-semibold">Tokens per stage <span class="text-xs font-normal text-muted-foreground">(avg in+out / render)</span></h2>
          <div class="space-y-1.5">
            <div v-for="s in STAGES" :key="s" class="flex items-center gap-2 text-xs">
              <span class="w-28 capitalize">{{ s.replace('_',' ') }}</span>
              <div class="h-2 flex-1 rounded bg-muted">
                <div class="h-2 rounded bg-primary" :style="{ width: pct(avgTok[s], maxAvgTok) + '%' }"/>
              </div>
              <span class="w-24 text-right tabular-nums">{{ avgTok[s] ? Math.round(avgTok[s]).toLocaleString() : '—' }}</span>
            </div>
          </div>
          <p class="mt-3 text-[11px] text-muted-foreground">
            Total this view: {{ totalTokens.toLocaleString() }} tokens
            ({{ totalTokIn.toLocaleString() }} in / {{ totalTokOut.toLocaleString() }} out)
          </p>
        </div>
      </div>

      <!-- render-time trend -->
      <div class="mt-4 rounded-lg border bg-card p-4">
        <h2 class="mb-3 font-semibold">Render-time trend <span class="text-xs font-normal text-muted-foreground">(oldest → newest, stacked by stage)</span></h2>
        <div class="flex h-40 items-end gap-1">
          <div v-for="r in trend" :key="r.key" class="group relative flex-1" :title="title(r) + ' — ' + fmt(r.total_seconds)">
            <div class="flex w-full flex-col-reverse overflow-hidden rounded-t" :style="{ height: pct(r.total_seconds, maxTotal) + '%' }">
              <div v-for="s in STAGES" :key="s" :style="{ height: pct(stageSec(r,s), r.total_seconds||1) + '%', background: COLORS[s] }"/>
            </div>
          </div>
        </div>
        <div class="mt-1 text-[11px] text-muted-foreground">each bar = one render · height = total time</div>
      </div>

      <!-- per-piece table -->
      <div class="mt-4 rounded-lg border bg-card p-4">
        <h2 class="mb-3 font-semibold">Per-render breakdown</h2>
        <div class="space-y-2">
          <div v-for="r in records" :key="keyOf(r)" class="rounded border">
            <button class="flex w-full items-center gap-3 p-2 text-left hover:bg-muted/50" @click="toggle(keyOf(r))">
              <StatusBadge :status="r.status" dot />
              <span class="min-w-0 flex-1 truncate">{{ title(r) }}</span>
              <span
                v-if="r.theme" :title="`Visual theme: ${r.theme}. Every shot in a take shares one style so the piece hangs together.`"
                class="hidden rounded border border-stale-border bg-stale-bg px-1.5 py-0.5 text-[11px] text-stale sm:inline"
              >{{ r.theme }}</span>
              <span
                :title="`Aspect ratio ${r.format || '16:9'} — 9:16 is the vertical cut.`"
                class="hidden rounded border border-running-border bg-running-bg px-1.5 py-0.5 text-[11px] text-running sm:inline"
              >{{ r.format || '16:9' }}</span>
              <!-- mini stacked bar -->
              <span class="hidden h-3 w-40 overflow-hidden rounded md:flex">
                <span v-for="s in STAGES" :key="s" :style="{ width: pct(stageSec(r,s), r.total_seconds||1) + '%', background: COLORS[s] }"/>
              </span>
              <span class="w-16 text-right tabular-nums">{{ fmt(r.total_seconds) }}</span>
              <span class="w-20 text-right text-[11px] text-muted-foreground tabular-nums">{{ ((r.total_tokens_in||0)+(r.total_tokens_out||0)).toLocaleString() }} tok</span>
              <span class="w-4 text-muted-foreground">{{ open[keyOf(r)] ? '▾' : '▸' }}</span>
            </button>

            <div v-if="open[keyOf(r)]" class="border-t p-3 text-xs">
              <div class="grid grid-cols-2 gap-4 md:grid-cols-3">
                <div>
                  <div class="mb-1 font-medium text-muted-foreground">Stage timing</div>
                  <div v-for="s in STAGES" :key="s" class="flex justify-between">
                    <span class="capitalize">{{ s.replace('_',' ') }}</span>
                    <span class="tabular-nums">{{ stageSec(r,s) ? fmt(stageSec(r,s)) : '—' }}</span>
                  </div>
                </div>
                <div>
                  <div class="mb-1 font-medium text-muted-foreground">Tokens (in / out)</div>
                  <div v-for="s in STAGES" :key="s" class="flex justify-between">
                    <span class="capitalize">{{ s.replace('_',' ') }}</span>
                    <span class="tabular-nums">{{ tok(r,s) || '—' }}</span>
                  </div>
                </div>
                <div>
                  <div class="mb-1 font-medium text-muted-foreground">Output</div>
                  <div v-for="[k,v] in Object.entries(r.counts||{})" :key="k" class="flex justify-between">
                    <span class="capitalize">{{ k.replace(/_/g,' ') }}</span>
                    <span class="tabular-nums" :class="k.includes('fail') && v ? 'text-danger' : ''">{{ v }}</span>
                  </div>
                  <div class="mt-2 flex gap-3">
                    <NuxtLink :to="`/hn/item/${r.item_id}/run/${r.run}/segment/${r.seg}`" class="inline-block text-primary hover:underline">x-ray ↗</NuxtLink>
                    <NuxtLink :to="`/hn/item/${r.item_id}`" class="inline-block text-primary hover:underline">story ↗</NuxtLink>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </PageShell>
</template>

<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Icon } from '#components'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import EmptyState from '~/components/kit/EmptyState.vue'
import StatusBadge from '~/components/kit/StatusBadge.vue'
import LoadingRows from '~/components/kit/LoadingRows.vue'

useHead({ title: 'hn.fm · Observability' })

const config = useRuntimeConfig()
const apiBase = computed(() => config.public?.apiBase || 'http://localhost:8000')

const STAGES = ['scrape', 'source_images', 'script', 'audio', 'images', 'media_plan', 'video']
// Colours come from the shared vocabulary (usePipelineVocab), not a map
// declared here. This page and live.vue each had one, with different values.
const COLORS: Record<string, string> = Object.fromEntries(
  STAGES.map(s => [s, `hsl(var(--stage-${s}))`]),
)

// The shape `metrics.finalize` writes (see src/hnfm/utils/metrics.py). Typed
// out rather than left as `any` because this page is the only consumer, so a
// backend field rename should break here rather than render blank.
interface MetricsStage {
  seconds?: number
  llm_calls?: number
  tokens_in?: number
  tokens_out?: number
}

interface MetricsRecord {
  item_id: number
  run: number
  seg: number
  title: string | null
  theme: string | null
  format: string | null
  status: string
  partial_reason?: string
  stages: Record<string, MetricsStage>
  counts: Record<string, number>
  total_seconds?: number
  total_tokens_in?: number
  total_tokens_out?: number
  started_ts?: number
  finished_ts?: number
}

const records = ref<MetricsRecord[]>([])
const titles = ref<Record<number, string>>({})
const open = ref<Record<string, boolean>>({})
const loading = ref(true)

function keyOf(r: MetricsRecord) { return `${r.item_id}-${r.run}-${r.seg}` }
function toggle(k: string) { open.value[k] = !open.value[k] }
function stageSec(r: MetricsRecord, s: string) { return r.stages?.[s]?.seconds || 0 }
function tok(r: MetricsRecord, s: string) {
  const st = r.stages?.[s]; if (!st) return ''
  const i = st.tokens_in || 0, o = st.tokens_out || 0
  return (i || o) ? `${i.toLocaleString()} / ${o.toLocaleString()}` : ''
}
function title(r: MetricsRecord) { return titles.value[r.item_id] || `Item ${r.item_id} · run ${r.run}` }
function fmt(s: number) {
  if (!s) return '0s'
  if (s < 60) return `${s.toFixed(1)}s`
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}
function pct(a: number, b: number) { return b ? Math.round((a / b) * 1000) / 10 : 0 }

const avgStage = computed(() => {
  const o: Record<string, number> = {}
  for (const s of STAGES) {
    const vals = records.value.map(r => stageSec(r, s))
    o[s] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0
  }
  return o
})
const avgTotal = computed(() => Object.values(avgStage.value).reduce((a, b) => a + b, 0))
const maxAvgStage = computed(() => Math.max(1, ...Object.values(avgStage.value)))
const avgTok = computed(() => {
  const o: Record<string, number> = {}
  for (const s of STAGES) {
    const vals = records.value.map(r => (r.stages?.[s]?.tokens_in || 0) + (r.stages?.[s]?.tokens_out || 0))
    o[s] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0
  }
  return o
})
const maxAvgTok = computed(() => Math.max(1, ...Object.values(avgTok.value)))
const totalTokIn = computed(() => records.value.reduce((a, r) => a + (r.total_tokens_in || 0), 0))
const totalTokOut = computed(() => records.value.reduce((a, r) => a + (r.total_tokens_out || 0), 0))
const totalTokens = computed(() => totalTokIn.value + totalTokOut.value)
const trend = computed(() => [...records.value].reverse().slice(-40).map(r => ({ ...r, key: keyOf(r) })))
const maxTotal = computed(() => Math.max(1, ...records.value.map(r => r.total_seconds || 0)))

function sum(key: string) { return records.value.reduce((a, r) => a + (r.counts?.[key] || 0), 0) }
const cards = computed(() => {
  const n = records.value.length || 1
  const avgT = records.value.reduce((a, r) => a + (r.total_seconds || 0), 0) / n
  const ltx = sum('ltx_clips'), ltxF = sum('ltx_failures')
  return [
    { label: 'Renders', value: records.value.length },
    { label: 'Avg time', value: fmt(avgT) },
    { label: 'Avg tokens', value: Math.round(totalTokens.value / n).toLocaleString() },
    { label: 'LTX clips', value: ltx, sub: ltxF ? `${ltxF} failed` : 'all ok', cls: ltxF ? 'text-danger' : '' },
    { label: 'Hyperframes', value: sum('hyperframes') },
    { label: 'Source imgs', value: sum('source_images') },
  ]
})

async function load() {
  loading.value = true
  try {
    const resp = await $fetch<{ records?: MetricsRecord[] }>(
      `${apiBase.value}/api/metrics?limit=200`
    )
    records.value = resp?.records || []
    // resolve titles (unique items, capped)
    const ids = [...new Set(records.value.map(r => r.item_id))].slice(0, 60)
    await Promise.all(ids.map(async (id) => {
      try {
        const it = await $fetch<{ title?: string }>(
          `${apiBase.value}/api/hn/items/${id}`
        )
        if (it?.title) titles.value[id] = it.title
      } catch {
        // A missing title is cosmetic; the row falls back to "Item N · run M".
      }
    }))
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>
