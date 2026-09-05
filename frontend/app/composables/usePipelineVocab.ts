/**
 * One definition of what the pipeline's words mean.
 *
 * Status and stage colours used to be declared per page — `live.vue` and
 * `observability.vue` each had their own stage map, with different values, so
 * the same stage was two different colours depending on where you looked.
 * The glossary was nowhere: a reader had to already know what "producibility"
 * or "superseded" meant.
 */

export type StatusKey =
  | 'ok' | 'running' | 'error' | 'abandoned' | 'stale'
  | 'superseded' | 'partial' | 'gated' | 'queued' | 'idle'

interface StatusMeta {
  label: string
  /** Token group backing this status — see tailwind.css. */
  tone: 'ok' | 'running' | 'danger' | 'warn' | 'idle' | 'stale'
  /** Shown on hover. Says what the state means and what to do about it. */
  hint: string
}

export const STATUS: Record<StatusKey, StatusMeta> = {
  ok: {
    label: 'ok',
    tone: 'ok',
    hint: 'Finished and produced its output.',
  },
  running: {
    label: 'running',
    tone: 'running',
    hint: 'In flight right now. The Live page streams these as they change.',
  },
  error: {
    label: 'error',
    tone: 'danger',
    hint: 'Failed. Some failures are soft — the run continues without that piece.',
  },
  abandoned: {
    label: 'abandoned',
    tone: 'warn',
    hint: 'The worker died mid-step. Not a failure of the work itself, which is why it is counted separately from errors.',
  },
  stale: {
    label: 'stale',
    tone: 'stale',
    hint: 'Still valid, but something it depended on changed. Re-run to refresh it.',
  },
  superseded: {
    label: 'superseded',
    tone: 'stale',
    hint: 'A later run of the same step replaced this one. Kept for the audit trail.',
  },
  partial: {
    label: 'partial',
    tone: 'warn',
    hint: 'Finished without producing the artifact it exists to produce — no video or episode on disk.',
  },
  gated: {
    label: 'gated',
    tone: 'idle',
    hint: 'Stopped at the scrape gate: too little text to build a story from, so no LLM was spent on it.',
  },
  queued: {
    label: 'queued',
    tone: 'idle',
    hint: 'Waiting for a worker on its queue.',
  },
  idle: { label: 'idle', tone: 'idle', hint: 'Nothing happening.' },
}

export function statusMeta(raw?: string | null): StatusMeta {
  const key = (raw || 'idle').toLowerCase() as StatusKey
  return STATUS[key] ?? { label: raw || 'unknown', tone: 'idle', hint: 'Unrecognised state.' }
}

/** Tailwind classes for a status chip. Token-backed, so both modes are right. */
export function statusClasses(raw?: string | null): string {
  return {
    ok: 'bg-ok-bg text-ok border-ok-border',
    running: 'bg-running-bg text-running border-running-border',
    danger: 'bg-danger-bg text-danger border-danger-border',
    warn: 'bg-warn-bg text-warn border-warn-border',
    idle: 'bg-idle-bg text-idle border-idle-border',
    stale: 'bg-stale-bg text-stale border-stale-border',
  }[statusMeta(raw).tone]
}

/**
 * What each pipeline stage is for. Shown on hover wherever a stage appears, so
 * the pipeline is legible without reading the source.
 */
export const STAGE: Record<string, { label: string; hint: string }> = {
  scrape: { label: 'Scrape', hint: 'Fetch the linked article. YouTube and PDFs use dedicated readers; a failure falls back to the HN text.' },
  summary: { label: 'Summary', hint: 'One LLM pass that condenses the article. Everything downstream reads this, not the raw text.' },
  enrich: { label: 'Enrich', hint: 'Tags, emoji, short description and haiku. Runs only after triage passes, so duds do not pay for it.' },
  triage: { label: 'Triage', hint: 'Scores interest and producibility. The gate that decides whether a story is worth generating.' },
  brief: { label: 'Story Brief', hint: 'Framing, evidence and comment insights. What the script writer actually reads.' },
  script: { label: 'Script', hint: 'The two-host dialogue, in sections. Each section becomes one TTS call and one visual.' },
  audio: { label: 'Audio', hint: 'Text-to-speech per section, stitched, then transcribed back to check it against the script.' },
  images: { label: 'Images', hint: 'One scene per section. Each prompt sees the previous shots so a take holds its cast and setting.' },
  media_plan: { label: 'Media plan', hint: 'Chooses image sequence, motion clip or hyperframe per section, then critiques its own plan.' },
  video: { label: 'Video', hint: 'Assembles images, motion, captions and audio into the finished file.' },
  task: { label: 'Task', hint: 'A whole task that died outside any step — recorded so a crash cannot be invisible.' },
}

export function stageMeta(raw?: string | null) {
  const key = (raw || '').toLowerCase()
  return STAGE[key] ?? { label: raw || 'unknown', hint: '' }
}

/** Inline style for a stage's colour. Uses the shared token, not a local map. */
export function stageStyle(raw?: string | null) {
  const key = (raw || 'task').toLowerCase()
  const known = key in STAGE ? key : 'task'
  return { backgroundColor: `hsl(var(--stage-${known}))` }
}

/**
 * Definitions for the numbers the UI shows. A reader should not have to guess
 * what "rank" is made of or why "producibility" can be capped.
 */
export const GLOSSARY: Record<string, string> = {
  interest: 'How much a reader would care, 0-100. The model judges this from the story, not from HN points.',
  producibility: 'How much there is to actually build from, 0-100. Capped automatically when the scrape came back thin — a great headline with no article cannot score well.',
  rank: 'Interest weighted by producibility, topic match and HN score. What the digest and the queue sort by.',
  verdict: 'Derived from interest and producibility against configured thresholds, not asked of the model — it was bad at bucketing its own scores.',
  interest_match: 'Overlap between the story topics and your configured interest profile, -1 to 1.',
  tokens: 'LLM tokens in and out, summed from every step of the run.',
  llm_calls: 'How many model calls this run made. The cheapest lever on cost.',
  seconds: 'Wall-clock time across all steps. Render stages dominate.',
  run: 'One pass over a story. A second run re-scrapes and re-scores, giving a different take.',
  segment: 'One finished piece of content from a run — its own script, audio, images and video.',
  brief: 'The Story Brief: facts, comment insights, and what the source does NOT establish.',
}
