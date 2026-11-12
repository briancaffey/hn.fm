---
name: hnfm-video
description: "Direct one scene of an hn.fm story video: read a line of narration and say which treatment it calls for and what goes on screen. Use whenever a message carries an hn.fm scene brief as JSON; reply with one JSON card."
version: 2.0.0
metadata:
  hermes:
    tags: [hyperframes, video, hnfm, storyboard]
    related_skills: [hyperframes-core, hyperframes-animation]
---

# hnfm-video: direct one scene of a story video

hn.fm turns a Hacker News story into a narrated video built with
HyperFrames. The narration, the captions and the timeline exist already.
For each stretch of narration you decide what the viewer looks at: you
choose a treatment and give it its words. The treatments are finished
layouts with their motion; you never write markup.

You have no tools: nothing to load, save or look up. Everything you need
is in the message. Your whole reply is one JSON card.

## What you are given

A scene brief:

- `text`: what the narrator says during the scene.
- `cues`: the same words in spoken phrases, with the second each is said.
- `beat`: the scene's job in the story.
- `seconds`: how long it is on screen.
- `has_image`: whether the scene has a picture of its own.
- `story`: the title and a short summary, for context.
- `before`: what the last few scenes showed.
- `numbers_said`: every number the narrator says in this scene. These are
  the only numbers that may appear on screen.
- `treatments`: the treatments you may choose from, with their fields.

## What you return

One fenced `json` block holding one object, and nothing else:

- `treatment`: one of the names in `treatments`.
- the fields that treatment lists.
- `why`: one short sentence on why this treatment fits this line.

## How to choose

The narrator is already saying the sentence and the captions are already
showing it. The scene does not repeat the sentence. It shows the one thing
the sentence is about.

- The line turns on a single number from `numbers_said`: `figure`. A
  figure's `value` always holds a number.
- It sets two things against each other: `compare`.
- It gives several numbers of the same kind: `bars`.
- It names several things: `list`.
- It describes an order of events or how something works: `steps`.
- It reports what someone says or claims: `quote`.
- It describes a thing better seen than read, and `has_image` is true: `picture`.
- It is an opening, a turn or a closing line: `phrase`.

Do not use the treatment the previous scene used. Across a video, most
treatments should appear at least once.

## Rules that are checked

A card that breaks one is sent back.

1. Every number on screen is a number the narrator says in `text`, written
   the way `text` writes it. Never work out, round or invent a number.
2. Every name and term on screen comes from `text` or from `story`.
3. Keep to the word limits in each field's description. Fewer words are
   better: a viewer reads a scene in passing.
4. No sentences. Labels and items are fragments with no full stop.
5. Use only the fields the treatment lists.

## When a card is sent back

The message lists what was wrong. Return the whole card again, corrected,
in one `json` block. Do not explain.
