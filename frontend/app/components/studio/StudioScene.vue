<script setup lang="ts">
/**
 * The set (plans/21). Every component of the station is a thing on a
 * dark floor: the Library, the Producer's desk, the Switchboard, the DJ
 * booth, the Transmitter, and the patrol Drone. Props are the station's
 * state; the scene animates the difference between frames.
 *
 * All primitives, no models to load: it must draw the moment the page does.
 */
import { computed, shallowRef, watch } from 'vue'
import { useLoop } from '@tresjs/core'
import { Html, OrbitControls } from '@tresjs/cientos'
import type { Group, Mesh } from 'three'

export interface Bubble { component: string, text: string, at: number }
export interface SheetItem { kind: string, episode?: string | null, host?: string | null, line?: string | null, music_style?: string | null }

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
  bubbles: Bubble[]
  /** Monotonic counters; a change fires an animation. */
  trackChanges: number
  plans: number
  packets: { id: number, from: string, to: string, color: string }[]
  monitorRounds: number
}>()

// --- the palette: charcoal set, warm light, orange for anything on air ------
const C = {
  floor: '#25211c', wall: '#2c2722', metal: '#3b3733', metalLight: '#514c46',
  cream: '#e8e0d0', orange: '#ff6a00', cyan: '#5eead4', amber: '#f5b642',
  lavender: '#b39ddb', white: '#f4efe6', red: '#d7263d', yellow: '#e9d829',
  duck: '#f2c14e', dim: '#6b655b',
}
const KIND_COLOR: Record<string, string> = {
  episode: C.orange, music: C.cyan, station_id: C.white, coming_up: C.amber, time_check: C.lavender,
}
const kindColor = (k: string | null | undefined) => KIND_COLOR[k || ''] || C.dim

// --- anchors: where each component lives, and where its packets dock -------
const ANCHOR: Record<string, [number, number, number]> = {
  library: [-7.2, 1.2, 0.5],
  producer: [-3.6, 1.4, -3.2],
  hub: [0, 1.2, -0.2],
  dj: [0.2, 1.3, 3.4],
  transmitter: [6.4, 2.6, -1.2],
  monitor: [3.5, 3.2, 1.5],
}

// --- animation state -------------------------------------------------------
// Per-frame motion never touches Vue reactivity: the loop mutates three.js
// objects through refs. Reactive state changes only on events, so the
// template re-renders a few times a minute, not sixty times a second.
const deckA = shallowRef<Mesh | null>(null)
const tonearm = shallowRef<Group | null>(null)
const eye = shallowRef<Mesh | null>(null)
const drone = shallowRef<Group | null>(null)
const strip = shallowRef<Group | null>(null)
const ringMeshes: Mesh[] = []
const vuMeshes: Mesh[] = []
const packetMeshes: Mesh[] = []
const setRing = (i: number) => (el: unknown) => { if (el) ringMeshes[i] = el as Mesh }
const setVu = (i: number) => (el: unknown) => { if (el) vuMeshes[i] = el as Mesh }
const setPacket = (i: number) => (el: unknown) => { if (el) packetMeshes[i] = el as Mesh }
const POOL = 12
const anim = {
  rings: [0, 0.33, 0.66],
  vu: [0.2, 0.4, 0.3, 0.5, 0.35, 0.25, 0.45, 0.3],
  swapT: 1, swapping: false, printerT: 1, droneUntil: 0,
  packets: [] as { id: number, from: number[], to: number[], t: number, color: string }[],
}

watch(() => props.trackChanges, () => { anim.swapT = 0; anim.swapping = true })
watch(() => props.plans, () => { anim.printerT = 0 })
watch(() => props.monitorRounds, () => { anim.droneUntil = performance.now() + 3500 })
watch(() => props.packets, (list) => {
  for (const p of list) {
    if (anim.packets.some(l => l.id === p.id)) continue
    anim.packets.push({ id: p.id, from: ANCHOR[p.from] || ANCHOR.hub, to: ANCHOR[p.to] || ANCHOR.hub, t: 0, color: p.color })
  }
}, { deep: true })

const { onBeforeRender } = useLoop()
onBeforeRender(({ delta, elapsed }) => {
  if (deckA.value && props.onAir) deckA.value.rotation.y += delta * 2.2
  if (anim.swapping) {
    anim.swapT = Math.min(1, anim.swapT + delta / 1.4)
    if (tonearm.value) {
      const lift = Math.sin(anim.swapT * Math.PI) * 0.35
      tonearm.value.position.y = 0.55 + lift
      tonearm.value.rotation.y = -0.6 + Math.sin(anim.swapT * Math.PI) * 0.9
    }
    if (anim.swapT >= 1) anim.swapping = false
  }
  if (eye.value) {
    const mat = eye.value.material as { emissiveIntensity: number }
    mat.emissiveIntensity = props.thinking ? 1.2 + Math.sin(elapsed * 8) * 0.8 : 0.35
  }
  for (let i = 0; i < anim.rings.length; i++) {
    if (props.onAir) anim.rings[i] = (anim.rings[i] + delta * 0.35) % 1
    const m = ringMeshes[i]
    if (m) {
      const r = anim.rings[i]
      m.scale.set(0.3 + r * 3.2, 0.3 + r * 3.2, 1)
      ;(m.material as { opacity: number }).opacity = props.onAir ? (1 - r) * 0.7 : 0
    }
  }
  for (let i = 0; i < anim.vu.length; i++) {
    anim.vu[i] = props.onAir
      ? 0.15 + Math.abs(Math.sin(elapsed * (2.1 + i * 0.37) + i)) * 0.85
      : Math.max(0.05, anim.vu[i] - delta)
    const m = vuMeshes[i]
    if (m) { m.scale.y = anim.vu[i]; m.position.y = 0.9 + anim.vu[i] * 0.3 }
  }
  anim.printerT = Math.min(1, anim.printerT + delta / 1.2)
  if (strip.value) strip.value.position.x = 0.7 - 0.9 * (1 - anim.printerT)
  if (drone.value) {
    const parked = performance.now() < anim.droneUntil
    const target = parked
      ? [ANCHOR.producer[0] + 1.2, 3.2, ANCHOR.producer[2] + 0.6]
      : [Math.cos(elapsed * 0.25) * 6.5, 3.4 + Math.sin(elapsed * 1.3) * 0.15, Math.sin(elapsed * 0.25) * 4.5]
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
      const arc = Math.sin(p.t * Math.PI) * 0.9
      m.position.set(
        p.from[0] + (p.to[0] - p.from[0]) * p.t,
        p.from[1] + (p.to[1] - p.from[1]) * p.t + arc,
        p.from[2] + (p.to[2] - p.from[2]) * p.t,
      )
      ;(m.material as { color: { set: (c: string) => void }, emissive: { set: (c: string) => void } }).color.set(p.color)
      ;(m.material as { emissive: { set: (c: string) => void } }).emissive.set(p.color)
    }
  }
})


// Tubes from the hub to each station: a thin cylinder placed between two points.
function tube(a: [number, number, number], b: [number, number, number]) {
  const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2]
  const len = Math.hypot(dx, dy, dz)
  const mid: [number, number, number] = [a[0] + dx / 2, a[1] + dy / 2, a[2] + dz / 2]
  // Rotate the y-axis cylinder to point along (dx,dy,dz).
  const rotZ = -Math.atan2(dx, dy)
  const rotX = Math.atan2(dz, Math.hypot(dx, dy))
  return { mid, len, rot: [rotX, 0, rotZ] as [number, number, number] }
}
const TUBES = computed(() => ['library', 'producer', 'dj', 'transmitter'].map(k => ({ key: k, ...tube([0, 0.6, -0.2], [ANCHOR[k][0], 0.6, ANCHOR[k][2]]) })))

// The run sheet as a strip of tiles on the producer's desk.
const tiles = computed(() => props.sheetItems.slice(0, 16))

// The latest bubble per component, if fresh.
const bubbleFor = (component: string) => {
  const b = [...props.bubbles].reverse().find(x => x.component === component)
  return b && performance.now() - b.at < 9000 ? b : null
}
const stacks = (n: number, max: number) => Math.max(0, Math.min(max, n))
</script>

<template>
  <TresPerspectiveCamera :position="[9, 8.5, 11]" :look-at="[0, 0.8, 0]" :fov="38" />
  <OrbitControls :target="[0, 0.8, 0]" :min-distance="7" :max-distance="24" :max-polar-angle="1.35" :enable-pan="false" />

  <!-- Night, but a lit night: a warm key from above-right, a cool sky fill
       from the hemisphere, and practicals over each station. -->
  <TresAmbientLight :intensity="0.9" color="#fff3e0" />
  <TresHemisphereLight :intensity="1.1" color="#cfd8ff" ground-color="#3a2a1a" />
  <TresDirectionalLight :position="[6, 12, 6]" :intensity="2.6" color="#fff1dc" cast-shadow />
  <TresPointLight :position="[0.2, 3.2, 3.4]" :intensity="props.onAir ? 16 : 4" :color="C.orange" :distance="8" />
  <TresPointLight :position="[6.4, 4, -1.2]" :intensity="props.onAir ? 10 : 2" :color="C.orange" :distance="7" />
  <TresPointLight :position="[-3.6, 3.4, -2.6]" :intensity="12" color="#ffe9c9" :distance="7" />
  <TresPointLight :position="[-6.8, 3.4, 1.2]" :intensity="10" color="#ffe9c9" :distance="6" />
  <TresPointLight :position="[0, 3.6, -0.2]" :intensity="8" color="#dfe8ff" :distance="6" />

  <!-- Floor and back wall -->
  <TresMesh :position="[0, -0.05, 0]" receive-shadow>
    <TresBoxGeometry :args="[20, 0.1, 13]" />
    <TresMeshStandardMaterial :color="C.floor" :roughness="0.95" />
  </TresMesh>
  <TresMesh :position="[0, 2.5, -6.55]">
    <TresBoxGeometry :args="[20, 5, 0.1]" />
    <TresMeshStandardMaterial :color="C.wall" :roughness="1" />
  </TresMesh>
  <!-- Grid of faint plus marks, the station's own ground texture -->
  <TresMesh v-for="i in 24" :key="'px' + i" :position="[((i - 1) % 6) * 3.2 - 8, 0.011, Math.floor((i - 1) / 6) * 3.2 - 5]" :rotation="[-Math.PI / 2, 0, 0]">
    <TresPlaneGeometry :args="[0.28, 0.04]" />
    <TresMeshBasicMaterial color="#5a3212" />
  </TresMesh>
  <TresMesh v-for="i in 24" :key="'py' + i" :position="[((i - 1) % 6) * 3.2 - 8, 0.011, Math.floor((i - 1) / 6) * 3.2 - 5]" :rotation="[-Math.PI / 2, 0, Math.PI / 2]">
    <TresPlaneGeometry :args="[0.28, 0.04]" />
    <TresMeshBasicMaterial color="#5a3212" />
  </TresMesh>

  <!-- ===== The Switchboard (hn.fm API) ===== -->
  <TresGroup :position="[0, 0, -0.2]">
    <TresMesh :position="[0, 0.6, 0]" cast-shadow>
      <TresCylinderGeometry :args="[1.1, 1.25, 1.2, 6]" />
      <TresMeshStandardMaterial :color="C.metal" :roughness="0.6" :metalness="0.4" />
    </TresMesh>
    <TresMesh :position="[0, 1.25, 0]">
      <TresCylinderGeometry :args="[0.55, 0.55, 0.1, 6]" />
      <TresMeshStandardMaterial :color="C.orange" :emissive="C.orange" :emissive-intensity="0.7" />
    </TresMesh>
    <TresMesh v-for="t in TUBES" :key="t.key" :position="t.mid" :rotation="t.rot">
      <TresCylinderGeometry :args="[0.05, 0.05, t.len, 8]" />
      <TresMeshStandardMaterial :color="C.metalLight" :roughness="0.4" :metalness="0.6" />
    </TresMesh>
    <Html :position="[0, 2.1, 0]" center>
      <div class="lbl">Switchboard <span>hn.fm API</span></div>
    </Html>
  </TresGroup>

  <!-- ===== The DJ booth (Liquidsoap) ===== -->
  <TresGroup :position="[0.2, 0, 3.4]">
    <TresMesh :position="[0, 0.45, 0]" cast-shadow receive-shadow>
      <TresBoxGeometry :args="[3.6, 0.9, 1.5]" />
      <TresMeshStandardMaterial :color="C.metal" :roughness="0.7" :metalness="0.3" />
    </TresMesh>
    <!-- deck A: the item on air -->
    <TresMesh ref="deckA" :position="[-1.0, 0.93, 0]" :rotation="[0, 0, 0]">
      <TresCylinderGeometry :args="[0.55, 0.55, 0.06, 32]" />
      <TresMeshStandardMaterial :color="kindColor(props.nowKind)" :emissive="kindColor(props.nowKind)" :emissive-intensity="props.onAir ? 0.5 : 0.05" :roughness="0.35" />
    </TresMesh>
    <TresMesh :position="[-1.0, 0.98, 0]">
      <TresCylinderGeometry :args="[0.12, 0.12, 0.04, 16]" />
      <TresMeshStandardMaterial :color="C.cream" />
    </TresMesh>
    <!-- deck B: waiting -->
    <TresMesh :position="[1.0, 0.93, 0]">
      <TresCylinderGeometry :args="[0.55, 0.55, 0.06, 32]" />
      <TresMeshStandardMaterial :color="C.metalLight" :roughness="0.5" />
    </TresMesh>
    <!-- the tonearm on its robotic arm -->
    <TresGroup ref="tonearm" :position="[-0.3, 0.55, 0.5]" :rotation="[0, -0.6, 0]">
      <TresMesh :position="[0, 0.35, 0]">
        <TresCylinderGeometry :args="[0.07, 0.09, 0.7, 12]" />
        <TresMeshStandardMaterial :color="C.metalLight" :metalness="0.7" :roughness="0.3" />
      </TresMesh>
      <TresMesh :position="[-0.45, 0.7, 0]" :rotation="[0, 0, Math.PI / 2]">
        <TresCylinderGeometry :args="[0.03, 0.03, 0.9, 8]" />
        <TresMeshStandardMaterial :color="C.cream" :metalness="0.6" />
      </TresMesh>
      <TresMesh :position="[-0.9, 0.66, 0]">
        <TresBoxGeometry :args="[0.14, 0.08, 0.1]" />
        <TresMeshStandardMaterial :color="C.orange" />
      </TresMesh>
    </TresGroup>
    <!-- VU meter -->
    <TresMesh v-for="i in 8" :key="'vu' + i" :ref="setVu(i - 1)" :position="[-0.7 + (i - 1) * 0.2, 1.0, -0.55]">
      <TresBoxGeometry :args="[0.12, 0.6, 0.1]" />
      <TresMeshStandardMaterial :color="i > 6 ? C.red : i > 4 ? C.amber : C.cyan" :emissive="i > 6 ? C.red : i > 4 ? C.amber : C.cyan" :emissive-intensity="0.6" />
    </TresMesh>
    <!-- the robot DJ: torso, head, headphones -->
    <TresGroup :position="[0, 0, -1.3]">
      <TresMesh :position="[0, 0.8, 0]" cast-shadow>
        <TresBoxGeometry :args="[0.9, 1.1, 0.6]" />
        <TresMeshStandardMaterial :color="C.cream" :roughness="0.6" />
      </TresMesh>
      <TresMesh :position="[0, 1.75, 0]" cast-shadow>
        <TresBoxGeometry :args="[0.7, 0.6, 0.6]" />
        <TresMeshStandardMaterial :color="C.cream" :roughness="0.6" />
      </TresMesh>
      <TresMesh :position="[0, 1.78, 0.31]">
        <TresBoxGeometry :args="[0.5, 0.18, 0.02]" />
        <TresMeshStandardMaterial :color="props.onAir ? C.orange : C.dim" :emissive="props.onAir ? C.orange : C.dim" :emissive-intensity="0.9" />
      </TresMesh>
      <TresMesh :position="[0, 2.1, 0]" :rotation="[0, 0, 0]">
        <TresTorusGeometry :args="[0.42, 0.06, 8, 24, Math.PI]" />
        <TresMeshStandardMaterial :color="C.metalLight" :metalness="0.6" />
      </TresMesh>
      <TresMesh v-for="s in [-1, 1]" :key="'cup' + s" :position="[s * 0.42, 1.75, 0]">
        <TresCylinderGeometry :args="[0.16, 0.16, 0.14, 16]" />
        <TresMeshStandardMaterial :color="C.orange" />
      </TresMesh>
    </TresGroup>
    <!-- ON AIR sign -->
    <TresMesh :position="[0, 2.9, -1.9]">
      <TresBoxGeometry :args="[1.6, 0.5, 0.12]" />
      <TresMeshStandardMaterial :color="props.onAir ? C.red : '#3a1a1f'" :emissive="props.onAir ? C.red : '#000'" :emissive-intensity="1.1" />
    </TresMesh>
    <Html :position="[0, 2.9, -1.83]" center>
      <div class="sign" :class="{ lit: props.onAir }">ON AIR</div>
    </Html>
    <!-- sticker -->
    <Html :position="[1.55, 0.6, 0.76]" center transform :distance-factor="2.2">
      <div class="sticker">works on my machine</div>
    </Html>
    <Html :position="[0, 3.6, 0]" center>
      <div class="lbl">The DJ <span>Liquidsoap</span></div>
    </Html>
  </TresGroup>

  <!-- ===== The Producer's desk (the model) ===== -->
  <TresGroup :position="[-3.6, 0, -3.2]">
    <TresMesh :position="[0, 0.4, 0]" cast-shadow receive-shadow>
      <TresBoxGeometry :args="[3.2, 0.8, 1.4]" />
      <TresMeshStandardMaterial :color="C.metal" :roughness="0.7" />
    </TresMesh>
    <!-- the producer: a boxy robot with one big eye -->
    <TresGroup :position="[-0.6, 0, -1.2]">
      <TresMesh :position="[0, 0.9, 0]" cast-shadow>
        <TresBoxGeometry :args="[1.0, 1.3, 0.8]" />
        <TresMeshStandardMaterial :color="C.metalLight" :roughness="0.5" :metalness="0.3" />
      </TresMesh>
      <TresMesh ref="eye" :position="[0, 1.15, 0.42]">
        <TresSphereGeometry :args="[0.22, 24, 24]" />
        <TresMeshStandardMaterial :color="C.cyan" :emissive="C.cyan" :emissive-intensity="0.35" />
      </TresMesh>
      <TresMesh :position="[0, 1.7, 0]">
        <TresCylinderGeometry :args="[0.03, 0.03, 0.5, 8]" />
        <TresMeshStandardMaterial :color="C.cream" />
      </TresMesh>
      <TresMesh :position="[0, 1.98, 0]">
        <TresSphereGeometry :args="[0.07, 12, 12]" />
        <TresMeshStandardMaterial :color="props.thinking ? C.cyan : C.dim" :emissive="props.thinking ? C.cyan : '#000'" :emissive-intensity="1" />
      </TresMesh>
    </TresGroup>
    <!-- dot-matrix printer and the strip it prints: the run sheet -->
    <TresMesh :position="[0.7, 0.98, -0.2]" cast-shadow>
      <TresBoxGeometry :args="[1.2, 0.36, 0.7]" />
      <TresMeshStandardMaterial :color="C.cream" :roughness="0.8" />
    </TresMesh>
    <TresGroup ref="strip" :position="[0.7, 1.2, 0.55]">
      <TresMesh v-for="(it, i) in tiles" :key="'tile' + i" :position="[(i - tiles.length / 2) * 0.28 + 0.14, 0, 0]">
        <TresBoxGeometry :args="[0.24, i < props.sheetCursor ? 0.05 : 0.14, 0.24]" />
        <TresMeshStandardMaterial :color="kindColor(it.kind)" :emissive="kindColor(it.kind)" :emissive-intensity="i === props.sheetCursor ? 0.9 : i < props.sheetCursor ? 0.05 : 0.3" :transparent="true" :opacity="i < props.sheetCursor ? 0.45 : 1" />
      </TresMesh>
      <TresMesh v-if="tiles.length" :position="[(Math.min(props.sheetCursor, tiles.length - 1) - tiles.length / 2) * 0.28 + 0.14, 0.22, 0]">
        <TresConeGeometry :args="[0.08, 0.16, 4]" />
        <TresMeshStandardMaterial :color="C.white" :emissive="C.white" :emissive-intensity="0.6" />
      </TresMesh>
    </TresGroup>
    <!-- rubber duck and the mug -->
    <TresMesh :position="[-1.25, 0.95, 0.35]">
      <TresSphereGeometry :args="[0.16, 16, 16]" />
      <TresMeshStandardMaterial :color="C.duck" />
    </TresMesh>
    <TresMesh :position="[-1.13, 1.1, 0.45]">
      <TresSphereGeometry :args="[0.11, 16, 16]" />
      <TresMeshStandardMaterial :color="C.duck" />
    </TresMesh>
    <TresMesh :position="[-1.02, 1.08, 0.5]">
      <TresBoxGeometry :args="[0.08, 0.04, 0.08]" />
      <TresMeshStandardMaterial :color="C.orange" />
    </TresMesh>
    <TresMesh :position="[1.35, 0.95, 0.4]">
      <TresCylinderGeometry :args="[0.11, 0.1, 0.24, 16]" />
      <TresMeshStandardMaterial :color="C.white" />
    </TresMesh>
    <Html :position="[1.35, 1.2, 0.55]" center transform :distance-factor="1.6">
      <div class="tiny mono">kubectl get pods</div>
    </Html>
    <Html :position="[0, 3.2, -0.6]" center>
      <div class="lbl">The Producer <span>{{ props.thinking ? 'thinking…' : 'the local model' }}</span></div>
    </Html>
  </TresGroup>

  <!-- ===== The Library (the bank + episodes) ===== -->
  <TresGroup :position="[-7.2, 0, 0.5]">
    <TresMesh :position="[0, 1.4, 0]" cast-shadow>
      <TresBoxGeometry :args="[1.2, 2.8, 2.6]" />
      <TresMeshStandardMaterial :color="C.wall" :roughness="0.9" />
    </TresMesh>
    <!-- records (music beds): stacked discs -->
    <TresMesh v-for="i in stacks(props.beds, 12)" :key="'bed' + i" :position="[0.62, 0.25 + (i - 1) * 0.11, -0.7]" :rotation="[0, 0, Math.PI / 2]">
      <TresCylinderGeometry :args="[0.42, 0.42, 0.05, 24]" />
      <TresMeshStandardMaterial :color="C.cyan" :emissive="C.cyan" :emissive-intensity="0.25" />
    </TresMesh>
    <!-- cassettes (station IDs) -->
    <TresMesh v-for="i in stacks(props.stationIds, 12)" :key="'id' + i" :position="[0.65, 1.55 + ((i - 1) % 6) * 0.14, 0.15 + Math.floor((i - 1) / 6) * 0.45]">
      <TresBoxGeometry :args="[0.16, 0.1, 0.36]" />
      <TresMeshStandardMaterial :color="C.white" :roughness="0.7" />
    </TresMesh>
    <!-- episodes: a rack of glowing cards -->
    <TresMesh v-for="i in stacks(props.episodes, 14)" :key="'ep' + i" :position="[0.66, 2.35 + Math.floor((i - 1) / 7) * 0.3, -1.05 + ((i - 1) % 7) * 0.3]">
      <TresBoxGeometry :args="[0.03, 0.22, 0.22]" />
      <TresMeshStandardMaterial :color="C.orange" :emissive="C.orange" :emissive-intensity="0.45" />
    </TresMesh>
    <Html :position="[0, 3.4, 0]" center>
      <div class="lbl">The Library <span>{{ props.episodes }} episodes · {{ props.beds }} beds · {{ props.stationIds }} IDs</span></div>
    </Html>
    <!-- whiteboard on the wall -->
    <Html :position="[-0.62, 1.6, 0]" :rotation="[0, -Math.PI / 2, 0]" center transform :distance-factor="2.4">
      <div class="board">TODO: prod<br>tabs | spaces<br><s>rewrite in rust</s></div>
    </Html>
  </TresGroup>

  <!-- ===== The Transmitter (Icecast) ===== -->
  <TresGroup :position="[6.4, 0, -1.2]">
    <TresMesh :position="[0, 0.3, 0]" cast-shadow>
      <TresCylinderGeometry :args="[0.9, 1.1, 0.6, 24]" />
      <TresMeshStandardMaterial :color="C.metal" :metalness="0.4" :roughness="0.6" />
    </TresMesh>
    <TresMesh :position="[0, 2.3, 0]" cast-shadow>
      <TresCylinderGeometry :args="[0.06, 0.22, 3.6, 8]" />
      <TresMeshStandardMaterial :color="C.metalLight" :metalness="0.7" :roughness="0.3" />
    </TresMesh>
    <TresMesh :position="[0, 4.2, 0]">
      <TresSphereGeometry :args="[0.16, 16, 16]" />
      <TresMeshStandardMaterial :color="props.onAir ? C.orange : C.dim" :emissive="props.onAir ? C.orange : '#000'" :emissive-intensity="1.2" />
    </TresMesh>
    <TresMesh v-for="i in 3" :key="'ring' + i" :ref="setRing(i - 1)" :position="[0, 4.2, 0]" :rotation="[Math.PI / 2, 0, 0]">
      <TresTorusGeometry :args="[1, 0.035, 6, 48]" />
      <TresMeshBasicMaterial :color="C.orange" :transparent="true" :opacity="0" />
    </TresMesh>
    <!-- one orb per listener, orbiting the mast -->
    <TresMesh v-for="i in Math.min(props.listeners, 24)" :key="'lis' + i" :position="[Math.cos(i * 1.7) * (1.6 + (i % 3) * 0.4), 1.4 + (i % 4) * 0.5, Math.sin(i * 1.7) * (1.6 + (i % 3) * 0.4)]">
      <TresSphereGeometry :args="[0.11, 12, 12]" />
      <TresMeshStandardMaterial :color="C.white" :emissive="C.white" :emissive-intensity="0.8" />
    </TresMesh>
    <Html :position="[0, 5.0, 0]" center>
      <div class="lbl">The Transmitter <span>Icecast · {{ props.listeners }} listening</span></div>
    </Html>
    <Html :position="[0, 1.05, 1.15]" center transform :distance-factor="2.2">
      <div class="neon">NOT A BOT <small>(mostly)</small></div>
    </Html>
  </TresGroup>

  <!-- ===== The Drone (the station manager) ===== -->
  <TresGroup ref="drone" :position="[5, 3.4, 3]">
    <TresMesh>
      <TresBoxGeometry :args="[0.5, 0.16, 0.5]" />
      <TresMeshStandardMaterial :color="C.metalLight" :metalness="0.6" />
    </TresMesh>
    <TresMesh v-for="s in [[-0.3, -0.3], [0.3, -0.3], [-0.3, 0.3], [0.3, 0.3]]" :key="'rot' + s[0] + s[1]" :position="[s[0], 0.12, s[1]]" :rotation="[0, 0, 0]">
      <TresCylinderGeometry :args="[0.16, 0.16, 0.02, 12]" />
      <TresMeshStandardMaterial :color="C.cyan" :transparent="true" :opacity="0.55" />
    </TresMesh>
    <TresMesh :position="[0, -0.16, 0]">
      <TresSphereGeometry :args="[0.07, 10, 10]" />
      <TresMeshStandardMaterial :color="C.amber" :emissive="C.amber" :emissive-intensity="1" />
    </TresMesh>
    <TresPointLight :position="[0, -0.3, 0]" :intensity="3" :color="C.amber" :distance="5" />
    <Html :position="[0, 0.5, 0]" center>
      <div class="lbl small">The Manager <span>monitor round every 5 min</span></div>
    </Html>
  </TresGroup>

  <!-- ===== Packets on the tubes ===== -->
  <TresMesh v-for="i in POOL" :key="'pk' + i" :ref="setPacket(i - 1)" :position="[0, -5, 0]" :visible="false">
    <TresSphereGeometry :args="[0.12, 12, 12]" />
    <TresMeshStandardMaterial :color="C.cyan" :emissive="C.cyan" :emissive-intensity="1.4" />
  </TresMesh>

  <!-- ===== Commentary, beside whoever said it ===== -->
  <template v-for="key in ['dj', 'director', 'producer', 'bank', 'monitor']" :key="'bub' + key">
    <Html
      v-if="bubbleFor(key)"
      :position="[ANCHOR[key === 'director' ? 'hub' : key === 'bank' ? 'library' : key === 'monitor' ? 'monitor' : key][0], ANCHOR[key === 'director' ? 'hub' : key === 'bank' ? 'library' : key === 'monitor' ? 'monitor' : key][1] + 1.35, ANCHOR[key === 'director' ? 'hub' : key === 'bank' ? 'library' : key === 'monitor' ? 'monitor' : key][2]]"
      center
    >
      <div class="bubble" :class="key">{{ bubbleFor(key)?.text }}</div>
    </Html>
  </template>
</template>

<style scoped>
.lbl { font: 600 11px/1.2 "IBM Plex Mono", ui-monospace, monospace; color: #f4efe6; text-transform: uppercase; letter-spacing: .08em; white-space: nowrap; text-shadow: 0 1px 8px rgba(0,0,0,.9); pointer-events: none; }
.lbl span { display: block; font-weight: 400; text-transform: none; letter-spacing: 0; color: #a69c8e; font-size: 10px; margin-top: 2px; }
.lbl.small { font-size: 11px; }
.sign { font: 900 12px/1 "Archivo Black", "Archivo", sans-serif; letter-spacing: .12em; color: #5a1a22; pointer-events: none; }
.sign.lit { color: #fff; text-shadow: 0 0 10px #ff2e4a, 0 0 22px #ff2e4a; }
.sticker { font: 600 8px/1 "IBM Plex Mono", monospace; color: #1a1a00; background: #e9d829; padding: 3px 5px; border-radius: 2px; transform: rotate(-6deg); white-space: nowrap; pointer-events: none; }
.tiny { font-size: 6px; color: #1a1a1a; background: #f4efe6; padding: 1px 3px; border-radius: 2px; white-space: nowrap; pointer-events: none; }
.mono { font-family: "IBM Plex Mono", monospace; }
.board { font: 500 8px/1.5 "IBM Plex Mono", monospace; color: #2b2622; background: #f4efe6; padding: 6px 8px; border: 3px solid #6b655b; width: 96px; pointer-events: none; }
.neon { font: 800 11px/1 "Archivo", sans-serif; color: #5eead4; letter-spacing: .1em; text-shadow: 0 0 8px #5eead4, 0 0 18px #5eead4; white-space: nowrap; pointer-events: none; }
.neon small { font-size: 8px; font-weight: 500; letter-spacing: 0; }
.bubble { max-width: 220px; font: 500 11px/1.35 "Archivo", sans-serif; color: #17130e; background: #f4efe6; border-radius: 10px; padding: 6px 9px; box-shadow: 0 4px 18px rgba(0,0,0,.5); pointer-events: none; }
.bubble.dj { border-left: 4px solid #ff6a00; }
.bubble.director { border-left: 4px solid #f4efe6; }
.bubble.producer { border-left: 4px solid #5eead4; }
.bubble.bank { border-left: 4px solid #b39ddb; }
.bubble.monitor { border-left: 4px solid #f5b642; }
</style>
