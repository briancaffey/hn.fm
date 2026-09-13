<script setup lang="ts">
/**
 * A record: the unit of content on the set (plans/21). A vinyl disc with a
 * coloured label, an icon for what it is, and its title. Everything the
 * station plays is one of these — an episode, a station ID, a coming-up
 * line, a time check, a music bed — and they travel the belt, sit on the
 * decks and stack in the library.
 */
import { computed } from 'vue'
import { Html } from '@tresjs/cientos'
import { Icon } from '#components'

const props = withDefaults(defineProps<{
  kind: string
  title?: string | null
  host?: string | null
  /** Disc radius in scene units. */
  radius?: number
  /** Whether the label stands up (readable from the camera) or lies flat. */
  standing?: boolean
  spinning?: boolean
  showLabel?: boolean
  glow?: number
}>(), { title: '', host: null, radius: 0.55, standing: false, spinning: false, showLabel: true, glow: 0.25 })

const COLOR: Record<string, string> = {
  episode: '#ff6a00', music: '#5eead4', station_id: '#f4efe6', coming_up: '#f5b642', time_check: '#b39ddb', brief: '#ff9f43', feature: '#ff4d6d', bit: '#f78fb3',
}
const ICON: Record<string, string> = {
  episode: 'lucide:newspaper', music: 'lucide:music', station_id: 'lucide:radio-tower',
  coming_up: 'lucide:signpost', time_check: 'lucide:clock', brief: 'lucide:zap', feature: 'lucide:book-open', bit: 'lucide:sparkles',
}
const LABEL: Record<string, string> = {
  episode: 'Episode', music: 'Music bed', station_id: 'Station ID', coming_up: 'Coming up', time_check: 'Time check', brief: 'Brief', feature: 'Feature', bit: 'Bit',
}
const color = computed(() => COLOR[props.kind] || '#6b655b')
const icon = computed(() => ICON[props.kind] || 'lucide:disc')
const text = computed(() => (props.title || LABEL[props.kind] || props.kind).slice(0, 48))
</script>

<template>
  <TresGroup :rotation="standing ? [Math.PI / 2, 0, 0] : [0, 0, 0]">
    <!-- the vinyl -->
    <TresMesh cast-shadow>
      <TresCylinderGeometry :args="[radius, radius, 0.05, 40]" />
      <TresMeshStandardMaterial color="#1a1714" :roughness="0.35" :metalness="0.15" />
    </TresMesh>
    <!-- grooves: two faint rings -->
    <TresMesh v-for="r in [0.82, 0.62]" :key="'g' + r" :position="[0, 0.028, 0]" :rotation="[-Math.PI / 2, 0, 0]">
      <TresRingGeometry :args="[radius * r - 0.006, radius * r, 40]" />
      <TresMeshBasicMaterial color="#2b2622" />
    </TresMesh>
    <!-- the label -->
    <TresMesh :position="[0, 0.03, 0]">
      <TresCylinderGeometry :args="[radius * 0.42, radius * 0.42, 0.012, 32]" />
      <TresMeshStandardMaterial :color="color" :emissive="color" :emissive-intensity="glow" :roughness="0.6" />
    </TresMesh>
    <TresMesh :position="[0, 0.045, 0]">
      <TresCylinderGeometry :args="[0.03, 0.03, 0.02, 12]" />
      <TresMeshStandardMaterial color="#1a1714" />
    </TresMesh>
    <Html v-if="showLabel" :position="[0, 0.12, 0]" center>
      <div class="rec" :style="{ '--c': color }">
        <Icon :name="icon" class="ico" />
        <span class="t">{{ text }}</span>
        <span v-if="host" class="h">{{ host }}</span>
      </div>
    </Html>
  </TresGroup>
</template>

<style scoped>
.rec { display: inline-flex; align-items: center; gap: 6px; max-width: 220px; padding: 3px 8px 3px 5px; border-radius: 999px;
       background: rgba(20, 17, 14, .85); border: 1px solid var(--c); color: #f4efe6; font: 500 11px/1.2 "Archivo", sans-serif;
       white-space: nowrap; pointer-events: none; box-shadow: 0 2px 10px rgba(0,0,0,.5); }
.rec .ico { width: 13px; height: 13px; color: var(--c); flex: none; }
.rec .t { overflow: hidden; text-overflow: ellipsis; }
.rec .h { font-family: "IBM Plex Mono", monospace; font-size: 9px; color: #a69c8e; }
</style>
