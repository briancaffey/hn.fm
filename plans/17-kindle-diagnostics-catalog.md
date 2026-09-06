# Kindle correctness, diagnostics, image catalog, and the X-ray redesign

## A. The Kindle metadata bug (first, it is a regression I reported as fixed)

Diagnosis, not a guess:
- The three illustrated files on disk DO carry `<title>Name · 9/5</title>`,
  `<meta name="author" content="hn.fm">` and a cover div. The narrative one
  does not — it was built before the fix and I sent the stale file.
- But that is not why the device shows the old style. **Amazon's HTML path
  ignores `<meta name="author">` (hence "Unknown"), takes the document title
  from the attachment FILENAME, and will not treat an inline `<img>` as a
  cover.** Sending `hnfm-digest-2026-09-05-illustrated.html` produces exactly
  the title the device is showing.
- Provider cannot change: Brevo rewrites the From to the brevosend address,
  and *that* address is the one on Amazon's approved list. Switching providers
  silently stops delivery.
- Brevo rejects `.epub` — verified again, `Unsupported file format: epub`.
- **Brevo accepts `.docx` — verified, 201.** DOCX carries `dc:title` and
  `dc:creator` in `docProps/core.xml`, embeds images, and Amazon reflows it.

So: emit DOCX for the Kindle, keep HTML for the browser, and attach it under a
human filename.

## B. Diagnostics
Collect models, token counts and timings per phase (research/brief, digest
prose, image prompts, images) and per story. Render as a closing section in the
digest, and as a page in the web UI.

## C. Image catalog
Persist every generated image — digest inline, cover, and segment/video — with
its full prompt, style, technique, model and dimensions. Browsable, filterable
by type, sortable. Grow the style library beyond twelve.

## D. Story source
Record whether an item arrived from `top` or `new`; filter on it.

## E. Voices
More than one TTS voice, assigned per speaker, recorded per section and shown
on the segment page.

## F. Segment detail redesign
It never got the overhaul: no header, no breadcrumb consistency, an awkward
collapse pattern, x-ray showing image links instead of images, the finished
video buried at the bottom, and the browser default audio player. Rebuild it
compact, with a custom player and the video pinned top-right.

## G. Content
Review the latest 20 `new` submissions, judge how many are actually suitable,
build a digest from only those, and generate two videos.
