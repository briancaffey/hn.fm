# Plan 8 — LLM foundation: structured output, versioned prompts, loud failures

**Milestone 1.** Everything in plans 9–15 is a prompt. You cannot improve prompts you
cannot version, diff, replay, or A/B. This plan makes the LLM layer trustworthy so the
content work that follows is measurable rather than vibes.

## Why this is first

Three concrete problems in the current layer, all found in live output:

1. **Silent fallback swallows failures.** `LLMService.generate_content` catches every
   exception and returns `_generate_fallback_content()` → the literal string
   `"[S1] This is a fallback, error generating script"`. A dead LLM produces a
   *successful* run with a one-line garbage script. Every downstream stage (TTS,
   images, video) then burns GPU time on it.
2. **No output contract.** `generate_script_v1` sends one f-string and trusts prose
   back. Real output from item 48747304 run 2 leaked markdown headers, `**[S1]**`
   (bold markers break the `[S1]` parser in `split_script_into_sections`), literal
   `**[SPECULATIVE FOR SCRIPT FLOW]**` annotations, and an invented institution
   ("*Let's speculate: University of California, San Diego*"). That fabrication would
   have been narrated aloud as fact.
3. **Every consumer regex-scrapes JSON out of prose.** `triage._extract_json`,
   `meta_sequencer._parse_json_list`, `sequence_planner`'s `re.search(r"\[.*\]")` —
   three independent tolerant-parsers, each with its own silent-failure path.

## Design

### Structured output as the default call
Add `LLMService.generate_structured(prompt, schema, *, model=None, temperature=None,
max_tokens=None) -> dict`, using OpenAI-compatible `response_format={"type":
"json_schema", ...}` where the route supports it, with a validate-and-retry loop
(re-prompt with the validation error) as the portable fallback. Pydantic models
define the schemas. Retire the three ad-hoc extractors in favour of this one path.

⚠️ **Verify first:** confirm the LiteLLM gateway route (`nvidia-nemotron-super`)
honours `json_schema`; if not, the retry loop carries it. Probe with the real key
from `.env` — an unauthenticated `GET /v1/models` returns 401.

### Per-task model profiles
One model at `temperature=0.7, max_tokens=2000` currently serves triage, summary,
haiku, script, image prompts, and the director. Add a `llm_profiles:` block in
`config.yaml` keyed by task (`script.write`, `script.factcheck`, `art.storyboard`,
`triage.score`, …), each with model / temperature / max_tokens / reasoning setting.
Free-and-local constraint stays; this is about right-sizing, not spending.

### Prompt registry
Prompts move out of Python string literals into `prompts/` (YAML, one file per task,
with a `version` field), loaded through a `PromptRegistry`. Every `pipeline_steps`
row records `prompt_name` + `prompt_version` alongside the existing model/token
fields. This is what makes "did my new script prompt actually help?" answerable —
plan 14 depends on it.

### Fail loudly, degrade deliberately
Delete `_generate_fallback_content`. Replace with an explicit policy per call site:
- **fatal** (script, image prompt) — raise; the step fails and is visible in the
  audit trail and re-runnable via `rerun_step`.
- **cosmetic** (emoji, haiku, tags) — keep the existing `_safe()` defaults in
  `process_hn_item_run`, which already do this correctly.

## Tasks

- [x] `LLMService.generate_structured()` + Pydantic schemas (`content/llm_schemas.py`)
      + validate/retry loop that feeds the validation error back
- [x] `llm.profiles:` config block; `task` threaded through every call site
- [x] `PromptRegistry` (`content/prompts.py`) reading versioned YAML from `prompts/`;
      all six existing prompts migrated, plus a new `summary.write`
- [x] Record `prompt_name` / `prompt_version` on `pipeline_steps` (Alembic 0004);
      surfaced in the X-ray timeline
- [x] Remove `_generate_fallback_content`; per-call-site fatal/cosmetic policy
- [x] Port `triage`, `meta_sequencer`, `sequence_planner` off their bespoke JSON parsers
- [x] **Model allowlist** (`content/model_policy.py`) — not in the original plan. The
      gateway advertises 221 routes including groq and ~200 `lmstudio/*` OpenAI-catalog
      entries. Checked before the request *and* against the served model, which is what
      catches silent server-side failover
- [x] Delete the dead `content/image_prompt_generator.py` legacy path, and the
      now-unreferenced `image_generation.default_style` config it read
- [x] Strip `**`, markdown headers and leaked meta-commentary in `_clean_script_for_tts`
      as a belt-and-braces guard even after the contract lands

### Landed with this milestone but belonging to later plans

- [x] **Structured script** (plan 11's foundation): `Script` / `ScriptSection` with
      writer-chosen boundaries, `beat` and `visual_intent`; `segments.script_json`.
      `split_script_into_sections` survives only as the fallback for pre-0004 segments
- [x] `visual_intent` threaded into image prompts (plan 13's input)
- [x] `script_quality_flags()` — deterministic detection of gap-narration,
      undepictable visual intents and strict speaker alternation (plan 14's first
      checks), recorded on the script step

### Verified against the live gateway (2026-08-16)

- `nvidia-nemotron-super` honours `json_schema` including enums, at temperature 0.8
- **`nemotron-omni` needs `chat_template_kwargs.enable_thinking=false` even with a
  schema** — without it, content is null and everything lands in `reasoning_content`.
  `nvidia-nemotron-super` does not need this. Both options compose fine
- **The vision sequence planner was silently falling back on every run.** It used
  `LLM_MODEL` (a text-only, cloud-routed model) and the gateway's rampart PII guard
  fail-closes on image payloads to it with a 500. Pinned to `nemotron-omni`

## Known-remaining (deliberately deferred)

- The script writer still occasionally narrates source gaps ("the institution is not
  disclosed") and writes undepictable visual intents on very thin sources. Two prompt
  revisions did not eliminate it; both are now *detected* rather than prompted away.
  The real fix is upstream — plan 9's `producibility` score should stop a 214-character
  scrape reaching the script stage at all.
- `sequence.plan` output still drifts toward lighting changes, which its own prompt
  forbids. That is a model-capability limit; plan 13's frame critic is the answer.
