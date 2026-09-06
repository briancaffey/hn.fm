<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Icon } from '#components'
import { Button } from '~/components/ui/button'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import StatTile from '~/components/kit/StatTile.vue'
import LoadingRows from '~/components/kit/LoadingRows.vue'
import InfoHint from '~/components/kit/InfoHint.vue'

/**
 * How the prompts got to where they are.
 *
 * Every metric here is computed without a model and without a human, so a
 * change is judged by whether a number moved rather than by whether the output
 * felt better. Rounds that made things worse are kept — a log that only
 * records wins is not a log.
 */
useHead({ title: 'hn.fm · Evolution' })

interface Round {
  label: string
  at: string | null
  summary: Record<string, number | null>
  stories: Array<Record<string, unknown>>
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase
const rounds = ref<Round[]>([])
const changelog = ref('')
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const r = await $fetch<{ rounds: Round[], changelog: string }>(`${apiBase}/api/evolution`)
    rounds.value = r.rounds
    changelog.value = r.changelog
  } catch {
    rounds.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)

/** What each metric means, and which direction is good. */
const METRICS: Record<string, { label: string, hint: string, lowerBetter: boolean }> = {
  switch_rate: { label: 'Speaker switch', lowerBetter: true,
    hint: 'Share of adjacent sections that change speaker. Near 1.0 is pure ping-pong; the intended rhythm is runs of two or three, around 0.4-0.5.' },
  repeated_openings: { label: 'Repeated openings', lowerBetter: true,
    hint: 'Share of sections starting with the same words as another. Reads as formulaic long before any single line looks wrong.' },
  script_lex: { label: 'Script vocabulary', lowerBetter: false,
    hint: 'Distinct content words over total. Low means the same words over and over.' },
  length_variation: { label: 'Length variation', lowerBetter: false,
    hint: 'Spread of section lengths. Uniform lengths sound machine-paced however good each line is.' },
  intent_overlap: { label: 'Intent overlap', lowerBetter: true,
    hint: 'How similar the writer’s declared visual subjects are to each other. Already near-perfect; the loss happens downstream.' },
  intent_lex: { label: 'Intent vocabulary', lowerBetter: false, hint: 'Vocabulary spread across visual intents.' },
  subject_overlap: { label: 'Scene overlap', lowerBetter: true,
    hint: 'Pairwise word overlap between a take’s image prompts. Note the floor: scenes from three different stories still score 0.161, so the honest reading is excess above that, not the raw number.' },
  tableau_rate: { label: 'Tech-tableau rate', lowerBetter: true,
    hint: 'Share of frames containing a desk, laptop, screen, monitor or office. This is the number that tracks "another picture of a desk" — the complaint that started this work.' },
  lexical_diversity: { label: 'Scene vocabulary', lowerBetter: false, hint: 'Vocabulary spread across a take’s image prompts.' },
  shot_coverage: { label: 'Shot coverage', lowerBetter: false,
    hint: 'Distinct camera treatments. Was already healthy while subjects repeated — which is how we knew angle was never the problem.' },
  max_pair_overlap: { label: 'Worst pair', lowerBetter: true, hint: 'The most similar pair of prompts in a take.' },
  near_duplicate_pairs: { label: 'Near-duplicates', lowerBetter: true, hint: 'Pairs sharing more than half their vocabulary.' },
}

const ordered = computed(() => rounds.value)

function delta(metric: string, i: number): number | null {
  if (i === 0) return null
  const cur = ordered.value[i]?.summary?.[metric]
  // Compare against the most recent earlier round that measured the same thing.
  for (let j = i - 1; j >= 0; j--) {
    const prev = ordered.value[j]?.summary?.[metric]
    if (typeof cur === 'number' && typeof prev === 'number') return cur - prev
  }
  return null
}
function good(metric: string, d: number | null) {
  if (d === null || Math.abs(d) < 0.004) return null
  const lower = METRICS[metric]?.lowerBetter
  return lower ? d < 0 : d > 0
}
const fmt = (v: unknown) => typeof v === 'number' ? v.toFixed(3) : '—'
</script>

<template>
  <PageShell>
    <PageHeader
      title="Prompt evolution"
      subtitle="What was measured, what changed, and whether the number actually moved."
      hint="Each round regenerates the same three deliberately unalike stories — consumer hardware, systems internals, and a web-history piece with no hardware in it — so a fix that only works on one kind of story shows up as not generalising. Rounds that made things worse are kept."
      :meta="loading ? [] : [`${rounds.length} rounds`]"
    >
      <template #actions>
        <Button variant="outline" size="sm" :disabled="loading" @click="load">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
          Refresh
        </Button>
      </template>
    </PageHeader>

    <LoadingRows v-if="loading && !rounds.length" :rows="4" height="h-24" />

    <template v-else-if="rounds.length">
      <section class="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Rounds" :value="rounds.length"
          hint="Each is a full regeneration of the same three stories, so rounds are comparable."
        />
        <StatTile
          label="Tech-tableau rate" value="0.413 → 0.315" tone="ok"
          detail="24% fewer desk frames"
          :hint="METRICS.tableau_rate.hint"
        />
        <StatTile
          label="Min sections" value="6 → 12" tone="ok"
          detail="a six-section video was too short to watch"
          hint="The lowest section count across the three test stories. Fixed with a retry guard, not a prompt — count came back as 9, 8, 3 and 6 across four samples of the same story."
        />
        <StatTile
          label="Changes reverted" value="2" tone="warn"
          detail="numeric rhythm quota; softened floor"
          hint="A numeric target made the model aim for the middle, and a softer section floor collapsed one script to three sections. Both are in the log."
        />
      </section>

      <section class="mt-6 overflow-x-auto rounded-lg border bg-card">
        <div class="flex items-center gap-1.5 border-b px-4 py-2.5">
          <h2 class="text-sm font-semibold">Round by round</h2>
          <InfoHint text="Arrows compare against the previous round that measured the same metric. Green means it moved the way we wanted." />
        </div>
        <table class="w-full text-xs">
          <thead class="border-b text-left text-muted-foreground">
            <tr>
              <th class="px-4 py-2 font-medium">Round</th>
              <th v-for="(m, k) in METRICS" :key="k" class="px-3 py-2 text-right font-medium">
                <span :title="m.hint">{{ m.label }}</span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y">
            <tr v-for="(r, i) in ordered" :key="r.label" class="hover:bg-muted/40">
              <td class="whitespace-nowrap px-4 py-2 font-mono">{{ r.label }}</td>
              <td v-for="(m, k) in METRICS" :key="k" class="px-3 py-2 text-right tabular-nums">
                <template v-if="typeof r.summary[k] === 'number'">
                  {{ fmt(r.summary[k]) }}
                  <span
                    v-if="good(k, delta(k, i)) !== null"
                    class="ml-1"
                    :class="good(k, delta(k, i)) ? 'text-ok' : 'text-danger'"
                  >{{ good(k, delta(k, i)) ? '▲' : '▼' }}</span>
                </template>
                <span v-else class="text-muted-foreground/40">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="mt-4 rounded-lg border bg-card">
        <div class="border-b px-4 py-2.5">
          <h2 class="text-sm font-semibold">The log</h2>
        </div>
        <pre class="overflow-x-auto p-4 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">{{ changelog }}</pre>
      </section>
    </template>
  </PageShell>
</template>
