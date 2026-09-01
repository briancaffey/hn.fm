<script setup lang="ts">
import { Card, CardContent, CardHeader, CardTitle } from '~/components/ui/card'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'

interface DigestFile {
  slug: string
  formats: string[]
  bytes: number
  modified: string
}

interface DigestsResponse {
  digests: DigestFile[]
  delivery_ready: boolean
  delivery: string
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const { data, pending, refresh } = await useAsyncData<DigestsResponse>('digests', () =>
  $fetch(`${apiBase}/api/digests`)
)

const storyCount = ref(5)
const sendAfterBuild = ref(false)
const busy = ref(false)
const message = ref('')

// Building runs triage first, which is several LLM calls per unscored story —
// slow enough that a spinner alone would look stuck without saying why.
const buildDigest = async () => {
  busy.value = true
  message.value = 'Scoring stories and rendering… this can take a few minutes.'
  try {
    await $fetch(`${apiBase}/api/digests`, {
      method: 'POST',
      body: { limit: storyCount.value, send: sendAfterBuild.value, score_first: true },
    })
    message.value = sendAfterBuild.value
      ? 'Queued. It will be emailed to your Kindle when it finishes.'
      : 'Queued. Refresh in a moment to see it.'
  } catch (e: unknown) {
    message.value = `Failed to queue: ${e}`
  } finally {
    busy.value = false
  }
}

const sendExisting = async (slug: string) => {
  busy.value = true
  message.value = ''
  try {
    const res = await $fetch<{ status: string, file: string }>(
      `${apiBase}/api/digests/${slug}/send`, { method: 'POST' })
    message.value = `Sent ${res.file} to your Kindle.`
  } catch (e: unknown) {
    message.value = `Send failed: ${e}`
  } finally {
    busy.value = false
  }
}

const prettyBytes = (n: number) => n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`
const prettyDate = (iso: string) => new Date(iso).toLocaleString()
</script>

<template>
  <div class="container mx-auto p-6 space-y-6">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold">Kindle Digests</h1>
        <p class="text-muted-foreground mt-1">
          Top-ranked stories, typeset to read. Built from Story Briefs, so a digest
          costs no LLM calls of its own.
        </p>
      </div>
      <Button variant="outline" :disabled="pending" @click="refresh()">Refresh</Button>
    </div>

    <!-- Delivery state is worth surfacing even when nothing is wrong: a
         misconfigured sender fails silently at Amazon, with no bounce. -->
    <Card>
      <CardHeader><CardTitle class="text-base">Delivery</CardTitle></CardHeader>
      <CardContent class="flex items-center gap-3">
        <Badge :variant="data?.delivery_ready ? 'default' : 'destructive'">
          {{ data?.delivery_ready ? 'Configured' : 'Not configured' }}
        </Badge>
        <span class="text-sm text-muted-foreground font-mono">{{ data?.delivery }}</span>
      </CardContent>
    </Card>

    <Card>
      <CardHeader><CardTitle class="text-base">Build a digest</CardTitle></CardHeader>
      <CardContent class="space-y-4">
        <div class="flex flex-wrap items-end gap-4">
          <div class="space-y-1">
            <label class="text-sm font-medium">Stories</label>
            <Input v-model.number="storyCount" type="number" min="1" max="20" class="w-24" />
          </div>
          <label class="flex items-center gap-2 text-sm pb-2">
            <input v-model="sendAfterBuild" type="checkbox" class="h-4 w-4">
            Email to Kindle when done
          </label>
          <Button :disabled="busy || !data" class="mb-1" @click="buildDigest">
            {{ busy ? 'Working…' : 'Build digest' }}
          </Button>
        </div>
        <p v-if="message" class="text-sm text-muted-foreground">{{ message }}</p>
      </CardContent>
    </Card>

    <Card>
      <CardHeader><CardTitle class="text-base">Rendered digests</CardTitle></CardHeader>
      <CardContent>
        <p v-if="!data?.digests?.length" class="text-sm text-muted-foreground">
          None yet. Build one above — note that only stories with a Story Brief are
          included, so run triage if a digest comes out short.
        </p>
        <div v-else class="divide-y">
          <div
            v-for="d in data.digests"
            :key="d.slug"
            class="flex flex-wrap items-center justify-between gap-3 py-3"
          >
            <div>
              <div class="font-medium">{{ d.slug }}</div>
              <div class="text-xs text-muted-foreground">
                {{ prettyDate(d.modified) }} · {{ prettyBytes(d.bytes) }}
              </div>
            </div>
            <div class="flex items-center gap-2">
              <a
                v-for="f in d.formats"
                :key="f"
                :href="`${apiBase}/api/digests/${d.slug}.${f}`"
                target="_blank"
                class="text-sm underline underline-offset-4"
              >{{ f.toUpperCase() }}</a>
              <Button
                size="sm"
                variant="outline"
                :disabled="busy || !data.delivery_ready"
                @click="sendExisting(d.slug)"
              >Send to Kindle</Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  </div>
</template>
