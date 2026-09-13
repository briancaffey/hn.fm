<script setup lang="ts">
/**
 * The set (plans/21). Every component of the station is a thing on a lit
 * night floor, and every piece of content is a record:
 *
 *   the Press      the producer stamps the block out as records, onto the belt
 *   the Belt       carries the block's records to the DJ booth, in order
 *   the DJ booth   two decks; the arm takes the next record off the belt
 *   the Jukebox    lights up with the prompt while a music bed is generated,
 *                  and drops the finished record into the Library
 *   the Library    stacks of records and cassettes, a rack of episode cards
 *   the Mic        lit while a host is speaking — station IDs, coming-ups
 *   the Clock      lit during a time check
 *   the Switchboard, the Transmitter, the Manager drone — as before
 *
 * Per-frame motion mutates three.js objects through refs, never Vue
 * reactivity; the template re-renders only when the station's state does.
 */
import { computed, shallowRef, watch } from 'vue'
import { useLoop } from '@tresjs/core'
import { Html, OrbitControls } from '@tresjs/cientos'
import type { Group, Mesh } from 'three'
import StudioRecord from './StudioRecord.vue'

export interface Bubble { component: string, text: string, at: number }
export interface SheetItem { kind: string, episode?: string | null, host?: string | null, line?: string | null, music_style?: string | null, title?: string | null }

const props = defineProps<{
  onAir: boolean
  nowKind: string | null
  nowTitle: string | null
  nowHost: string | null
  listeners: number
  episodes: number
  stationIds: number
  beds: number
  sheetItems: SheetItem[]
  sheetCursor: number
  thinking: boolean
  jukeboxPrompt: string | null
  bubbles: Bubble[]
  trackChanges: number
  plans: number
  bedsPressed: number
  packets: { id: number, from: string, to: string, color: string }[]
  monitorRounds: number
}>()

const C = {
  floor: '#25211c', wall: '#2c2722', metal: '#3b3733', metalLight: '#514c46', belt: '#1c1916',
  cream: '#e8e0d0', orange: '#ff6a00', cyan: '#5eead4', amber: '#f5b642',
  lavender: '#b39ddb', white: '#f4efe6', red: '#d7263d', yellow: '#e9d829',
  duck: '#f2c14e', dim: '#6b655b', juke: '#7a2e12',
}

// Where things live. The belt runs from the press (left, back) to the DJ
// booth (centre, front).
const ANCHOR: Record<string, [number, number, number]> = {
  library: [-8.4, 1.4, 1.0],
  jukebox: [-8.2, 1.6, -3.0],
  producer: [-4.2, 1.4, -4.0],
  hub: [2.8, 1.2, -2.2],
  dj: [0.6, 1.3, 3.6],
  transmitter: [8.2, 2.6, -1.6],
  monitor: [4.5, 3.4, 2.0],
  mic: [3.6, 1.2, 3.8],
  clock: [-1.0, 3.6, -6.3],
}
const BELT = { x0: -3.0, x1: -0.9, z0: -3.6, z1: 2.4, y: 0.62 }   // press end → booth end
const BELT_LEN = Math.hypot(BELT.x1 - BELT.x0, BELT.z1 - BELT.z0)
const BELT_YAW = Math.atan2(BELT.x1 - BELT.x0, BELT.z1 - BELT.z0)
const SLOTS = 7                                                   // records visible on the belt

// --- refs the loop mutates -------------------------------------------------
const deckA = shallowRef<Group | null>(null)
const tonearm = shallowRef<Group | null>(null)
const eye = shallowRef<Mesh | null>(null)
const drone = shallowRef<Group | null>(null)
const jukeArch = shallowRef<Mesh | null>(null)
const pressHead = shallowRef<Mesh | null>(null)
const popped = shallowRef<Group | null>(null)
const ringMeshes: Mesh[] = []
const vuMeshes: Mesh[] = []
const packetMeshes: Mesh[] = []
const beltRecords = new Map<number, Group>()
const rollers: Mesh[] = []
const setRing = (i: number) => (el: unknown) => { if (el) ringMeshes[i] = el as Mesh }
const setVu = (i: number) => (el: unknown) => { if (el) vuMeshes[i] = el as Mesh }
const setPacket = (i: number) => (el: unknown) => { if (el) packetMeshes[i] = el as Mesh }
const setRoller = (i: number) => (el: unknown) => { if (el) rollers[i] = el as Mesh }
const setBeltRecord = (idx: number) => (el: unknown) => { if (el) beltRecords.set(idx, el as Group); else beltRecords.delete(idx) }
const POOL = 12

const anim = {
  rings: [0, 0.33, 0.66],
  vu: [0.2, 0.4, 0.3, 0.5, 0.35, 0.25, 0.45, 0.3],
  swapT: 1, swapping: false, pressT: 1, droneUntil: 0, popT: 1,
  packets: [] as { id: number, from: number[], to: number[], t: number, color: string }[],
}
watch(() => props.trackChanges, () => { anim.swapT = 0; anim.swapping = true })
watch(() => props.plans, () => { anim.pressT = 0 })
watch(() => props.bedsPressed, () => { anim.popT = 0 })
watch(() => props.monitorRounds, () => { anim.droneUntil = performance.now() + 3500 })
watch(() => props.packets, (list) => {
  for (const p of list) {
    if (anim.packets.some(l => l.id === p.id)) continue
    anim.packets.push({ id: p.id, from: ANCHOR[p.from] || ANCHOR.hub, to: ANCHOR[p.to] || ANCHOR.hub, t: 0, color: p.color })
  }
}, { deep: true })

// The block's upcoming records, from the cursor on. Keyed by their index in
// the sheet so a record keeps its identity as it moves down the belt.
const upcoming = computed(() =>
  props.sheetItems.map((it, i) => ({ ...it, idx: i })).slice(props.sheetCursor, props.sheetCursor + SLOTS))
// Slot 0 is nearest the booth; the last slot sits under the press.
const slotPos = (slot: number): [number, number, number] => {
  const t = 1 - (slot + 0.5) / SLOTS
  return [BELT.x0 + (BELT.x1 - BELT.x0) * t, BELT.y + 0.05, BELT.z0 + (BELT.z1 - BELT.z0) * t]
}
const recordTitle = (it: SheetItem) =>
  it.kind === 'episode' ? (it.title || it.episode || '') : (it.line || it.music_style || '')

const { onBeforeRender } = useLoop()
onBeforeRender(({ delta, elapsed }) => {
  if (deckA.value && props.onAir) deckA.value.rotation.y += delta * 2.0
  if (anim.swapping) {
    anim.swapT = Math.min(1, anim.swapT + delta / 1.6)
    if (tonearm.value) {
      const s = Math.sin(anim.swapT * Math.PI)
      tonearm.value.position.y = 0.55 + s * 0.5
      tonearm.value.rotation.y = -0.5 + s * 1.3
    }
    if (anim.swapT >= 1) anim.swapping = false
  }
  if (eye.value) (eye.value.material as { emissiveIntensity: number }).emissiveIntensity = props.thinking ? 1.2 + Math.sin(elapsed * 8) * 0.8 : 0.35
  if (jukeArch.value) (jukeArch.value.material as { emissiveIntensity: number }).emissiveIntensity = props.jukeboxPrompt ? 1.0 + Math.sin(elapsed * 6) * 0.6 : 0.25
  anim.pressT = Math.min(1, anim.pressT + delta / 0.9)
  if (pressHead.value) pressHead.value.position.y = 1.9 - Math.sin(anim.pressT * Math.PI) * 0.55
  anim.popT = Math.min(1, anim.popT + delta / 1.4)
  if (popped.value) { popped.value.position.z = 0.8 + anim.popT * 0.6; popped.value.position.y = 0.3 + Math.sin(anim.popT * Math.PI) * 0.3 }
  for (let i = 0; i < anim.rings.length; i++) {
    if (props.onAir) anim.rings[i] = (anim.rings[i] + delta * 0.35) % 1
    const m = ringMeshes[i]
    if (m) { const r = anim.rings[i]; m.scale.set(0.3 + r * 3.4, 0.3 + r * 3.4, 1); (m.material as { opacity: number }).opacity = props.onAir ? (1 - r) * 0.7 : 0 }
  }
  for (let i = 0; i < anim.vu.length; i++) {
    anim.vu[i] = props.onAir ? 0.15 + Math.abs(Math.sin(elapsed * (2.1 + i * 0.37) + i)) * 0.85 : Math.max(0.05, anim.vu[i] - delta)
    const m = vuMeshes[i]
    if (m) { m.scale.y = anim.vu[i]; m.position.y = 0.95 + anim.vu[i] * 0.35 }
  }
  // The belt rolls while on air; the records glide to their slots.
  for (const r of rollers) if (r && props.onAir) r.rotation.y += delta * 3
  const items = upcoming.value
  for (let slot = 0; slot < items.length; slot++) {
    const g = beltRecords.get(items[slot].idx)
    if (!g) continue
    const [tx, ty, tz] = slotPos(slot)
    g.position.x += (tx - g.position.x) * Math.min(1, delta * 3)
    g.position.y += (ty - g.position.y) * Math.min(1, delta * 3)
    g.position.z += (tz - g.position.z) * Math.min(1, delta * 3)
    if (props.onAir) g.rotation.y += delta * 0.4
  }
  if (drone.value) {
    const parked = performance.now() < anim.droneUntil
    const target = parked ? [ANCHOR.producer[0] + 1.6, 3.4, ANCHOR.producer[2] + 0.8]
      : [Math.cos(elapsed * 0.22) * 7.5, 3.6 + Math.sin(elapsed * 1.3) * 0.15, Math.sin(elapsed * 0.22) * 5]
    drone.value.position.x += (target[0] - drone.value.position.x) * Math.min(1, delta * 1.5)
    drone.value.position.y += (target[1] - drone.value.position.y) * Math.min(1, delta * 2)
    drone.value.position.z += (target[2] - drone.value.position.z) * Math.min(1, delta * 1.5)
    drone.value.rotation.y = elapsed * 0.6
  }
  for (const p of anim.packets) p.t = Math.min(1, p.t + delta / 1.1)
  anim.packets = anim.packets.filter(p => p.t < 1)
  for (let i = 0; i < POOL; i++) {
    const m = packetMeshes[i]
    if (!m) continue
    const p = anim.packets[i]
    m.visible = !!p
    if (p) {
      const arc = Math.sin(p.t * Math.PI) * 1.0
      m.position.set(p.from[0] + (p.to[0] - p.from[0]) * p.t, p.from[1] + (p.to[1] - p.from[1]) * p.t + arc, p.from[2] + (p.to[2] - p.from[2]) * p.t)
      ;(m.material as { color: { set: (c: string) => void } }).color.set(p.color)
      ;(m.material as { emissive: { set: (c: string) => void } }).emissive.set(p.color)
    }
  }
})

function tube(a: [number, number, number], b: [number, number, number]) {
  const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2]
  const len = Math.hypot(dx, dy, dz)
  const mid: [number, number, number] = [a[0] + dx / 2, a[1] + dy / 2, a[2] + dz / 2]
  return { mid, len, rot: [Math.atan2(dz, Math.hypot(dx, dy)), 0, -Math.atan2(dx, dy)] as [number, number, number] }
}
const TUBES = computed(() => ['producer', 'dj', 'transmitter', 'library'].map(k => ({ key: k, ...tube([ANCHOR.hub[0], 0.5, ANCHOR.hub[2]], [ANCHOR[k][0], 0.5, ANCHOR[k][2]]) })))

const speaking = computed(() => ['station_id', 'coming_up', 'time_check'].includes(props.nowKind || ''))
const bubbleFor = (component: string) => {
  const b = [...props.bubbles].reverse().find(x => x.component === component)
  return b && performance.now() - b.at < 9000 ? b : null
}
const BUBBLE_AT: Record<string, string> = { dj: 'dj', director: 'hub', producer: 'producer', bank: 'jukebox', monitor: 'monitor' }
const stacks = (n: number, max: number) => Math.max(0, Math.min(max, n))
const rollerCount = 9
const JUKE_COLORS = [C.orange, C.cyan, C.amber, C.lavender, C.white]
</script>

<template>
  <TresPerspectiveCamera :position="[11, 10, 13]" :look-at="[0, 0.8, 0]" :fov="36" />
  <OrbitControls :target="[-0.5, 0.8, 0]" :min-distance="8" :max-distance="28" :max-polar-angle="1.35" :enable-pan="false" />

  <TresAmbientLight :intensity="0.9" color="#fff3e0" />
  <TresHemisphereLight :intensity="1.1" color="#cfd8ff" ground-color="#3a2a1a" />
  <TresDirectionalLight :position="[6, 12, 6]" :intensity="2.6" color="#fff1dc" cast-shadow />
  <TresPointLight :position="[0.6, 3.4, 3.6]" :intensity="props.onAir ? 18 : 4" :color="C.orange" :distance="9" />
  <TresPointLight :position="[8.2, 4, -1.6]" :intensity="props.onAir ? 10 : 2" :color="C.orange" :distance="7" />
  <TresPointLight :position="[-4.2, 3.6, -3.4]" :intensity="12" color="#ffe9c9" :distance="7" />
  <TresPointLight :position="[-8.2, 3.6, -1.0]" :intensity="props.jukeboxPrompt ? 16 : 8" :color="props.jukeboxPrompt ? C.cyan : '#ffe9c9'" :distance="7" />
  <TresPointLight :position="[2.8, 3.6, -2.2]" :intensity="8" color="#dfe8ff" :distance="6" />
  <TresPointLight :position="[3.6, 3.0, 3.8]" :intensity="speaking ? 12 : 1" :color="C.white" :distance="5" />

  <!-- floor, wall, ground marks -->
  <TresMesh :position="[0, -0.05, 0]" receive-shadow>
    <TresBoxGeometry :args="[24, 0.1, 15]" />
    <TresMeshStandardMaterial :color="C.floor" :roughness="0.95" />
  </TresMesh>
  <TresMesh :position="[0, 2.8, -7.55]">
    <TresBoxGeometry :args="[24, 5.6, 0.1]" />
    <TresMeshStandardMaterial :color="C.wall" :roughness="1" />
  </TresMesh>
  <TresMesh v-for="i in 30" :key="'px' + i" :position="[((i - 1) % 6) * 3.8 - 9.5, 0.011, Math.floor((i - 1) / 6) * 3.0 - 6]" :rotation="[-Math.PI / 2, 0, 0]">
    <TresPlaneGeometry :args="[0.3, 0.05]" />
    <TresMeshBasicMaterial color="#5a3212" />
  </TresMesh>
  <TresMesh v-for="i in 30" :key="'py' + i" :position="[((i - 1) % 6) * 3.8 - 9.5, 0.011, Math.floor((i - 1) / 6) * 3.0 - 6]" :rotation="[-Math.PI / 2, 0, Math.PI / 2]">
    <TresPlaneGeometry :args="[0.3, 0.05]" />
    <TresMeshBasicMaterial color="#5a3212" />
  </TresMesh>

  <!-- ===== The Clock, on the wall: lit during a time check ===== -->
  <TresGroup :position="[ANCHOR.clock[0], ANCHOR.clock[1], ANCHOR.clock[2]]">
    <TresMesh :rotation="[Math.PI / 2, 0, 0]">
      <TresCylinderGeometry :args="[0.9, 0.9, 0.12, 40]" />
      <TresMeshStandardMaterial :color="props.nowKind === 'time_check' ? C.lavender : '#3a342e'" :emissive="props.nowKind === 'time_check' ? C.lavender : '#000'" :emissive-intensity="0.6" />
    </TresMesh>
    <TresMesh :position="[0, 0, 0.08]" :rotation="[Math.PI / 2, 0, 0]">
      <TresCylinderGeometry :args="[0.78, 0.78, 0.02, 40]" />
      <TresMeshStandardMaterial :color="C.white" />
    </TresMesh>
    <TresMesh :position="[0, 0.25, 0.1]"><TresBoxGeometry :args="[0.06, 0.5, 0.02]" /><TresMeshBasicMaterial color="#17130e" /></TresMesh>
    <TresMesh :position="[0.2, 0.05, 0.1]" :rotation="[0, 0, -1.1]"><TresBoxGeometry :args="[0.05, 0.62, 0.02]" /><TresMeshBasicMaterial color="#17130e" /></TresMesh>
    <Html :position="[0, -1.15, 0.2]" center>
      <div class="lbl">The Clock <span>time checks</span></div>
    </Html>
  </TresGroup>

  <!-- ===== The Switchboard (hn.fm API) ===== -->
  <TresGroup :position="[ANCHOR.hub[0], 0, ANCHOR.hub[2]]">
    <TresMesh :position="[0, 0.6, 0]" cast-shadow>
      <TresCylinderGeometry :args="[1.2, 1.4, 1.2, 6]" />
      <TresMeshStandardMaterial :color="C.metal" :roughness="0.6" :metalness="0.4" />
    </TresMesh>
    <TresMesh :position="[0, 1.25, 0]">
      <TresCylinderGeometry :args="[0.6, 0.6, 0.1, 6]" />
      <TresMeshStandardMaterial :color="C.orange" :emissive="C.orange" :emissive-intensity="0.7" />
    </TresMesh>
    <TresMesh v-for="s in 6" :key="'lamp' + s" :position="[Math.cos(s) * 0.95, 1.15, Math.sin(s) * 0.95]">
      <TresSphereGeometry :args="[0.07, 10, 10]" />
      <TresMeshStandardMaterial :color="C.cyan" :emissive="C.cyan" :emissive-intensity="0.9" />
    </TresMesh>
    <Html :position="[0, 2.3, 0]" center><div class="lbl">Switchboard <span>hn.fm API</span></div></Html>
  </TresGroup>
  <TresMesh v-for="t in TUBES" :key="t.key" :position="t.mid" :rotation="t.rot">
    <TresCylinderGeometry :args="[0.06, 0.06, t.len, 8]" />
    <TresMeshStandardMaterial :color="C.metalLight" :roughness="0.4" :metalness="0.6" />
  </TresMesh>

  <!-- ===== The Press (the producer) ===== -->
  <TresGroup :position="[ANCHOR.producer[0], 0, ANCHOR.producer[2]]">
    <TresMesh :position="[0, 0.45, 0]" cast-shadow receive-shadow>
      <TresBoxGeometry :args="[3.6, 0.9, 2.0]" />
      <TresMeshStandardMaterial :color="C.metal" :roughness="0.7" />
    </TresMesh>
    <TresMesh v-for="s in [-1, 1]" :key="'pil' + s" :position="[1.0 + s * 0.6, 1.5, 0.2]">
      <TresCylinderGeometry :args="[0.07, 0.07, 1.4, 10]" />
      <TresMeshStandardMaterial :color="C.metalLight" :metalness="0.7" :roughness="0.3" />
    </TresMesh>
    <TresMesh ref="pressHead" :position="[1.0, 1.9, 0.2]" cast-shadow>
      <TresCylinderGeometry :args="[0.62, 0.62, 0.3, 32]" />
      <TresMeshStandardMaterial :color="C.cream" :roughness="0.5" :metalness="0.2" />
    </TresMesh>
    <TresMesh :position="[1.0, 0.95, 0.2]">
      <TresCylinderGeometry :args="[0.66, 0.66, 0.08, 32]" />
      <TresMeshStandardMaterial :color="C.orange" :emissive="C.orange" :emissive-intensity="props.thinking ? 0.9 : 0.2" />
    </TresMesh>
    <!-- the producer robot -->
    <TresGroup :position="[-0.9, 0, -1.5]">
      <TresMesh :position="[0, 1.0, 0]" cast-shadow>
        <TresBoxGeometry :args="[1.2, 1.5, 0.9]" />
        <TresMeshStandardMaterial :color="C.metalLight" :roughness="0.5" :metalness="0.3" />
      </TresMesh>
      <TresMesh ref="eye" :position="[0, 1.25, 0.47]">
        <TresSphereGeometry :args="[0.28, 24, 24]" />
        <TresMeshStandardMaterial :color="C.cyan" :emissive="C.cyan" :emissive-intensity="0.35" />
      </TresMesh>
      <TresMesh :position="[0, 2.0, 0]"><TresCylinderGeometry :args="[0.03, 0.03, 0.5, 8]" /><TresMeshStandardMaterial :color="C.cream" /></TresMesh>
      <TresMesh :position="[0, 2.28, 0]">
        <TresSphereGeometry :args="[0.08, 12, 12]" />
        <TresMeshStandardMaterial :color="props.thinking ? C.cyan : C.dim" :emissive="props.thinking ? C.cyan : '#000'" :emissive-intensity="1" />
      </TresMesh>
      <TresMesh v-for="s in [-1, 1]" :key="'arm' + s" :position="[s * 0.8, 0.9, 0.6]" :rotation="[0.4, 0, 0]">
        <TresCylinderGeometry :args="[0.08, 0.08, 1.1, 10]" />
        <TresMeshStandardMaterial :color="C.metalLight" :metalness="0.6" />
      </TresMesh>
    </TresGroup>
    <TresMesh :position="[-1.45, 1.05, 0.5]"><TresSphereGeometry :args="[0.18, 16, 16]" /><TresMeshStandardMaterial :color="C.duck" /></TresMesh>
    <TresMesh :position="[-1.3, 1.22, 0.62]"><TresSphereGeometry :args="[0.12, 16, 16]" /><TresMeshStandardMaterial :color="C.duck" /></TresMesh>
    <TresMesh :position="[-1.18, 1.2, 0.68]"><TresBoxGeometry :args="[0.09, 0.05, 0.09]" /><TresMeshStandardMaterial :color="C.orange" /></TresMesh>
    <TresMesh :position="[-0.4, 1.05, 0.6]"><TresCylinderGeometry :args="[0.12, 0.11, 0.26, 16]" /><TresMeshStandardMaterial :color="C.white" /></TresMesh>
    <Html :position="[-0.4, 1.3, 0.75]" center transform :distance-factor="1.6"><div class="tiny mono">kubectl get pods</div></Html>
    <Html :position="[0, 3.3, -0.4]" center>
      <div class="lbl">The Producer <span>{{ props.thinking ? 'thinking…' : 'presses the block onto records' }}</span></div>
    </Html>
  </TresGroup>

  <!-- ===== The Belt: press → booth ===== -->
  <TresGroup>
    <TresMesh :position="[(BELT.x0 + BELT.x1) / 2, BELT.y - 0.12, (BELT.z0 + BELT.z1) / 2]" :rotation="[0, BELT_YAW, 0]" receive-shadow>
      <TresBoxGeometry :args="[1.5, 0.16, BELT_LEN + 0.6]" />
      <TresMeshStandardMaterial :color="C.belt" :roughness="0.9" />
    </TresMesh>
    <TresMesh v-for="s in [-1, 1]" :key="'rail' + s" :position="[(BELT.x0 + BELT.x1) / 2 + s * 0.8 * Math.cos(BELT_YAW), BELT.y - 0.02, (BELT.z0 + BELT.z1) / 2 - s * 0.8 * Math.sin(BELT_YAW)]" :rotation="[0, BELT_YAW, 0]">
      <TresBoxGeometry :args="[0.08, 0.28, BELT_LEN + 0.6]" />
      <TresMeshStandardMaterial :color="C.metalLight" :metalness="0.6" :roughness="0.4" />
    </TresMesh>
    <TresMesh
      v-for="i in rollerCount" :key="'roll' + i" :ref="setRoller(i - 1)"
      :position="[BELT.x0 + (BELT.x1 - BELT.x0) * ((i - 0.5) / rollerCount), BELT.y - 0.1, BELT.z0 + (BELT.z1 - BELT.z0) * ((i - 0.5) / rollerCount)]"
      :rotation="[0, BELT_YAW, Math.PI / 2]"
    >
      <TresCylinderGeometry :args="[0.12, 0.12, 1.5, 12]" />
      <TresMeshStandardMaterial :color="C.metal" :metalness="0.5" :roughness="0.5" />
    </TresMesh>
    <!-- the block's records, newest under the press -->
    <TresGroup v-for="it in upcoming" :key="'br' + it.idx" :ref="setBeltRecord(it.idx)" :position="[BELT.x0, BELT.y + 0.05, BELT.z0]">
      <StudioRecord :kind="it.kind" :title="recordTitle(it)" :host="it.host" :radius="0.5" />
    </TresGroup>
    <Html :position="[(BELT.x0 + BELT.x1) / 2 - 1.4, 1.0, (BELT.z0 + BELT.z1) / 2]" center>
      <div class="lbl small">The Belt <span>{{ Math.max(0, props.sheetItems.length - props.sheetCursor) }} records to go</span></div>
    </Html>
  </TresGroup>

  <!-- ===== The DJ booth (Liquidsoap) ===== -->
  <TresGroup :position="[ANCHOR.dj[0], 0, ANCHOR.dj[2]]">
    <TresMesh :position="[0, 0.45, 0]" cast-shadow receive-shadow>
      <TresBoxGeometry :args="[4.4, 0.9, 1.8]" />
      <TresMeshStandardMaterial :color="C.metal" :roughness="0.7" :metalness="0.3" />
    </TresMesh>
    <TresGroup ref="deckA" :position="[-1.2, 0.92, 0.1]">
      <StudioRecord :kind="props.nowKind || 'music'" :title="props.nowTitle || ''" :host="props.nowHost" :radius="0.72" :glow="props.onAir ? 0.7 : 0.1" />
    </TresGroup>
    <TresGroup :position="[1.2, 0.92, 0.1]">
      <StudioRecord v-if="upcoming[0]" :kind="upcoming[0].kind" :title="recordTitle(upcoming[0])" :host="upcoming[0].host" :radius="0.72" :glow="0.2" :show-label="false" />
      <TresMesh v-else><TresCylinderGeometry :args="[0.72, 0.72, 0.05, 40]" /><TresMeshStandardMaterial :color="C.metalLight" /></TresMesh>
    </TresGroup>
    <TresGroup ref="tonearm" :position="[0, 0.55, 0.7]" :rotation="[0, -0.5, 0]">
      <TresMesh :position="[0, 0.4, 0]"><TresCylinderGeometry :args="[0.08, 0.1, 0.8, 12]" /><TresMeshStandardMaterial :color="C.metalLight" :metalness="0.7" :roughness="0.3" /></TresMesh>
      <TresMesh :position="[-0.6, 0.8, 0]" :rotation="[0, 0, Math.PI / 2]"><TresCylinderGeometry :args="[0.035, 0.035, 1.2, 8]" /><TresMeshStandardMaterial :color="C.cream" :metalness="0.6" /></TresMesh>
      <TresMesh :position="[-1.2, 0.75, 0]"><TresBoxGeometry :args="[0.18, 0.1, 0.12]" /><TresMeshStandardMaterial :color="C.orange" /></TresMesh>
    </TresGroup>
    <TresMesh v-for="i in 8" :key="'vu' + i" :ref="setVu(i - 1)" :position="[-0.7 + (i - 1) * 0.2, 1.1, -0.72]">
      <TresBoxGeometry :args="[0.13, 0.7, 0.1]" />
      <TresMeshStandardMaterial :color="i > 6 ? C.red : i > 4 ? C.amber : C.cyan" :emissive="i > 6 ? C.red : i > 4 ? C.amber : C.cyan" :emissive-intensity="0.6" />
    </TresMesh>
    <TresGroup :position="[0, 0, -1.6]">
      <TresMesh :position="[0, 0.85, 0]" cast-shadow><TresBoxGeometry :args="[1.1, 1.3, 0.7]" /><TresMeshStandardMaterial :color="C.cream" :roughness="0.6" /></TresMesh>
      <TresMesh :position="[0, 1.9, 0]" cast-shadow><TresBoxGeometry :args="[0.8, 0.7, 0.7]" /><TresMeshStandardMaterial :color="C.cream" :roughness="0.6" /></TresMesh>
      <TresMesh :position="[0, 1.93, 0.36]"><TresBoxGeometry :args="[0.56, 0.2, 0.02]" /><TresMeshStandardMaterial :color="props.onAir ? C.orange : C.dim" :emissive="props.onAir ? C.orange : C.dim" :emissive-intensity="0.9" /></TresMesh>
      <TresMesh :position="[0, 2.3, 0]"><TresTorusGeometry :args="[0.5, 0.07, 8, 24, Math.PI]" /><TresMeshStandardMaterial :color="C.metalLight" :metalness="0.6" /></TresMesh>
      <TresMesh v-for="s in [-1, 1]" :key="'cup' + s" :position="[s * 0.5, 1.9, 0]"><TresCylinderGeometry :args="[0.18, 0.18, 0.16, 16]" /><TresMeshStandardMaterial :color="C.orange" /></TresMesh>
    </TresGroup>
    <TresMesh :position="[0, 3.2, -2.2]">
      <TresBoxGeometry :args="[2.0, 0.6, 0.14]" />
      <TresMeshStandardMaterial :color="props.onAir ? C.red : '#3a1a1f'" :emissive="props.onAir ? C.red : '#000'" :emissive-intensity="1.1" />
    </TresMesh>
    <Html :position="[0, 3.2, -2.1]" center><div class="sign" :class="{ lit: props.onAir }">ON AIR</div></Html>
    <Html :position="[1.9, 0.6, 0.92]" center transform :distance-factor="2.2"><div class="sticker">works on my machine</div></Html>
    <Html :position="[0, 4.0, 0]" center><div class="lbl">The DJ <span>Liquidsoap</span></div></Html>
  </TresGroup>

  <!-- ===== The Mic: a host is speaking ===== -->
  <TresGroup :position="[ANCHOR.mic[0], 0, ANCHOR.mic[2]]">
    <TresMesh :position="[0, 0.08, 0]"><TresCylinderGeometry :args="[0.45, 0.5, 0.16, 24]" /><TresMeshStandardMaterial :color="C.metal" :metalness="0.5" /></TresMesh>
    <TresMesh :position="[0, 1.0, 0]"><TresCylinderGeometry :args="[0.04, 0.04, 1.9, 8]" /><TresMeshStandardMaterial :color="C.metalLight" :metalness="0.7" /></TresMesh>
    <TresMesh :position="[0, 2.05, 0]" :rotation="[0.5, 0, 0]">
      <TresCapsuleGeometry :args="[0.16, 0.34, 8, 16]" />
      <TresMeshStandardMaterial :color="speaking ? C.white : C.dim" :emissive="speaking ? C.white : '#000'" :emissive-intensity="0.6" :metalness="0.5" />
    </TresMesh>
    <Html v-if="speaking" :position="[0, 2.7, 0]" center>
      <div class="say"><b>{{ props.nowHost || 'host' }}</b> “{{ props.nowTitle }}”</div>
    </Html>
    <Html v-else :position="[0, 2.7, 0]" center><div class="lbl small">The Mic <span>station IDs, coming-ups, time checks</span></div></Html>
  </TresGroup>

  <!-- ===== The Jukebox (music generation) ===== -->
  <TresGroup :position="[ANCHOR.jukebox[0], 0, ANCHOR.jukebox[2]]">
    <TresMesh :position="[0, 1.1, 0]" cast-shadow>
      <TresBoxGeometry :args="[2.2, 2.2, 1.4]" />
      <TresMeshStandardMaterial :color="C.juke" :roughness="0.5" :metalness="0.2" />
    </TresMesh>
    <TresMesh :position="[0, 2.2, 0]" :rotation="[0, 0, Math.PI / 2]" cast-shadow>
      <TresCylinderGeometry :args="[1.1, 1.1, 2.2, 32, 1, false, 0, Math.PI]" />
      <TresMeshStandardMaterial :color="C.juke" :roughness="0.5" />
    </TresMesh>
    <TresMesh ref="jukeArch" :position="[0, 2.2, 0.72]">
      <TresTorusGeometry :args="[1.0, 0.1, 8, 32, Math.PI]" />
      <TresMeshStandardMaterial :color="C.cyan" :emissive="C.cyan" :emissive-intensity="0.25" />
    </TresMesh>
    <TresMesh :position="[0, 1.5, 0.72]">
      <TresBoxGeometry :args="[1.6, 0.7, 0.05]" />
      <TresMeshStandardMaterial color="#0d1a1a" :emissive="C.cyan" :emissive-intensity="props.jukeboxPrompt ? 0.35 : 0.05" />
    </TresMesh>
    <TresMesh v-for="i in 5" :key="'jb' + i" :position="[-0.8 + (i - 1) * 0.4, 0.55, 0.72]">
      <TresBoxGeometry :args="[0.28, 0.18, 0.06]" />
      <TresMeshStandardMaterial :color="JUKE_COLORS[i - 1]" :emissive="JUKE_COLORS[i - 1]" :emissive-intensity="props.jukeboxPrompt ? 0.8 : 0.2" />
    </TresMesh>
    <TresMesh :position="[0, 0.28, 0.72]"><TresBoxGeometry :args="[1.3, 0.12, 0.06]" /><TresMeshBasicMaterial color="#17130e" /></TresMesh>
    <TresGroup ref="popped" :position="[0, 0.3, 1.4]">
      <StudioRecord v-if="props.beds > 0" kind="music" :radius="0.45" :show-label="false" :glow="0.5" />
    </TresGroup>
    <Html :position="[0, 1.5, 0.8]" center>
      <div class="juke" :class="{ on: !!props.jukeboxPrompt }">
        <span class="k">{{ props.jukeboxPrompt ? 'GENERATING' : 'JUKEBOX' }}</span>
        <span class="p">{{ props.jukeboxPrompt || 'ACE-Step · type a prompt, get a record' }}</span>
      </div>
    </Html>
    <Html :position="[0, 3.6, 0]" center><div class="lbl">The Jukebox <span>music beds, from a prompt</span></div></Html>
  </TresGroup>

  <!-- ===== The Library (the bank + episodes) ===== -->
  <TresGroup :position="[ANCHOR.library[0], 0, ANCHOR.library[2]]">
    <TresMesh :position="[0, 1.6, 0]" cast-shadow>
      <TresBoxGeometry :args="[1.4, 3.2, 3.2]" />
      <TresMeshStandardMaterial :color="C.wall" :roughness="0.9" />
    </TresMesh>
    <TresMesh v-for="s in [0.45, 1.5, 2.55]" :key="'shelf' + s" :position="[0.75, s, 0]"><TresBoxGeometry :args="[0.9, 0.05, 3.2]" /><TresMeshStandardMaterial :color="C.metalLight" /></TresMesh>
    <TresGroup v-for="i in stacks(props.beds, 10)" :key="'bed' + i" :position="[0.75, 0.95, -1.35 + (i - 1) * 0.3]">
      <StudioRecord kind="music" :radius="0.45" standing :show-label="false" :glow="0.35" />
    </TresGroup>
    <TresMesh v-for="i in stacks(props.stationIds, 12)" :key="'id' + i" :position="[0.75, 1.62 + Math.floor((i - 1) / 6) * 0.14, -1.3 + ((i - 1) % 6) * 0.5]">
      <TresBoxGeometry :args="[0.2, 0.12, 0.42]" />
      <TresMeshStandardMaterial :color="C.white" :roughness="0.7" />
    </TresMesh>
    <TresGroup v-for="i in stacks(props.episodes, 10)" :key="'ep' + i" :position="[0.75, 3.0, -1.35 + (i - 1) * 0.3]">
      <StudioRecord kind="episode" :radius="0.42" standing :show-label="false" :glow="0.4" />
    </TresGroup>
    <Html :position="[0, 3.9, 0]" center>
      <div class="lbl">The Library <span>{{ props.episodes }} episodes · {{ props.beds }} beds · {{ props.stationIds }} IDs</span></div>
    </Html>
    <Html :position="[-0.72, 1.8, 0]" :rotation="[0, -Math.PI / 2, 0]" center transform :distance-factor="2.4">
      <div class="board">TODO: prod<br>tabs | spaces<br><s>rewrite in rust</s></div>
    </Html>
  </TresGroup>

  <!-- ===== The Transmitter (Icecast) ===== -->
  <TresGroup :position="[ANCHOR.transmitter[0], 0, ANCHOR.transmitter[2]]">
    <TresMesh :position="[0, 0.3, 0]" cast-shadow><TresCylinderGeometry :args="[1.0, 1.2, 0.6, 24]" /><TresMeshStandardMaterial :color="C.metal" :metalness="0.4" :roughness="0.6" /></TresMesh>
    <TresMesh :position="[0, 2.5, 0]" cast-shadow><TresCylinderGeometry :args="[0.06, 0.24, 4.0, 8]" /><TresMeshStandardMaterial :color="C.metalLight" :metalness="0.7" :roughness="0.3" /></TresMesh>
    <TresMesh v-for="h in [1.4, 2.4, 3.4]" :key="'strut' + h" :position="[0, h, 0]" :rotation="[Math.PI / 2, 0, 0]"><TresTorusGeometry :args="[0.35 - h * 0.05, 0.02, 6, 16]" /><TresMeshStandardMaterial :color="C.metalLight" /></TresMesh>
    <TresMesh :position="[0, 4.6, 0]">
      <TresSphereGeometry :args="[0.2, 16, 16]" />
      <TresMeshStandardMaterial :color="props.onAir ? C.orange : C.dim" :emissive="props.onAir ? C.orange : '#000'" :emissive-intensity="1.2" />
    </TresMesh>
    <TresMesh v-for="i in 3" :key="'ring' + i" :ref="setRing(i - 1)" :position="[0, 4.6, 0]" :rotation="[Math.PI / 2, 0, 0]">
      <TresTorusGeometry :args="[1, 0.04, 6, 48]" />
      <TresMeshBasicMaterial :color="C.orange" :transparent="true" :opacity="0" />
    </TresMesh>
    <TresMesh v-for="i in Math.min(props.listeners, 24)" :key="'lis' + i" :position="[Math.cos(i * 1.7) * (1.8 + (i % 3) * 0.4), 1.6 + (i % 4) * 0.5, Math.sin(i * 1.7) * (1.8 + (i % 3) * 0.4)]">
      <TresSphereGeometry :args="[0.13, 12, 12]" />
      <TresMeshStandardMaterial :color="C.white" :emissive="C.white" :emissive-intensity="0.8" />
    </TresMesh>
    <Html :position="[0, 5.4, 0]" center><div class="lbl">The Transmitter <span>Icecast · {{ props.listeners }} listening</span></div></Html>
    <Html :position="[0, 1.05, 1.3]" center transform :distance-factor="2.2"><div class="neon">NOT A BOT <small>(mostly)</small></div></Html>
  </TresGroup>

  <!-- ===== The Manager drone ===== -->
  <TresGroup ref="drone" :position="[5, 3.6, 3]">
    <TresMesh><TresBoxGeometry :args="[0.6, 0.18, 0.6]" /><TresMeshStandardMaterial :color="C.metalLight" :metalness="0.6" /></TresMesh>
    <TresMesh v-for="s in [[-0.35, -0.35], [0.35, -0.35], [-0.35, 0.35], [0.35, 0.35]]" :key="'rot' + s[0] + s[1]" :position="[s[0], 0.14, s[1]]">
      <TresCylinderGeometry :args="[0.18, 0.18, 0.02, 12]" />
      <TresMeshStandardMaterial :color="C.cyan" :transparent="true" :opacity="0.55" />
    </TresMesh>
    <TresMesh :position="[0, -0.18, 0]"><TresSphereGeometry :args="[0.08, 10, 10]" /><TresMeshStandardMaterial :color="C.amber" :emissive="C.amber" :emissive-intensity="1" /></TresMesh>
    <TresPointLight :position="[0, -0.3, 0]" :intensity="4" :color="C.amber" :distance="5" />
    <Html :position="[0, 0.55, 0]" center><div class="lbl small">The Manager <span>a round every 5 min</span></div></Html>
  </TresGroup>

  <!-- packets on the tubes -->
  <TresMesh v-for="i in POOL" :key="'pk' + i" :ref="setPacket(i - 1)" :position="[0, -5, 0]" :visible="false">
    <TresSphereGeometry :args="[0.14, 12, 12]" />
    <TresMeshStandardMaterial :color="C.cyan" :emissive="C.cyan" :emissive-intensity="1.4" />
  </TresMesh>

  <!-- commentary, beside whoever said it -->
  <template v-for="key in ['dj', 'director', 'producer', 'bank', 'monitor']" :key="'bub' + key">
    <Html v-if="bubbleFor(key)" :position="[ANCHOR[BUBBLE_AT[key]][0], ANCHOR[BUBBLE_AT[key]][1] + 1.6, ANCHOR[BUBBLE_AT[key]][2]]" center>
      <div class="bubble" :class="key">{{ bubbleFor(key)?.text }}</div>
    </Html>
  </template>
</template>

<style scoped>
.lbl { font: 600 11px/1.2 "IBM Plex Mono", ui-monospace, monospace; color: #f4efe6; text-transform: uppercase; letter-spacing: .08em; white-space: nowrap; text-shadow: 0 1px 8px rgba(0,0,0,.9); pointer-events: none; }
.lbl span { display: block; font-weight: 400; text-transform: none; letter-spacing: 0; color: #cfc6b8; font-size: 10px; margin-top: 2px; }
.lbl.small { font-size: 10px; }
.sign { font: 900 12px/1 "Archivo Black", "Archivo", sans-serif; letter-spacing: .12em; color: #5a1a22; pointer-events: none; }
.sign.lit { color: #fff; text-shadow: 0 0 10px #ff2e4a, 0 0 22px #ff2e4a; }
.sticker { font: 600 8px/1 "IBM Plex Mono", monospace; color: #1a1a00; background: #e9d829; padding: 3px 5px; border-radius: 2px; transform: rotate(-6deg); white-space: nowrap; pointer-events: none; }
.tiny { font-size: 6px; color: #1a1a1a; background: #f4efe6; padding: 1px 3px; border-radius: 2px; white-space: nowrap; pointer-events: none; }
.mono { font-family: "IBM Plex Mono", monospace; }
.board { font: 500 8px/1.5 "IBM Plex Mono", monospace; color: #2b2622; background: #f4efe6; padding: 6px 8px; border: 3px solid #6b655b; width: 96px; pointer-events: none; }
.neon { font: 800 11px/1 "Archivo", sans-serif; color: #5eead4; letter-spacing: .1em; text-shadow: 0 0 8px #5eead4, 0 0 18px #5eead4; white-space: nowrap; pointer-events: none; }
.neon small { font-size: 8px; font-weight: 500; letter-spacing: 0; }
.bubble { width: max-content; max-width: 260px; font: 500 11px/1.35 "Archivo", sans-serif; color: #17130e; background: #f4efe6; border-radius: 10px; padding: 6px 9px; box-shadow: 0 4px 18px rgba(0,0,0,.5); pointer-events: none; }
.bubble.dj { border-left: 4px solid #ff6a00; }
.bubble.director { border-left: 4px solid #f4efe6; }
.bubble.producer { border-left: 4px solid #5eead4; }
.bubble.bank { border-left: 4px solid #b39ddb; }
.bubble.monitor { border-left: 4px solid #f5b642; }
.say { width: max-content; max-width: 280px; font: 500 12px/1.35 "Archivo", sans-serif; color: #17130e; background: #f4efe6; border-radius: 12px; padding: 7px 10px; box-shadow: 0 4px 18px rgba(0,0,0,.5); pointer-events: none; border-left: 4px solid #b39ddb; }
.say b { font-family: "IBM Plex Mono", monospace; font-size: 10px; text-transform: uppercase; letter-spacing: .06em; color: #6b655b; margin-right: 6px; }
.juke { width: 150px; display: grid; gap: 2px; font-family: "IBM Plex Mono", monospace; color: #5eead4; text-align: center; pointer-events: none; }
.juke .k { font-size: 9px; letter-spacing: .14em; }
.juke .p { font-size: 8px; line-height: 1.3; color: #9be9dc; white-space: normal; }
.juke.on .k { text-shadow: 0 0 8px #5eead4; }
</style>
