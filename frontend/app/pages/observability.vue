<template>
  <div class="mx-auto max-w-7xl p-4 text-sm">
    <div class="mb-4 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold">Pipeline Observability</h1>
        <p class="text-xs text-muted-foreground">
          {{ records.length }} renders · x-ray into time, tokens & output per stage
        </p>
      </div>
      <button class="rounded border px-2 py-1 text-xs hover:bg-muted" @click="load">Refresh</button>
    </div>

    <p v-if="loading" class="text-xs text-muted-foreground">Loading metrics…</p>
    <p v-else-if="!records.length" class="text-xs text-muted-foreground">
      No metrics yet — render a video and it'll show up here.
    </p>

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
            <div v-for="s in STAGES" :key="s"
              :style="{ width: pct(avgStage[s], avgTotal) + '%', background: COLORS[s] }"
              :title="`${s}: ${fmt(avgStage[s])} (${pct(avgStage[s], avgTotal)}%)`"></div>
          </div>
          <div class="space-y-1.5">
            <div v-for="s in STAGES" :key="s" class="flex items-center gap-2 text-xs">
              <span class="inline-block h-3 w-3 rounded-sm" :style="{ background: COLORS[s] }"></span>
              <span class="w-28 capitalize">{{ s.replace('_',' ') }}</span>
              <div class="h-2 flex-1 rounded bg-muted">
                <div class="h-2 rounded" :style="{ width: pct(avgStage[s], maxAvgStage) + '%', background: COLORS[s] }"></div>
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
                <div class="h-2 rounded bg-orange-500" :style="{ width: pct(avgTok[s], maxAvgTok) + '%' }"></div>
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
              <div v-for="s in STAGES" :key="s" :style="{ height: pct(stageSec(r,s), r.total_seconds||1) + '%', background: COLORS[s] }"></div>
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
              <span class="text-xs" :class="r.status==='ok' ? 'text-green-600' : 'text-red-600'">●</span>
              <span class="min-w-0 flex-1 truncate">{{ title(r) }}</span>
              <span v-if="r.theme" class="hidden rounded bg-purple-100 px-1.5 py-0.5 text-[11px] text-purple-900 dark:bg-purple-900 dark:text-purple-100 sm:inline">{{ r.theme }}</span>
              <span class="hidden rounded bg-blue-100 px-1.5 py-0.5 text-[11px] text-blue-900 dark:bg-blue-900 dark:text-blue-100 sm:inline">{{ r.format || '16:9' }}</span>
              <!-- mini stacked bar -->
              <span class="hidden h-3 w-40 overflow-hidden rounded md:flex">
                <span v-for="s in STAGES" :key="s" :style="{ width: pct(stageSec(r,s), r.total_seconds||1) + '%', background: COLORS[s] }"></span>
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
                    <span class="tabular-nums" :class="k.includes('fail') && v ? 'text-red-600' : ''">{{ v }}</span>
                  </div>
                  <NuxtLink :to="`/hn/item/${r.item_id}/compare`" class="mt-2 inline-block text-blue-600 hover:underline">watch ↗</NuxtLink>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
const config = useRuntimeConfig()
const apiBase = computed(() => config.public?.apiBase || 'http://localhost:8000')

const STAGES = ['scrape', 'source_images', 'script', 'audio', 'images', 'media_plan', 'video']
const COLORS: Record<string, string> = {
  scrape: '#64748b', source_images: '#0ea5e9', script: '#a855f7', audio: '#22c55e',
  images: '#f97316', media_plan: '#eab308', video: '#ef4444',
}

const records = ref<any[]>([])
const titles = ref<Record<number, string>>({})
const open = ref<Record<string, boolean>>({})
const loading = ref(true)

function keyOf(r: any) { return `${r.item_id}-${r.run}-${r.seg}` }
function toggle(k: string) { open.value[k] = !open.value[k] }
function stageSec(r: any, s: string) { return r.stages?.[s]?.seconds || 0 }
function tok(r: any, s: string) {
  const st = r.stages?.[s]; if (!st) return ''
  const i = st.tokens_in || 0, o = st.tokens_out || 0
  return (i || o) ? `${i.toLocaleString()} / ${o.toLocaleString()}` : ''
}
function title(r: any) { return titles.value[r.item_id] || `Item ${r.item_id} · run ${r.run}` }
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
    { label: 'LTX clips', value: ltx, sub: ltxF ? `${ltxF} failed` : 'all ok', cls: ltxF ? 'text-red-600' : '' },
    { label: 'Hyperframes', value: sum('hyperframes') },
    { label: 'Source imgs', value: sum('source_images') },
  ]
})

async function load() {
  loading.value = true
  try {
    const resp: any = await $fetch(`${apiBase.value}/api/metrics?limit=200`)
    records.value = resp?.records || []
    // resolve titles (unique items, capped)
    const ids = [...new Set(records.value.map(r => r.item_id))].slice(0, 60)
    await Promise.all(ids.map(async (id) => {
      try { const it: any = await $fetch(`${apiBase.value}/api/hn/items/${id}`); if (it?.title) titles.value[id] = it.title } catch (_) {}
    }))
  } catch (e) { records.value = [] } finally { loading.value = false }
}
onMounted(load)
</script>
