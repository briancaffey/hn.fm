# Plan 11 — The agentic script room

**Milestone 4.** Replace the single script call with a small crew of specialised
agents, and replace the script *string* with a structured script *object*.

## What's wrong with the current script

`generate_script_v1` is one prompt asking for "a natural, engaging podcast script".
Reading six recent outputs back-to-back, the failure modes are consistent:

- **Every episode opens the same way** — "Welcome to the podcast", "Hey folks,
  welcome back" — with an *invented show name that changes every time*: "Proof
  Positive", "DevOps Digest", "Breaking Discoveries". No brand, and a viewer who
  watches two videos sees two different shows.
- **Rigid ping-pong.** `[S1]`/`[S2]` alternate on literally every line for the whole
  script. No monologue runs, no rhythm, no one ever finishes a thought.
- **No arc.** Lines are summary sentences in source order. There's no cold open, no
  turn, no payoff — the listener is never told why to keep listening.
- **No grounding discipline.** See plan 8: one script invented an institution and
  labelled its own guesses `[SPECULATIVE FOR SCRIPT FLOW]`.
- **Sections are an accident.** `split_script_into_sections` chunks *every two lines*.
  Since a section is the atomic unit of visuals and timing, visual pacing is currently
  decided by a line counter.

## The crew

Sequential agents over the Story Brief (plan 9), each with a narrow job and a
structured contract (plan 8). Text-stage LLM calls are cheap next to image/LTX GPU
time, so depth here is affordable.

| Agent | Input | Output |
|---|---|---|
| **Showrunner** | brief | beat sheet: cold open → context → turn → detail → implication → close, with an assigned duration and purpose per beat |
| **Writer** | beat sheet + brief | draft script sections against the beats |
| **Fact-checker** | draft + brief | every claim traced to `key_facts` / `comment_insights`, or flagged. Unsupported claims are cut or hedged — `brief.unknowns` is the authority on what we do *not* know |
| **Script doctor** | checked draft | rhythm and voice pass: kill the generic open, vary speaker runs, tighten, add the hook, enforce the comment-attribution rules from plan 10 |
| **Formatter** | final | strict machine contract; validation failure re-prompts rather than shipping malformed tags |

A **critic** pass scoring the result against the taste rubric already exists for the
media plan (`meta_sequencer._critic_revise`) — reuse that shape here rather than
inventing a second pattern.

## The structured script

The stage's output stops being a blob of text:

```jsonc
{
  "hook": "the first 5 seconds, written deliberately",
  "sections": [
    { "index": 1,
      "beat": "cold_open|context|turn|detail|implication|close",
      "speaker": "S1|S2|both",
      "text": "spoken words only, TTS-clean",
      "provenance": { "source": "article|comment|inference",
                      "hn_user": null, "comment_id": null, "confidence": 90 },
      "visual_intent": "what this beat needs to SHOW",
      "emphasis": ["the words that should hit"] }
  ],
  "cta": "..."
}
```

Three consequences worth naming:

1. **`split_script_into_sections` retires.** The writer decides boundaries, so section
   breaks land on meaning. Visual pacing improves for free, everywhere downstream.
2. **`visual_intent` is the bridge to plan 13.** The storyboard agent stops guessing
   what a line is about from the line alone.
3. **`provenance` makes plan 10's attribution auditable** and renderable on screen.

Keep `[S1]`/`[S2]` rendering for the TTS layer — Magpie's dual-voice split reads those
tags — but generate them from `speaker` rather than asking the LLM to emit them.

## Show identity

Fix the invented-show-name problem in config, not in the prompt: one show name, one
sign-off, a small rotating set of cold-open patterns, and an explicit ban on
"Welcome to the podcast". Put it in `config.yaml` under `show:` so it's tunable
without a deploy — the same treatment the triage rubric already gets.

## Tasks

- [ ] `content/script_room.py` — the five agents over a structured `ScriptDraft`
- [ ] Structured script schema + `segments.script_json` column (keep `script` text as
      the rendered TTS view, generated from the object)
- [ ] Fact-checker: every claim resolves to a brief fact or is cut/hedged; unresolved
      claims recorded on the step for inspection
- [ ] Retire `split_script_into_sections` in favour of writer-decided sections
      (`build_segment_audio` and `build_segment_images` both consume it — migrate both)
- [ ] `show:` identity block in `config.yaml`; cold-open pattern rotation
- [ ] Script-room prompts in the plan 8 registry, versioned from day one
- [ ] Segment UI: show beats, provenance and the fact-checker's verdict per section
