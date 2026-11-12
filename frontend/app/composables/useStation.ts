/**
 * What the station's pages share: the shapes the radio API returns and the
 * few ways of writing a time, a length and a name.
 */
export interface Line { speaker: string, mood: string, text: string }
export interface Cue { n: number, at: number, seconds: number }
export interface RundownItem {
  at: number, seconds: number, segment: string, name?: string | null, title?: string | null
  story?: number | null, host?: string | null, text?: Line[] | null, lyrics?: string | null
  cues?: Cue[] | null, qa?: { match?: number | null } | null
}
export interface Edition {
  id: string, kind?: string, title: string | null, show: string, show_name: string, tagline?: string
  anchor?: string, cohost?: string, date: string, aired_at: string, seconds: number | null
  stories: { item_id: number, title: string | null }[], featured?: boolean, video?: boolean
  rundown?: RundownItem[], stats?: Record<string, number>
}
export interface Show {
  key: string, name: string, tagline: string, anchor: string, cohost: string
  start: number, end: number, on_air?: boolean
}
export interface Character {
  key: string, name: string, role: string, line: string, beat: string, moods: string[], shows: string[]
}
export interface NowPlaying {
  id: number, at: string, kind: string, title: string | null, segment?: string | null, name?: string | null
  host?: string | null, text?: Line[] | null, lyrics?: string | null, item_id?: number | null
}
export interface StationStatus {
  enabled: boolean, now: NowPlaying | null, show?: Show, schedule?: Show[]
  icecast: { up: boolean, mounts?: { listeners: number }[] }
  produce?: { mode: string, producing: boolean }
  bank?: Record<string, number>
}

export function useStation() {
  const apiBase = useRuntimeConfig().public.apiBase as string
  const art = (key?: string | null) => `${apiBase}/api/radio/art/${key || 'station'}.jpg`
  const audio = (id: string) => `${apiBase}/api/radio/archive/${id}.mp3`
  const cap = (s?: string | null) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '')
  const speaker = (s: string) => (s.startsWith('caller') ? `Line ${s.replace('caller', '')}` : cap(s))
  const hour = (h: number) => `${h % 12 || 12}${h < 12 ? 'am' : 'pm'}`
  const mins = (s?: number | null) => (s ? `${Math.max(1, Math.round(s / 60))} min` : '')
  const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
  /** "Thu 12 Nov", from the edition's own date so it does not move with the reader's timezone. */
  const day = (date: string) => {
    const [y, m, d] = date.split('-').map(Number)
    return new Date(Date.UTC(y || 2026, (m || 1) - 1, d || 1))
      .toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })
  }
  /** The address to paste into a player: whole, even behind the ingress. */
  const streamUrl = computed(() => {
    try {
      const u = new URL(apiBase)
      if (u.hostname === 'localhost' || u.hostname === '127.0.0.1') return 'http://localhost:8010/hnfm.mp3'
      return `${u.origin}/radio/hnfm.mp3`
    } catch { return '/radio/hnfm.mp3' }
  })
  return { apiBase, art, audio, cap, speaker, hour, mins, clock, day, streamUrl }
}
