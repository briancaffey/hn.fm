<script setup lang="ts">
import { computed } from 'vue'
import { Button } from '~/components/ui/button'
import { Icon } from '#components'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import StatusBadge from '~/components/kit/StatusBadge.vue'
import StatTile from '~/components/kit/StatTile.vue'
import LoadingRows from '~/components/kit/LoadingRows.vue'
import InfoHint from '~/components/kit/InfoHint.vue'

useHead({ title: 'hn.fm · Services' })

interface Service {
  name: string
  url: string
  status: 'online' | 'offline' | 'error' | 'disabled'
  response_time: number
  details?: unknown
  error_message?: string
}
interface ServicesResponse {
  all_healthy: boolean
  timestamp: string
  services: Service[]
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const { data, pending, refresh } = await useAsyncData<ServicesResponse>('services', () =>
  $fetch(`${apiBase}/api/services/status`))

onMounted(() => {
  const t = setInterval(refresh, 30000)
  onUnmounted(() => clearInterval(t))
})

/**
 * What each backend does and what the pipeline does without it. The page used
 * to list names and green dots, which told you a thing was down but not
 * whether that mattered.
 */
const ROLE: Record<string, { does: string, without: string }> = {
  LLM: {
    does: 'Every text call — summaries, triage scores, scripts, image prompts, Story Briefs.',
    without: 'Nothing generates. Transient failures retry on the same model before giving up.',
  },
  Scrape: {
    does: 'Fetches the linked article and turns it into clean markdown.',
    without: 'Stories fall back to their HN title and text, and the scrape gate stops most of them before any LLM is spent.',
  },
  TTS: {
    does: 'Turns each script section into speech.',
    without: 'No audio, so no podcast episodes and no video soundtrack.',
  },
  Image: {
    does: 'Renders one scene per script section.',
    without: 'No visuals, so video runs cannot assemble.',
  },
  ASR: {
    does: 'Transcribes the generated audio back to check it against the script.',
    without: 'Audio still renders; the quality check on it is skipped.',
  },
  Music: {
    does: 'Generates the background bed under a video.',
    without: 'Video assembles without music.',
  },
  Video: {
    does: 'Image-to-video motion clips for sections that call for movement.',
    without: 'Those sections fall back to image sequences — the planner routes around it rather than queueing work that will fail.',
  },
  Enhance: {
    does: 'Optional speech cleanup after TTS.',
    without: 'Audio ships as synthesised.',
  },
}

function roleOf(name: string) {
  const key = name.split('·')[0]?.trim() ?? ''
  return ROLE[key]
}

const services = computed(() => data.value?.services ?? [])
const online = computed(() => services.value.filter(s => s.status === 'online'))
const down = computed(() => services.value.filter(s => s.status === 'offline' || s.status === 'error'))
const disabled = computed(() => services.value.filter(s => s.status === 'disabled'))

const slowest = computed(() => {
  const timed = online.value.filter(s => s.response_time != null)
  if (!timed.length) return null
  return timed.reduce((a, b) => (a.response_time > b.response_time ? a : b))
})

function ms(n?: number | null) {
  if (n == null) return '—'
  return n < 1 ? `${Math.round(n * 1000)} ms` : `${n.toFixed(2)} s`
}
function when(ts?: string) {
  return ts ? new Date(ts).toLocaleTimeString() : '—'
}
</script>

<template>
  <PageShell>
    <PageHeader
      title="Services"
      subtitle="The inference backends this pipeline calls, and what happens when one is down."
      hint="Each service runs in the inference-club cluster and is reached over a .lan ingress. Health is re-checked every 30 seconds. Most are optional in the sense that the pipeline degrades rather than fails — the notes on each card say how."
      :meta="[`checked ${when(data?.timestamp)}`]"
    >
      <template #actions>
        <Button variant="outline" size="sm" :disabled="pending" @click="refresh()">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" :class="pending ? 'animate-spin' : ''" />
          Re-check
        </Button>
      </template>
    </PageHeader>

    <section class="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile
        label="Online" :value="online.length" tone="ok"
        hint="Answering their health endpoint."
      />
      <StatTile
        label="Down" :value="down.length" :tone="down.length ? 'danger' : 'default'"
        hint="Unreachable or erroring. The pipeline plans around these rather than queueing work at them."
      />
      <StatTile
        label="Disabled" :value="disabled.length"
        hint="Deliberately switched off in config — not a fault."
      />
      <StatTile
        label="Slowest" :value="slowest ? ms(slowest.response_time) : '—'"
        :detail="slowest?.name"
        hint="Longest health-check round trip. A slow backend shows up as a slow stage long before it shows up as an error."
      />
    </section>

    <LoadingRows v-if="pending && !services.length" class="mt-6" :rows="4" height="h-24" />

    <div v-else class="mt-6 space-y-6">
      <section v-if="down.length">
        <h2 class="mb-2 flex items-center gap-1.5 text-sm font-semibold">
          Needs attention
          <InfoHint text="A backend being down is usually survivable — the note on each card says what the pipeline does instead." />
        </h2>
        <div class="grid gap-3 md:grid-cols-2">
          <article
            v-for="s in down" :key="s.name"
            class="rounded-lg border border-danger-border bg-danger-bg/40 p-4"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium">{{ s.name }}</p>
                <p class="mt-0.5 truncate font-mono text-xs text-muted-foreground">{{ s.url || '—' }}</p>
              </div>
              <StatusBadge :status="s.status === 'error' ? 'error' : 'error'" :label="s.status" dot />
            </div>
            <p v-if="roleOf(s.name)" class="mt-2 text-xs leading-relaxed text-muted-foreground">
              <span class="font-medium text-foreground">Without it:</span>
              {{ roleOf(s.name)!.without }}
            </p>
            <p v-if="s.error_message" class="mt-2 rounded border border-danger-border bg-danger-bg px-2 py-1 font-mono text-[11px] text-danger">
              {{ s.error_message }}
            </p>
          </article>
        </div>
      </section>

      <section>
        <h2 class="mb-2 text-sm font-semibold">All services</h2>
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <article
            v-for="s in services" :key="s.name"
            class="flex flex-col rounded-lg border bg-card p-4 transition-colors hover:bg-elevated"
          >
            <div class="flex items-start justify-between gap-3">
              <p class="min-w-0 truncate text-sm font-medium">{{ s.name }}</p>
              <StatusBadge
                :status="s.status === 'online' ? 'ok' : s.status === 'disabled' ? 'idle' : 'error'"
                :label="s.status" dot
              />
            </div>
            <p v-if="roleOf(s.name)" class="mt-1.5 text-xs leading-relaxed text-muted-foreground">
              {{ roleOf(s.name)!.does }}
            </p>
            <div class="mt-auto flex items-center justify-between gap-2 pt-3 text-xs text-muted-foreground">
              <span class="truncate font-mono">{{ s.url || '—' }}</span>
              <span v-if="s.status === 'online'" class="shrink-0 tabular-nums">{{ ms(s.response_time) }}</span>
            </div>
          </article>
        </div>
      </section>
    </div>
  </PageShell>
</template>
