<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

/**
 * The public face of HNFM (plans/20). This is the only page a public host
 * exposes: a player, what is on, what was on. No controls, no dashboard.
 */
definePageMeta({ layout: false })
useHead({ title: 'HNFM · on air' })

interface Event { id: number, at: string, kind: string, title: string | null }
interface Status { enabled: boolean, now: Event | null, icecast: { up: boolean, mounts?: { listeners: number }[] } }

const config = useRuntimeConfig()
const apiBase = config.public.apiBase
const status = ref<Status | null>(null)
const history = ref<Event[]>([])

const streamUrl = computed(() => {
  try {
    const u = new URL(apiBase)
    if (u.hostname === 'localhost' || u.hostname === '127.0.0.1') return 'http://localhost:8010/hnfm.mp3'
    return `${u.origin}/radio/hnfm.mp3`
  } catch { return '/radio/hnfm.mp3' }
})

async function load() {
  try {
    status.value = await $fetch<Status>(`${apiBase}/api/radio/status`)
    if (status.value?.enabled) {
      const h = await $fetch<{ events: Event[] }>(`${apiBase}/api/radio/history?hours=2`)
      history.value = [...h.events].reverse().filter(e => e.kind === 'episode').slice(0, 8)
    }
  } catch { /* the page still shows the player */ }
}
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => { load(); timer = setInterval(load, 20000) })
onUnmounted(() => { if (timer) clearInterval(timer) })
const listeners = computed(() => (status.value?.icecast?.mounts || []).reduce((n, m) => n + (m.listeners || 0), 0))
const when = (iso: string) => new Date(iso.endsWith('Z') ? iso : iso + 'Z').toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
</script>

<template>
  <main class="min-h-screen bg-background text-foreground">
    <div class="mx-auto flex max-w-xl flex-col gap-8 px-6 py-14">
      <header class="flex flex-col gap-3">
        <div class="flex gap-0.5" aria-hidden="true">
          <span class="h-5 w-5" style="background:#6f3410" /><span class="h-5 w-5" style="background:#8c4210" /><span class="h-5 w-5" style="background:#b5540c" /><span class="h-5 w-5" style="background:#d96208" /><span class="h-5 w-5" style="background:#ff6a00" />
        </div>
        <h1 class="text-2xl font-black tracking-tight">HNFM</h1>
        <p class="text-sm text-muted-foreground">Hacker News, on air. Short narrated episodes about what people are building, with generated music between them.</p>
      </header>

      <section class="rounded-xl border bg-card p-5">
        <div class="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
          <span class="inline-block h-2 w-2 rounded-full" :class="status?.icecast?.up ? 'bg-destructive' : 'bg-muted-foreground'" />
          {{ status?.icecast?.up ? 'On air' : 'Off air' }}
          <span v-if="listeners" class="ml-auto normal-case tracking-normal">{{ listeners }} listening</span>
        </div>
        <audio controls preload="none" :src="streamUrl" class="mt-4 w-full" />
        <div v-if="status?.now" class="mt-4">
          <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Now playing</p>
          <p class="mt-1 text-lg font-semibold leading-snug">{{ status.now.title }}</p>
        </div>
      </section>

      <section v-if="history.length">
        <p class="text-[11px] uppercase tracking-wider text-muted-foreground">Recently on</p>
        <ol class="mt-2 divide-y text-sm">
          <li v-for="e in history" :key="e.id" class="flex gap-3 py-2">
            <span class="w-16 shrink-0 font-mono text-xs text-muted-foreground">{{ when(e.at) }}</span>
            <span class="min-w-0 flex-1 truncate">{{ e.title }}</span>
          </li>
        </ol>
      </section>

      <footer class="text-xs text-muted-foreground">
        Stream: <span class="font-mono">{{ streamUrl }}</span>. Paste it into any player.
      </footer>
    </div>
  </main>
</template>
