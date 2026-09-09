<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '#components'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import PageShell from '~/components/kit/PageShell.vue'
import PageHeader from '~/components/kit/PageHeader.vue'
import InfoHint from '~/components/kit/InfoHint.vue'

/**
 * The title card every episode opens on, in each aspect ratio we produce.
 *
 * The frames are the live HTML the sidecar renders, so a CSS change shows
 * here on reload; "Render PNG" asks the sidecar for the exact pixels a
 * video would get.
 */
useHead({ title: 'hn.fm · Title cards' })

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const FORMATS: { key: string, w: number, h: number, label: string }[] = [
  { key: '16:9', w: 1280, h: 720, label: 'Landscape · 1280×720' },
  { key: '1:1', w: 1024, h: 1024, label: 'Square · 1024×1024' },
  { key: '9:16', w: 720, h: 1280, label: 'Portrait · 720×1280' },
]

const route = useRoute()
const itemId = ref<string>(String(route.query.item_id || ''))
const run = ref<string>(String(route.query.run || ''))
const seg = ref<string>(String(route.query.seg || ''))
const tagline = ref<string>('')
const nonce = ref(0)
const rendered = ref<Record<string, string>>({})
const rendering = ref<string | null>(null)
const message = ref('')

interface Context {
  tagline: string
  credits: { vendor: string, name: string, products: string[] }[]
}
const context = ref<Context | null>(null)

const params = computed(() => {
  const p = new URLSearchParams()
  if (itemId.value) p.set('item_id', itemId.value)
  if (run.value) p.set('run', run.value)
  if (seg.value) p.set('seg', seg.value)
  if (tagline.value) p.set('tagline', tagline.value)
  return p
})

function htmlSrc(fmt: string) {
  const p = new URLSearchParams(params.value)
  p.set('format', fmt)
  p.set('_', String(nonce.value))
  return `${apiBase}/api/title-card.html?${p}`
}

async function loadContext() {
  try {
    const p = new URLSearchParams()
    if (itemId.value) p.set('item_id', itemId.value)
    if (run.value) p.set('run', run.value)
    if (seg.value) p.set('seg', seg.value)
    context.value = await $fetch<Context>(`${apiBase}/api/title-card/context?${p}`)
  } catch {
    context.value = null
  }
}
watch([itemId, run, seg], loadContext, { immediate: true })

function refresh() {
  nonce.value++
  rendered.value = {}
  loadContext()
}

async function render(fmt: string) {
  rendering.value = fmt
  message.value = `Rendering ${fmt} through the sidecar…`
  try {
    const p = new URLSearchParams(params.value)
    p.set('format', fmt)
    p.set('force', 'true')
    const blob = await $fetch<Blob>(`${apiBase}/api/title-card.png?${p}`, { responseType: 'blob' })
    rendered.value = { ...rendered.value, [fmt]: URL.createObjectURL(blob) }
    message.value = `Rendered ${fmt}.`
  } catch (e: unknown) {
    message.value = `Render failed: ${e}`
  } finally {
    rendering.value = null
  }
}

/** Scale each frame so the three fit side by side at a common height. */
const PREVIEW_H = 360
const scale = (f: { w: number, h: number }) => PREVIEW_H / f.h
</script>

<template>
  <PageShell>
    <PageHeader
      title="Title cards"
      subtitle="The four seconds every episode opens on, in each aspect ratio we make."
      hint="One HTML card, laid out per format and rendered to a PNG by the Chromium sidecar at the exact frame size. The credits come from the audit trail — which models actually made the episode — and the tagline from its Story Brief. Drop an SVG at video/media/logos/<vendor>.svg to replace a monogram tile with a real logo."
    >
      <template #actions>
        <Button variant="outline" size="sm" @click="refresh">
          <Icon name="lucide:refresh-cw" class="mr-1.5 h-3.5 w-3.5" />
          Reload
        </Button>
      </template>
      <template #below>
        <div class="mt-3 flex flex-wrap items-end gap-3">
          <div class="space-y-1">
            <label class="text-xs font-medium" for="tc-item">Story</label>
            <Input id="tc-item" v-model="itemId" placeholder="item id" class="h-8 w-32 text-xs" />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-medium" for="tc-run">Run</label>
            <Input id="tc-run" v-model="run" placeholder="1" class="h-8 w-16 text-xs" />
          </div>
          <div class="space-y-1">
            <label class="text-xs font-medium" for="tc-seg">Segment</label>
            <Input id="tc-seg" v-model="seg" placeholder="1" class="h-8 w-16 text-xs" />
          </div>
          <div class="min-w-[18rem] flex-1 space-y-1">
            <label class="flex items-center gap-1 text-xs font-medium" for="tc-tag">
              Tagline
              <InfoHint text="Leave empty to use the story's own: the brief's thesis, else the run's short description." />
            </label>
            <Input id="tc-tag" v-model="tagline" :placeholder="context?.tagline || 'Hacker News, watchable.'" class="h-8 text-xs" @keyup.enter="refresh" />
          </div>
          <Button size="sm" class="h-8" @click="refresh">Apply</Button>
        </div>
        <p v-if="context?.credits?.length" class="mt-2 text-xs text-muted-foreground">
          Credits:
          <span v-for="(c, i) in context.credits" :key="c.vendor">
            <span class="font-medium text-foreground">{{ c.name }}</span> ({{ c.products.join(', ') }}){{ i < context.credits.length - 1 ? ' · ' : '' }}
          </span>
        </p>
        <p v-if="message" class="mt-1 text-xs text-muted-foreground">{{ message }}</p>
      </template>
    </PageHeader>

    <div class="flex flex-wrap items-start gap-6">
      <section v-for="f in FORMATS" :key="f.key" class="space-y-2">
        <div class="flex items-center justify-between gap-3" :style="{ width: `${f.w * scale(f)}px` }">
          <div>
            <p class="text-sm font-medium">{{ f.key }}</p>
            <p class="text-xs text-muted-foreground">{{ f.label }}</p>
          </div>
          <Button size="sm" variant="outline" :disabled="rendering !== null" @click="render(f.key)">
            <Icon name="lucide:image-down" class="mr-1.5 h-3.5 w-3.5" />
            {{ rendering === f.key ? 'Rendering…' : 'Render PNG' }}
          </Button>
        </div>
        <div
          class="overflow-hidden rounded-lg border bg-black shadow-sm"
          :style="{ width: `${f.w * scale(f)}px`, height: `${f.h * scale(f)}px` }"
        >
          <img
            v-if="rendered[f.key]"
            :src="rendered[f.key]"
            :alt="`Rendered ${f.key} title card`"
            class="block h-full w-full"
          >
          <iframe
            v-else
            :src="htmlSrc(f.key)"
            :title="`Title card ${f.key}`"
            :width="f.w"
            :height="f.h"
            class="block origin-top-left border-0"
            :style="{ transform: `scale(${scale(f)})`, width: `${f.w}px`, height: `${f.h}px` }"
            loading="lazy"
          />
        </div>
        <p class="text-[11px] text-muted-foreground">
          {{ rendered[f.key] ? 'Rendered PNG, exactly what the video gets.' : 'Live HTML, scaled to fit.' }}
        </p>
      </section>
    </div>
  </PageShell>
</template>
