#!/usr/bin/env node
/**
 * Design-system audit. Fails on the things that made the UI look inconsistent,
 * so they cannot come back quietly.
 *
 *  1. Hardcoded palette colours (bg-green-100, text-slate-500, ...). A colour
 *     with meaning belongs in tailwind.css as a token; 84% of the hardcoded
 *     ones had no dark-mode variant, which is why dark mode looked wrong.
 *  2. Page containers outside the two archetypes — use <PageShell>.
 *  3. Headings outside the scale.
 *
 * Run: node scripts/audit-frontend.mjs
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

const ROOT = new URL('..', import.meta.url).pathname
const PAGES = join(ROOT, 'app/pages')
const COMPONENTS = join(ROOT, 'app/components')

/** shadcn primitives are vendored upstream code; we do not restyle them. */
const EXCLUDE = [join(COMPONENTS, 'ui')]

const PALETTE =
  'slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose'
const COLOR_RE = new RegExp(`\\b(?:bg|text|border|ring|from|to|via)-(?:${PALETTE})-\\d{2,3}\\b`, 'g')
const CONTAINER_RE = /<div class="[^"]*\b(?:container|max-w-\d?xl|max-w-screen-\w+)\b[^"]*"/g
const H1_RE = /<h1[^>]*class="([^"]*)"/g
const ALLOWED_H1 = ['text-base', 'text-lg', 'text-xl', 'text-2xl']

/**
 * Comments are not styling. A note explaining why `bg-green-100` was wrong is
 * not itself a violation, and flagging it would push people to stop writing
 * the explanation.
 */
function stripComments(src) {
  return src
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1')
}

function walk(dir) {
  const out = []
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (EXCLUDE.some(e => p.startsWith(e))) continue
    if (statSync(p).isDirectory()) out.push(...walk(p))
    else if (p.endsWith('.vue')) out.push(p)
  }
  return out
}

const problems = []
for (const file of [...walk(PAGES), ...walk(COMPONENTS)]) {
  const raw = readFileSync(file, 'utf8')
  const src = stripComments(raw)
  const rel = relative(ROOT, file)

  for (const m of src.matchAll(COLOR_RE)) {
    const line = src.slice(0, m.index).split('\n').length
    problems.push({ rel, line, kind: 'palette', detail: m[0] })
  }
  if (rel.startsWith('app/pages')) {
    for (const m of src.matchAll(CONTAINER_RE)) {
      const line = src.slice(0, m.index).split('\n').length
      problems.push({ rel, line, kind: 'container', detail: 'use <PageShell>' })
    }
    for (const m of src.matchAll(H1_RE)) {
      const sizes = m[1].split(/\s+/).filter(c => /^text-(xs|sm|base|lg|[0-9]?xl)$/.test(c))
      const bad = sizes.filter(s => !ALLOWED_H1.includes(s))
      if (bad.length) {
        const line = src.slice(0, m.index).split('\n').length
        problems.push({ rel, line, kind: 'heading', detail: bad.join(' ') })
      }
    }
  }
}

const byKind = problems.reduce((a, p) => ((a[p.kind] = (a[p.kind] || 0) + 1), a), {})
if (!problems.length) {
  console.log('✓ frontend audit clean')
  process.exit(0)
}

for (const p of problems.slice(0, 60)) {
  console.log(`  ${p.rel}:${p.line}  ${p.kind}: ${p.detail}`)
}
if (problems.length > 60) console.log(`  … and ${problems.length - 60} more`)
console.log(`\n✗ ${problems.length} problem(s): ${JSON.stringify(byKind)}`)
process.exit(1)
