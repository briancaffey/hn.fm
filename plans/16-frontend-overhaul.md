# Frontend overhaul

## What's actually wrong (measured, not guessed)

- **374 hardcoded palette colors** across pages/components, and only 28 `dark:`
  variants against 174 light-mode usages — **~84% have no dark-mode
  counterpart**. `bg-green-100 text-green-800` on a dark page is a pale chip
  with near-black text. This is the "looks bad sometimes".
- **7 different page containers**: `container mx-auto p-6`, `mx-auto max-w-7xl
  p-4`, `w-full px-4 py-8`, `container mx-auto px-4 py-8`, full-bleed sticky,
  `max-w-2xl`, `container mx-auto px-4 py-3`.
- **4 different h1 sizes**: `text-lg`, `text-xl`, `text-3xl`, `text-6xl`.
- **Context is absent or generic.** Stories and Segments have no description at
  all. Services says "Monitor the health and availability of all pipeline
  services." Digests is the only page that explains *why* you'd care.
- **Stage colours defined twice**, differently, in `live.vue` and
  `observability.vue`.
- **Landing page is a "Coming soon..." placeholder** with two dead buttons.
- Dead routes: `test-api.vue`, `hn/test-detail.vue`.
- No loading skeletons — pages flash empty, then fill.
- No breadcrumbs on the 3-level-deep detail routes.

## Principles

1. **Every surface explains itself.** Each page gets a one-line "what this is",
   and each non-obvious column/metric/badge gets a hover definition. The test:
   could someone who has never seen the pipeline tell what they're looking at
   and why it matters?
2. **Tokens, not palette classes.** A colour with meaning (ok / running /
   error / stale / a pipeline stage) is a token, defined once, correct in both
   modes by construction.
3. **Two page archetypes, deliberately.** `board` (full-bleed, sticky header,
   dense table — Stories, Triage, Segments) and `document` (centred, max-width
   — Digests, Services, Observability, Live, detail pages). Nothing else.
4. **State is never blank.** Loading → skeleton. Empty → explains what would
   fill it and how. Error → says what failed and offers a retry.

## Phase 0 — Design foundation
- Extend `tailwind.css`: semantic status tokens (ok/running/error/warn/idle/
  stale), the 10 pipeline-stage hues, chart series, and a real dark elevation
  ladder (background → card → elevated, not one flat grey).
- Typography scale + a `--page-gutter` so gutters match everywhere.

## Phase 1 — Shared primitives (`app/components/ui-kit/`)
`PageShell` (archetype + gutter), `PageHeader` (title, subtitle, actions,
breadcrumbs), `InfoHint` (the "why this matters" tooltip), `StatusDot` /
`StatusBadge` (token-driven), `StatTile`, `EmptyState`, `LoadingSkeleton`,
`StageBadge`, `MetricPair`.

## Phase 2 — Pages
Landing · Stories · Triage · Segments · Digests · Live · Observability ·
Services · Story detail · Run detail · Segment detail · Compare. Delete the two
test routes.

Per page: adopt archetype, real title + context line, hints on every
non-obvious element, token colours only, skeleton + empty + error states,
verified in both modes.

## Phase 3 — Cross-cutting
Sidebar grouping and per-item descriptions; breadcrumbs on detail routes;
consistent focus rings and keyboard access.

## Phase 4 — Validation
- `scripts/audit-frontend.mjs`: fails on hardcoded palette colours, on a page
  container outside the two archetypes, and on an h1 outside the scale.
- `yarn lint` clean, backend suite green, every route 200 in both modes.
