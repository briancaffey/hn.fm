<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '#components'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import { Button } from '~/components/ui/button'
import type { Edition, Show, StationStatus } from '~/composables/useStation'

/**
 * The desk: the three things hn.fm publishes, each with what was last
 * made, a button to make the next one, and its switch. Everything here
 * could already be done somewhere; this is the one place it can all be
 * done from.
 */
useHead({ title: 'hn.fm · The desk' })

interface Digest {
  slug: string, formats: string[], bytes: number, modified: string, sent_at: string | null
  edition_name: string | null, shape: string | null
}
interface Segment { item_id: number, run: number, seg: number, created_at: string, title?: string, video_ready?: boolean }
interface StoryVideo {
  id: string, item_id: number, title?: string, state: string, step?: string, video: boolean, poster: boolean
  directed?: number, total?: number, length?: number, seconds?: number, bytes?: number, author?: string
  note?: string, error?: string, updated_at?: string
}
interface Candidate { item_id: number, run: number, seg: number, title: string, made: string | null }
interface Check { name: string, purpose: string, optional: boolean, ok: boolean | null, detail: string, seconds: number | null }
interface LogLine { id: number, at: string, component: string, message: string }
interface RadioSettings { produce: string, modes: string[], edition_hours: number[], producing: boolean }

const { apiBase, art, mins, day, hour } = useStation()
const controls = ref<{ scraping_paused: boolean, generation_paused: boolean } | null>(null)
const delivery = ref<{ ready: boolean, detail: string } | null>(null)
const digests = ref<Digest[]>([])
const radio = ref<StationStatus | null>(null)
const settings = ref<RadioSettings | null>(null)
const editions = ref<Edition[]>([])
const segments = ref<Segment[]>([])
const log = ref<LogLine[]>([])
const covers = ref<{ key: string, drawn: boolean }[]>([])
const videos = ref<StoryVideo[]>([])
const candidates = ref<Candidate[]>([])
const agent = ref(false)
const pick = ref('')
const watching = ref<StoryVideo | null>(null)
const checks = ref<{ at: string | null, running?: boolean, checks: Check[], working?: number, of?: number } | null>(null)
const checking = ref(false)
const note = ref<Record<string, string>>({})
const preview = ref<Digest | null>(null)
const confirming = ref<string | null>(null)
const stamp = ref(Date.now())

const say = (where: string, text: string) => { note.value = { ...note.value, [where]: text } }

async function load() {
  const [sch, dg, st, sg] = await Promise.allSettled([
    $fetch<{ controls: typeof controls.value, delivery: typeof delivery.value }>(`${apiBase}/api/schedule`),
    $fetch<{ digests: Digest[] }>(`${apiBase}/api/digests`),
    $fetch<StationStatus>(`${apiBase}/api/radio/status`),
    $fetch<{ segments: Segment[] }>(`${apiBase}/api/segments?limit=6`),
  ])
  if (sch.status === 'fulfilled') { controls.value = sch.value.controls; delivery.value = sch.value.delivery }
  if (dg.status === 'fulfilled') digests.value = dg.value.digests.slice(0, 4)
  if (sg.status === 'fulfilled') segments.value = sg.value.segments
  if (st.status === 'fulfilled') radio.value = st.value
  const [vd, inf] = await Promise.allSettled([
    $fetch<{ videos: StoryVideo[], candidates: Candidate[], agent: boolean }>(`${apiBase}/api/videos`),
    $fetch<typeof checks.value>(`${apiBase}/api/inference`),
  ])
  if (vd.status === 'fulfilled') { videos.value = vd.value.videos; candidates.value = vd.value.candidates; agent.value = vd.value.agent }
  if (inf.status === 'fulfilled') {
    if (checking.value && inf.value?.at && inf.value.at !== checks.value?.at) checking.value = false
    checks.value = inf.value
  }
  if (radio.value?.enabled) {
    const [se, ar, lg, cv] = await Promise.allSettled([
      $fetch<RadioSettings>(`${apiBase}/api/radio/settings`),
      $fetch<{ editions: Edition[] }>(`${apiBase}/api/radio/archive?limit=60`),
      $fetch<{ lines: LogLine[] }>(`${apiBase}/api/radio/log?limit=80`),
      $fetch<{ art: { key: string, drawn: boolean }[] }>(`${apiBase}/api/radio/art`),
    ])
    if (se.status === 'fulfilled') settings.value = se.value
    if (ar.status === 'fulfilled') editions.value = [...ar.value.editions].sort((a, b) => b.aired_at.localeCompare(a.aired_at))
    // What is being made, not what is being played: the DJ's lines are the control room's.
    if (lg.status === 'fulfilled') log.value = lg.value.lines.filter(l => ['booth', 'producer', 'bank'].includes(l.component)).reverse()
    if (cv.status === 'fulfilled') covers.value = cv.value.art
  }
}
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => { load(); timer = setInterval(load, 6000) })
onUnmounted(() => { if (timer) clearInterval(timer) })

// --- switches ---------------------------------------------------------------
async function setControl(key: 'scraping_paused' | 'generation_paused', value: boolean) {
  controls.value = await $fetch(`${apiBase}/api/schedule/controls`, { method: 'POST', body: { [key]: value } })
}
async function setRadio(body: Partial<{ produce: string, edition_hours: number[] }>) {
  settings.value = await $fetch(`${apiBase}/api/radio/settings`, { method: 'POST', body })
}
function toggleHour(h: number) {
  const have = settings.value?.edition_hours || []
  setRadio({ edition_hours: have.includes(h) ? have.filter(x => x !== h) : [...have, h] })
}
const MODES: Record<string, { label: string, what: string }> = {
  off: { label: 'Off', what: 'Nothing is made unless you ask for it here.' },
  listeners: { label: 'When someone listens', what: 'New programming while someone is tuned in to the stream.' },
  always: { label: 'Always', what: 'Around the clock, whoever is listening. Keeps the models busy all day.' },
}

// --- reading ----------------------------------------------------------------
const SHAPES = [
  { value: 'daily', label: 'Daily', what: 'A teaser, quick hits, two features.' },
  { value: 'deep', label: 'Deep', what: 'Three stories, two of them features.' },
  { value: 'scan', label: 'Scan', what: 'Eight quick hits.' },
  { value: 'punchline', label: 'Punchline', what: 'The whole front page, each story in a few bullets.' },
]
const shape = ref('daily')
const sendToo = ref(false)
async function buildDigest() {
  try {
    await $fetch(`${apiBase}/api/digests`, { method: 'POST', body: { shape: shape.value, send: sendToo.value, score_first: true } })
    say('reading', sendToo.value ? 'Queued. It will be sent to the e-reader when it is built.' : 'Queued. It appears here when it is built, a few minutes from now.')
  } catch { say('reading', 'Could not queue the build.') }
}
async function sendDigest(d: Digest) {
  try {
    await $fetch(`${apiBase}/api/digests/${d.slug}/send`, { method: 'POST' })
    say('reading', `Sent ${d.edition_name || d.slug} to the e-reader.`); load()
  } catch { say('reading', 'Sending failed. The delivery line above says why, if it knows.') }
}
const kb = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} KB`)
const ago = (iso: string) => {
  const s = (Date.now() - new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z').getTime()) / 1000
  if (s < 90) return 'just now'
  if (s < 5400) return `${Math.round(s / 60)} min ago`
  if (s < 129600) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} days ago`
}

// --- radio ------------------------------------------------------------------
const shows = computed<Show[]>(() => radio.value?.schedule || [])
async function makeEpisode(s: Show, whole: boolean) {
  try {
    await $fetch(`${apiBase}/api/radio/edition`, { method: 'POST', body: { hour: s.start, whole, quarter: 0 } })
    say('radio', whole
      ? `Asked for a whole hour of ${s.name}. About twenty minutes; watch it being made below.`
      : `Asked for the opening block of ${s.name}. About five minutes.`)
  } catch { say('radio', 'Could not ask for it.') }
}
async function feature(e: Edition) {
  await $fetch(`${apiBase}/api/radio/editions/${e.id}`, { method: 'PATCH', body: { featured: !e.featured } }); load()
}
async function makeVideo(e: Edition) {
  await $fetch(`${apiBase}/api/radio/editions/${e.id}/video`, { method: 'POST' })
  say('video', `Asked for a video of ${e.show_name}, ${day(e.date)}. A minute or two.`)
}
async function removeEdition(e: Edition) {
  if (confirming.value !== e.id) { confirming.value = e.id; return }
  confirming.value = null
  await $fetch(`${apiBase}/api/radio/editions/${e.id}`, { method: 'DELETE' }); load()
}
async function drawCovers(key?: string) {
  await $fetch(`${apiBase}/api/radio/art`, { method: 'POST', body: key ? { key } : {} })
  say('video', key ? 'Redrawing that cover. About ten seconds; it changes here when it is done.' : 'Drawing the missing covers.')
  setTimeout(() => { stamp.value = Date.now() }, 15000)
}
// --- story videos and the inference check -----------------------------------
async function makeStoryVideo(direct = true) {
  const c = candidates.value.find(x => `${x.item_id}-${x.run}-${x.seg}` === pick.value) || candidates.value[0]
  if (!c) return
  await $fetch(`${apiBase}/api/videos`, { method: 'POST', body: { item_id: c.item_id, run: c.run, seg: c.seg, direct } })
  say('story', `Asked for “${c.title}”. A two-and-a-half minute video takes about four minutes.`)
  pick.value = ''
  load()
}
async function remakeStoryVideo(v: StoryVideo) {
  const [item_id, run, seg] = v.id.split('-').map(Number)
  await $fetch(`${apiBase}/api/videos`, { method: 'POST', body: { item_id, run, seg } })
  say('story', `Making “${v.title}” again.`)
  load()
}
async function removeStoryVideo(v: StoryVideo) {
  if (confirming.value !== `v-${v.id}`) { confirming.value = `v-${v.id}`; return }
  confirming.value = null
  await $fetch(`${apiBase}/api/videos/${v.id}`, { method: 'DELETE' })
  load()
}
const busy = (v: StoryVideo) => !['done', 'failed'].includes(v.state)
async function runChecks() {
  checking.value = true
  await $fetch(`${apiBase}/api/inference/check`, { method: 'POST' })
}

const withVideo = computed(() => editions.value.filter(e => e.video).slice(0, 4))
const working = computed(() => log.value.some(l => Date.now() - new Date(l.at + 'Z').getTime() < 90_000
  && ['booth', 'producer', 'bank'].includes(l.component)))
</script>

<template>
  <PageShell>
    <PageHeader
      title="The desk"
      subtitle="What hn.fm publishes: something to read, something to hear, something to watch. Make the next one, or turn its tap off."
      hint="Each column is one product. The switches at the top of a column change what happens on a timer; the buttons make one thing now, whatever the switches say."
    />

    <div class="grid gap-5 xl:grid-cols-3">
      <!-- ============================ READING ============================ -->
      <section class="flex flex-col rounded-xl border bg-card">
        <header class="flex items-center gap-2 border-b px-4 py-3">
          <Icon name="lucide:book-open" class="h-4 w-4 text-primary" />
          <h2 class="text-sm font-semibold">To read</h2>
          <NuxtLink to="/digests" class="ml-auto text-xs text-primary hover:underline">All digests →</NuxtLink>
        </header>
        <div class="flex flex-1 flex-col gap-4 p-4">
          <div class="flex flex-col gap-2 text-sm">
            <label class="flex items-start justify-between gap-3">
              <span><span class="font-medium">Fetch Hacker News</span>
                <span class="block text-xs text-muted-foreground">New and front-page stories, scored as they arrive.</span></span>
              <input type="checkbox" class="mt-1 h-4 w-4 accent-[var(--primary)]" :checked="controls ? !controls.scraping_paused : false" :disabled="!controls" @change="setControl('scraping_paused', !($event.target as HTMLInputElement).checked)">
            </label>
            <label class="flex items-start justify-between gap-3">
              <span><span class="font-medium">Digests and videos on a timer</span>
                <span class="block text-xs text-muted-foreground">Three digests a day, each emailed to the e-reader, and one video every six hours.</span></span>
              <input type="checkbox" class="mt-1 h-4 w-4 accent-[var(--primary)]" :checked="controls ? !controls.generation_paused : false" :disabled="!controls" @change="setControl('generation_paused', !($event.target as HTMLInputElement).checked)">
            </label>
            <p v-if="delivery" class="text-xs" :class="delivery.ready ? 'text-muted-foreground' : 'text-destructive'">
              E-reader delivery: {{ delivery.ready ? 'ready' : delivery.detail }}
            </p>
          </div>

          <div class="rounded-lg border p-3">
            <p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Make a digest now</p>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <button
                v-for="s in SHAPES" :key="s.value" type="button" :title="s.what"
                class="rounded-full border px-2.5 py-1 text-xs" :class="shape === s.value ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'"
                @click="shape = s.value"
              >{{ s.label }}</button>
            </div>
            <p class="mt-2 text-xs text-muted-foreground">{{ SHAPES.find(s => s.value === shape)?.what }}</p>
            <div class="mt-3 flex items-center gap-3">
              <Button size="sm" @click="buildDigest">Build it</Button>
              <label class="flex items-center gap-1.5 text-xs text-muted-foreground"><input v-model="sendToo" type="checkbox" class="accent-[var(--primary)]"> and send it to the e-reader</label>
            </div>
            <p v-if="note.reading" class="mt-2 text-xs text-muted-foreground" role="status">{{ note.reading }}</p>
          </div>

          <ul class="divide-y text-sm">
            <li v-for="d in digests" :key="d.slug" class="flex items-center gap-3 py-2.5">
              <span class="min-w-0 flex-1">
                <span class="block truncate font-medium">{{ d.edition_name || d.slug }}</span>
                <span class="block text-xs text-muted-foreground">{{ d.shape }} · {{ kb(d.bytes) }} · {{ ago(d.modified) }} · {{ d.sent_at ? 'sent' : 'not sent' }}</span>
              </span>
              <Button variant="outline" size="sm" @click="preview = d">Read</Button>
              <Button variant="ghost" size="sm" :title="d.sent_at ? 'Send again' : 'Send to the e-reader'" @click="sendDigest(d)"><Icon name="lucide:send" class="h-3.5 w-3.5" /></Button>
            </li>
            <li v-if="!digests.length" class="py-3 text-xs text-muted-foreground">No digests built yet.</li>
          </ul>
        </div>
      </section>

      <!-- ============================= RADIO ============================= -->
      <section class="flex flex-col rounded-xl border bg-card">
        <header class="flex items-center gap-2 border-b px-4 py-3">
          <Icon name="lucide:radio" class="h-4 w-4 text-primary" />
          <h2 class="text-sm font-semibold">To hear</h2>
          <span v-if="working" class="flex items-center gap-1 text-xs text-primary"><Icon name="lucide:loader-circle" class="h-3 w-3 animate-spin" /> making</span>
          <span class="ml-auto flex gap-3 text-xs">
            <NuxtLink to="/listen" class="text-primary hover:underline">Listen page →</NuxtLink>
            <NuxtLink to="/radio" class="text-primary hover:underline">Control room →</NuxtLink>
          </span>
        </header>
        <div v-if="!radio?.enabled" class="p-4 text-sm text-muted-foreground">The station is switched off in this deployment.</div>
        <div v-else class="flex flex-1 flex-col gap-4 p-4">
          <div v-if="settings">
            <p class="text-sm font-medium">New programming</p>
            <div class="mt-1.5 inline-flex rounded-lg border p-0.5" role="radiogroup" aria-label="Production">
              <button
                v-for="m in settings.modes.slice().sort((a, b) => Object.keys(MODES).indexOf(a) - Object.keys(MODES).indexOf(b))" :key="m" type="button" role="radio" :aria-checked="settings.produce === m"
                class="rounded-md px-2.5 py-1 text-xs" :class="settings.produce === m ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'"
                @click="setRadio({ produce: m })"
              >{{ MODES[m]?.label || m }}</button>
            </div>
            <p class="mt-1.5 text-xs text-muted-foreground">{{ MODES[settings.produce]?.what }}</p>
            <p class="mt-3 text-sm font-medium">An episode every day of</p>
            <div class="mt-1.5 flex flex-wrap gap-1.5">
              <button
                v-for="s in shows" :key="s.key" type="button" :aria-pressed="settings.edition_hours.includes(s.start)"
                class="rounded-full border px-2.5 py-1 text-xs" :class="settings.edition_hours.includes(s.start) ? 'border-primary bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground'"
                @click="toggleHour(s.start)"
              >{{ s.name }}</button>
            </div>
            <p class="mt-1.5 text-xs text-muted-foreground">
              {{ settings.edition_hours.length ? `Made at ${settings.edition_hours.map(hour).join(', ')} station time, for the archive.` : 'None. Episodes are made only when asked for below.' }}
            </p>
          </div>

          <div class="rounded-lg border p-3">
            <p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Make an episode now</p>
            <div class="mt-2 grid grid-cols-3 gap-2">
              <button
                v-for="s in shows" :key="s.key" type="button" :title="`A whole hour of ${s.name}`"
                class="group overflow-hidden rounded-md border text-left hover:border-primary" @click="makeEpisode(s, true)"
              >
                <img :src="`${art(s.key)}?v=${stamp}`" alt="" class="aspect-[16/9] w-full object-cover" loading="lazy">
                <span class="block truncate px-1.5 py-1 text-[11px] font-medium group-hover:text-primary">{{ s.name }}</span>
              </button>
            </div>
            <p class="mt-2 text-xs text-muted-foreground">A whole hour: about twenty minutes of programme, and about as long to make.</p>
            <p v-if="note.radio" class="mt-2 text-xs text-muted-foreground" role="status">{{ note.radio }}</p>
            <ol v-if="log.length" class="mt-2 flex flex-col gap-0.5 border-t pt-2 font-mono text-[11px] leading-snug text-muted-foreground">
              <li v-for="l in log.slice(0, 5)" :key="l.id" class="truncate"><span class="opacity-60">{{ l.component }}</span> {{ l.message }}</li>
            </ol>
          </div>

          <ul class="divide-y text-sm">
            <li v-for="e in editions.slice(0, 6)" :key="e.id" class="flex items-center gap-2 py-2.5">
              <img :src="`${art(e.show)}?v=${stamp}`" alt="" class="h-9 w-9 shrink-0 rounded object-cover">
              <NuxtLink :to="`/listen/${e.id}`" class="min-w-0 flex-1 hover:text-primary">
                <span class="block truncate font-medium">{{ e.show_name }}<span v-if="e.kind === 'episode'" class="font-normal text-muted-foreground"> · whole hour</span></span>
                <span class="block text-xs text-muted-foreground">{{ day(e.date) }} · {{ mins(e.seconds) }} · {{ e.stories.length }} stories</span>
              </NuxtLink>
              <Button variant="ghost" size="sm" :title="e.featured ? 'Stop featuring' : 'Feature on the listen page'" @click="feature(e)">
                <Icon name="lucide:star" class="h-3.5 w-3.5" :class="e.featured ? 'fill-primary text-primary' : ''" />
              </Button>
              <Button variant="ghost" size="sm" :title="e.video ? 'Make the video again' : 'Make a video of it'" @click="makeVideo(e)">
                <Icon name="lucide:video" class="h-3.5 w-3.5" :class="e.video ? 'text-primary' : ''" />
              </Button>
              <Button variant="ghost" size="sm" :title="confirming === e.id ? 'Press again to remove it' : 'Remove'" @click="removeEdition(e)">
                <Icon :name="confirming === e.id ? 'lucide:check' : 'lucide:trash-2'" class="h-3.5 w-3.5" :class="confirming === e.id ? 'text-destructive' : ''" />
              </Button>
            </li>
            <li v-if="!editions.length" class="py-3 text-xs text-muted-foreground">Nothing in the archive yet.</li>
          </ul>
        </div>
      </section>

      <!-- ============================= VIDEO ============================= -->
      <section class="flex flex-col rounded-xl border bg-card">
        <header class="flex items-center gap-2 border-b px-4 py-3">
          <Icon name="lucide:clapperboard" class="h-4 w-4 text-primary" />
          <h2 class="text-sm font-semibold">To watch</h2>
          <NuxtLink to="/segments" class="ml-auto text-xs text-primary hover:underline">All segments →</NuxtLink>
        </header>
        <div class="flex flex-1 flex-col gap-4 p-4">
          <div>
            <p class="text-sm font-medium">Story videos</p>
            <p class="text-xs text-muted-foreground">
              One story, narrated, as a single HyperFrames composition.
              <template v-if="agent">Hermes directs each scene: it reads the line and picks what to show.</template>
              <template v-else>No agent is connected, so scenes are the plain version.</template>
            </p>
            <div v-if="candidates.length" class="mt-2 flex gap-2">
              <label class="sr-only" for="story-pick">Story to make a video of</label>
              <select id="story-pick" v-model="pick" class="min-w-0 flex-1 rounded-md border bg-background px-2 py-1.5 text-xs">
                <option value="">{{ candidates[0].title }}</option>
                <option v-for="c in candidates.slice(1)" :key="`${c.item_id}-${c.run}-${c.seg}`" :value="`${c.item_id}-${c.run}-${c.seg}`">{{ c.title }}</option>
              </select>
              <Button size="sm" @click="makeStoryVideo()">Make</Button>
            </div>
            <p v-else class="mt-2 text-xs text-muted-foreground">Every narrated story has a video. Narrate another from <NuxtLink to="/triage" class="underline underline-offset-2">Triage</NuxtLink>.</p>
            <p v-if="note.story" class="mt-2 text-xs text-muted-foreground" role="status">{{ note.story }}</p>
            <ul class="mt-3 flex flex-col gap-3">
              <li v-for="v in videos.slice(0, 5)" :key="v.id" class="flex gap-3">
                <button v-if="v.video" type="button" class="relative h-[68px] w-[120px] shrink-0 overflow-hidden rounded-md border bg-black" :aria-label="`Play ${v.title}`" @click="watching = v">
                  <img v-if="v.poster" :src="`${apiBase}/api/videos/${v.id}/poster.jpg?v=${v.updated_at}`" alt="" class="h-full w-full object-cover" loading="lazy">
                  <span class="absolute inset-0 grid place-items-center bg-black/20 text-white"><Icon name="lucide:play" class="h-5 w-5" /></span>
                </button>
                <span v-else class="grid h-[68px] w-[120px] shrink-0 place-items-center rounded-md border border-dashed text-muted-foreground">
                  <Icon :name="v.state === 'failed' ? 'lucide:triangle-alert' : 'lucide:loader'" class="h-4 w-4" :class="busy(v) ? 'animate-spin' : ''" />
                </span>
                <div class="min-w-0 flex-1 text-xs">
                  <p class="truncate text-sm font-medium">{{ v.title || `Story ${v.item_id}` }}</p>
                  <p v-if="busy(v)" class="text-muted-foreground">{{ v.state }}: {{ v.step }}</p>
                  <p v-else-if="v.state === 'failed'" class="text-destructive">{{ v.error }}</p>
                  <p v-else class="text-muted-foreground">
                    {{ mins(v.length || 0) }} · {{ v.directed ?? 0 }} of {{ v.total }} scenes directed · made in {{ Math.round((v.seconds || 0) / 60) }} min · {{ kb(v.bytes || 0) }}
                  </p>
                  <p v-if="v.note" class="text-muted-foreground">{{ v.note }}</p>
                  <p v-if="!busy(v)" class="mt-1 flex gap-3">
                    <a v-if="v.video" :href="`${apiBase}/api/videos/${v.id}/video.mp4`" download class="underline underline-offset-2">Download</a>
                    <a v-if="v.video" :href="`${apiBase}/api/videos/${v.id}/sheet.jpg`" target="_blank" class="underline underline-offset-2">Scenes</a>
                    <button type="button" class="underline underline-offset-2" @click="remakeStoryVideo(v)">Make again</button>
                    <button type="button" class="underline underline-offset-2" :class="confirming === `v-${v.id}` ? 'text-destructive' : ''" @click="removeStoryVideo(v)">{{ confirming === `v-${v.id}` ? 'Really remove?' : 'Remove' }}</button>
                  </p>
                </div>
              </li>
              <li v-if="!videos.length" class="rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">No story video yet.</li>
            </ul>
          </div>

          <div>
            <p class="text-sm font-medium">Editions on video</p>
            <p class="text-xs text-muted-foreground">The cover, the words as they are spoken, the sound as a waveform. Press the camera beside an edition to make one.</p>
            <p v-if="note.video" class="mt-2 text-xs text-muted-foreground" role="status">{{ note.video }}</p>
            <div v-if="withVideo.length" class="mt-3 flex flex-col gap-3">
              <figure v-for="e in withVideo.slice(0, 2)" :key="e.id">
                <video controls preload="none" :poster="art(e.show)" class="aspect-video w-full rounded-lg border bg-black" :src="`${apiBase}/api/radio/archive/${e.id}/video.mp4`" />
                <figcaption class="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span class="truncate">{{ e.show_name }} · {{ day(e.date) }}</span>
                  <a :href="`${apiBase}/api/radio/archive/${e.id}/video.mp4`" download class="shrink-0 underline underline-offset-2">Download</a>
                </figcaption>
              </figure>
            </div>
            <p v-else class="mt-3 rounded-lg border border-dashed p-4 text-center text-xs text-muted-foreground">No edition has a video yet.</p>
          </div>

          <div>
            <div class="flex items-baseline justify-between gap-2">
              <p class="text-sm font-medium">Covers</p>
              <button type="button" class="text-xs text-primary hover:underline" @click="drawCovers()">Draw the missing ones</button>
            </div>
            <p class="text-xs text-muted-foreground">Drawn by the image model. Press one to have it drawn again.</p>
            <div class="mt-2 grid grid-cols-7 gap-1.5">
              <button v-for="c in covers" :key="c.key" type="button" :title="`Redraw ${c.key.replace('_', ' ')}`" class="overflow-hidden rounded border hover:border-primary" @click="drawCovers(c.key)">
                <img v-if="c.drawn" :src="`${art(c.key)}?v=${stamp}`" :alt="c.key" class="aspect-square w-full object-cover" loading="lazy">
                <span v-else class="grid aspect-square place-items-center text-muted-foreground"><Icon name="lucide:image-off" class="h-3.5 w-3.5" /></span>
              </button>
            </div>
          </div>

        </div>
      </section>
    </div>

    <!-- ============================ INFERENCE ============================ -->
    <section class="mt-4 rounded-xl border bg-card">
      <header class="flex flex-wrap items-center gap-2 border-b px-4 py-3">
        <Icon name="lucide:activity" class="h-4 w-4 text-primary" />
        <h2 class="text-sm font-semibold">The models</h2>
        <span class="text-xs text-muted-foreground">
          <template v-if="checks?.at">{{ checks.working }} of {{ checks.of }} working · checked {{ ago(checks.at) }}</template>
          <template v-else-if="checks?.running">Checking now</template>
          <template v-else>Not checked yet</template>
        </span>
        <Button size="sm" variant="outline" class="ml-auto" :disabled="checking" @click="runChecks">{{ checking ? 'Checking…' : 'Check them all' }}</Button>
      </header>
      <p class="px-4 pt-3 text-xs text-muted-foreground">One small real request to each: write a sentence, read a picture, say a line and hear it back, draw, play, fetch a page, render a clip, ask the agent. About a minute.</p>
      <ul class="grid gap-x-6 gap-y-2 p-4 text-xs sm:grid-cols-2 xl:grid-cols-3">
        <li v-for="c in checks?.checks || []" :key="c.name" class="flex gap-2">
          <Icon :name="c.ok === null ? 'lucide:circle-dashed' : c.ok ? 'lucide:circle-check' : (c.optional ? 'lucide:circle-minus' : 'lucide:circle-x')" class="mt-0.5 h-4 w-4 shrink-0" :class="c.ok ? 'text-primary' : c.ok === false && !c.optional ? 'text-destructive' : 'text-muted-foreground'" />
          <span class="min-w-0">
            <span class="font-medium capitalize">{{ c.name }}</span>
            <span class="text-muted-foreground"> · {{ c.purpose }}</span>
            <span class="block break-words text-muted-foreground">{{ c.ok === null ? '' : c.ok ? 'Working' : 'Not working' }}<template v-if="c.seconds !== null"> in {{ c.seconds }}s</template><template v-if="c.detail">: {{ c.detail }}</template></span>
          </span>
        </li>
      </ul>
    </section>

    <!-- A story video, played -->
    <div v-if="watching" class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" role="dialog" aria-modal="true" :aria-label="watching.title" @click.self="watching = null" @keydown.esc="watching = null">
      <div class="w-full max-w-4xl">
        <video controls autoplay class="aspect-video w-full rounded-lg bg-black" :src="`${apiBase}/api/videos/${watching.id}/video.mp4?v=${watching.updated_at}`" />
        <div class="mt-2 flex items-center justify-between gap-3 text-sm text-neutral-200">
          <span class="truncate">{{ watching.title }}</span>
          <button type="button" class="rounded bg-neutral-700 px-3 py-1 text-neutral-100" autofocus @click="watching = null">Close</button>
        </div>
      </div>
    </div>

    <!-- The digest as the e-reader shows it -->
    <div v-if="preview" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" :aria-label="`Preview of ${preview.edition_name || preview.slug}`" @click.self="preview = null" @keydown.esc="preview = null">
      <div class="flex h-full max-h-[900px] w-full max-w-[640px] flex-col overflow-hidden rounded-2xl border-8 border-neutral-800 bg-[#f4f1ea] shadow-2xl">
        <div class="flex items-center justify-between gap-3 bg-neutral-800 px-3 pb-2 text-xs text-neutral-300">
          <span class="truncate">{{ preview.edition_name || preview.slug }} · as the e-reader shows it</span>
          <span class="flex shrink-0 items-center gap-3">
            <a :href="`${apiBase}/api/digests/${preview.slug}.html`" target="_blank" class="underline underline-offset-2">Open</a>
            <a :href="`${apiBase}/api/digests/${preview.slug}.html`" download class="underline underline-offset-2">Download</a>
            <button type="button" class="rounded bg-neutral-700 px-2 py-0.5 text-neutral-100" autofocus @click="preview = null">Close</button>
          </span>
        </div>
        <iframe :src="`${apiBase}/api/digests/${preview.slug}.html`" class="min-h-0 w-full flex-1 bg-[#f4f1ea] grayscale" title="Digest preview" />
      </div>
    </div>
  </PageShell>
</template>
