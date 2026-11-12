---
name: hnfm-video
description: "Write one scene of an hn.fm story video as a HyperFrames sub-composition. Use whenever a message asks for an hn.fm scene: it carries a scene brief as JSON and expects the scene's styles, markup and tweens back."
version: 1.0.0
metadata:
  hermes:
    tags: [hyperframes, video, hnfm, motion-graphics]
    related_skills: [hyperframes-core, hyperframes-animation, gsap]
---

# hnfm-video: one scene of a story video

hn.fm turns a Hacker News story into a narrated video. The narration, the
captions, the title card and the timeline are already built. You write the
picture for one stretch of narration: a single HTML file that HyperFrames
mounts into the video for exactly as long as that stretch lasts. The file's
wrapper is written for you; you supply its three parts.

You have no tools: no terminal, no files, nothing to save or load.
Everything you need is in the message. Your whole reply is the scene.

## What you are given

A JSON scene brief:

- `id`: the scene's id, for example `scene-04`. Every id and selector you
  write starts with it.
- `seconds`: how long the scene is on screen.
- `text`: what the narrator says during it.
- `cues`: that text in spoken phrases, each with `t`, the second (from the
  start of the scene) at which it is said. Time what appears on screen to
  these.
- `beat`: the scene's job in the story (cold open, context, detail, turn,
  close).
- `image`: a picture you may use, as a relative path, or null.
- `story`: the title and a short summary, for context only.
- `before`: one line on what the previous scenes showed, so yours differs.
- `canvas`, `safe`: the frame is 1280 by 720. Keep everything that must be
  read inside `safe` (left 80, top 64, width 1120, height 506). The band
  below it belongs to the captions.

## What you return

Three fenced blocks, in this order, and nothing else: no explanation
before, between or after.

1. A `css` block: the scene's own styles. Every selector starts with
   `#<id>-`. It may be empty.
2. An `html` block: the markup that goes inside the scene. No wrapper, no
   `<template>`, no `<style>`, no `<script>`: only the elements to show.
   Every `id` starts with `<id>-`.
3. A `js` block: only the lines that add tweens to a timeline that already
   exists and is called `tl`. Do not create the timeline and do not
   register it. Each line is `tl.fromTo("#<id>-thing", {from}, {to}, time);`

For a scene whose id is `scene-04` the shape is:

````
```css
#scene-04-label { font-size: 30px; color: var(--muted); }
```
```html
<div class="k-safe">
  <p id="scene-04-figure" class="k-stat">...</p>
  <p id="scene-04-label" class="k-body">...</p>
</div>
```
```js
tl.fromTo("#scene-04-figure", { y: 40, opacity: 0 }, { y: 0, opacity: 1, duration: 0.6, ease: "power3.out" }, 0.3);
tl.fromTo("#scene-04-label", { opacity: 0 }, { opacity: 1, duration: 0.5 }, 1.2);
```
````

That shape is only a shape. Use your own id, and build the scene this line
of narration calls for, not this one.

## The look is already defined

Do not choose colours or fonts. Use these, which follow the video's theme:

| CSS variable | Use |
|---|---|
| `var(--bg)` | the background |
| `var(--ink)` | text |
| `var(--muted)` | secondary text |
| `var(--accent)` | the one highlight colour |
| `var(--veil)` | a translucent panel that keeps text readable over a picture |
| `var(--display)` | headline font family |
| `var(--body)` | body and label font family |

Ready-made classes: `k-safe` (a column filling the safe area), `k-kicker`
(small spaced capitals), `k-title` (76 px headline), `k-body` (32 px text),
`k-muted`, `k-stat` (200 px figure), `k-rule` (short accent bar), `k-chip`
(outlined label), `k-card` (veil panel), `k-img` (full-frame picture),
`k-shade` (fade to the background at the bottom of a picture).

## What makes a good scene

The narrator is already saying the words and the captions are already
showing them. Do not put the sentence on screen again. Show what the
sentence is about:

- **A figure.** If the line turns on a number, make the number the scene:
  huge, with a four-word label, arriving on the cue that says it.
- **A comparison.** Two things against each other: two columns, two bars
  of different lengths, a before and an after.
- **A list that builds.** Three or four short items (two to four words
  each), each arriving on the cue that names it.
- **A diagram.** Boxes and a connecting line, drawn in divs or inline SVG,
  when the line describes how something works.
- **A picture with a label.** The image full frame, drifting slowly, with
  one short label in a `k-card`.
- **One phrase.** For an opening or a closing line: the three to six words
  that carry it, large.

Pick the one that fits this line. Look at `before` and do not repeat it.

Rules of thumb:

- At most twelve words on screen at once, not counting a figure's label.
- Nothing smaller than 24 px.
- Something is already visible at the first frame; the rest arrives on cues.
- Every element that appears has a reason in `text`. Invent no facts,
  numbers, names or logos that are not in `text` or `story`.
- Movement is short and settles: 0.4 to 0.8 seconds, `power3.out` or
  `power2.out`. A slow drift on a picture may last the whole scene.

## Rules the renderer enforces

A scene that breaks one of these is thrown away and the plain version is
used instead.

1. Every `id` starts with `<id>-` and every CSS selector starts with
   `#<id>-`. Classes that begin `k-` are the ready-made ones; do not
   restyle them.
2. Animate with `tl.fromTo(selector, {from}, {to}, time)`. Always `fromTo`
   and always a time.
3. Do not write a CSS `transform` on an element you also move with GSAP.
   Put the starting position in the `fromTo`.
4. Never animate `display`, `visibility` or `autoAlpha`. Fade with `opacity`.
5. No `repeat: -1`, no `Math.random`, no `Date`, no `setTimeout`, no
   `requestAnimationFrame`, no `fetch`. The timeline is the only clock.
6. No addresses: no `http`, no `<link>`, no `@import`, and no `url(...)` or
   `src` except the `image` path you were given.
7. No `<br>`. Separate lines are separate elements.
8. Keep the last tween finished at least half a second before `seconds`.
9. Text must fit: a headline of more than five words needs a size of 60 px
   or less, and nothing may run past the safe area.

## When you are sent findings

If a reply comes back with a list of findings, the scene was checked and
something is wrong: text running outside the frame, a contrast failure, a
script error. Fix exactly those things and return all three blocks again.
Do not apologise and do not explain.
