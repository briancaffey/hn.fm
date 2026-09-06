import html, json, os
from datetime import datetime

# Runs inside the web container, where the round JSON is mounted.
#   docker compose exec -T web python /tmp/build_report.py
#   docker cp ... hnfm-hyperframes:/tmp/report.html
#   chromium --headless --print-to-pdf --no-pdf-header-footer
# hyperframes is the only image in the stack that ships a chromium.
D = "/app/outputs/evals"
rounds = {}
for f in os.listdir(D):
    if f.endswith(".json"):
        rounds[f[:-5]] = json.load(open(os.path.join(D, f)))

def esc(x): return html.escape(str(x))

CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 10.5pt;
       line-height: 1.55; color: #1b1a1f; margin: 0; }
h1 { font-size: 26pt; line-height: 1.1; margin: 0 0 4pt; letter-spacing: -.5pt; }
h2 { font-size: 15pt; margin: 22pt 0 6pt; padding-bottom: 3pt;
     border-bottom: 1.5pt solid #1b1a1f; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt; page-break-after: avoid; }
.sub { font-size: 11pt; color: #55525c; margin: 0 0 4pt; }
.meta { font-size: 8.5pt; color: #77747e; text-transform: uppercase;
        letter-spacing: .09em; margin: 0 0 18pt; }
p { margin: 0 0 8pt; }
table { width: 100%; border-collapse: collapse; margin: 8pt 0 12pt;
        font-size: 9pt; page-break-inside: avoid; }
th { text-align: left; border-bottom: 1pt solid #1b1a1f; padding: 4pt 5pt;
     font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 8pt;
     text-transform: uppercase; letter-spacing: .06em; }
td { border-bottom: .5pt solid #ddd; padding: 4pt 5pt; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
.win { color: #1f6b3a; font-weight: bold; }
.lose { color: #96342b; font-weight: bold; }
.callout { border-left: 3pt solid #2E4A6B; background: #f4f6f9;
           padding: 8pt 11pt; margin: 10pt 0; page-break-inside: avoid; }
.callout p:last-child { margin-bottom: 0; }
code, .mono { font-family: 'SF Mono', Menlo, monospace; font-size: 8.5pt; }
.kicker { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 8pt;
          text-transform: uppercase; letter-spacing: .11em; color: #2E4A6B;
          font-weight: bold; margin: 0 0 3pt; }
.small { font-size: 8.5pt; color: #55525c; }
.pb { page-break-before: always; }
ul { margin: 0 0 9pt 14pt; padding: 0; }
li { margin: 0 0 4pt; }
"""

def row(label, *cells):
    return "<tr><td>" + esc(label) + "</td>" + "".join(
        f'<td class="n">{c}</td>' for c in cells) + "</tr>"

def g(lbl, key):
    v = (rounds.get(lbl, {}).get("summary") or {}).get(key)
    return f"{v:.3f}" if isinstance(v, float) else ("—" if v is None else str(v))

body = f"""
<p class="kicker">hn.fm · self-improvement cycle</p>
<h1>Measuring the prompts, not trusting them</h1>
<p class="sub">Three stories, seven regeneration rounds, four prompt revisions,
two reverts, and one new output format.</p>
<p class="meta">{datetime.utcnow():%d %B %Y} · branch <span class="mono">self-improve/prompt-evolution</span></p>

<div class="callout">
<p><strong>The one-line result.</strong> The complaint that started this — video
frames being "really good variations of the same image" — was not where it
appeared to be. The script's declared visual subjects were already
near-perfectly distinct (0.028 pairwise overlap); the art-director step turned
them into near-repetitive scenes (0.327). A ten-fold collapse, one step
downstream. Fixing it cut the share of frames containing a desk, laptop or
screen from <strong>0.413 to 0.315</strong>, confirmed at <strong>0.355 on real
end-to-end renders</strong>.</p>
</div>

<h2>Method</h2>
<p>Every metric is computed without a model and without a human, so a prompt
change is judged by whether a number moved rather than by whether the output
felt better. The three test stories were chosen to be deliberately unalike — a
consumer hardware launch, a systems-internals piece about <code>malloc()</code>,
and a web-history story with no hardware in it — so a fix that only works on one
kind of story shows up as failing to generalise.</p>

<h3>Calibration came first, and changed the conclusion</h3>
<p>Raw pairwise overlap cannot be read on its own. Scenes drawn from three
<em>different stories</em> — definitionally unrelated — still score
<strong>0.161</strong>, because cinematic prose shares a great deal of
unavoidable vocabulary. That is the floor, not zero. Identical scenes score
1.000. Without measuring the floor the headline number would have looked like a
failure; with it, the picture is that overlap was the wrong instrument and a
second metric was needed.</p>

<h2>What changed, and what each change did</h2>

<h3>1 · The art director (image.scene v3 → v5)</h3>
<p>Two causes, both instructions I had written myself in an earlier session.
<code>image.scene</code> said <em>"keep the same world, cast and place where the
story has not moved on"</em> — added for cross-shot continuity, and equally an
instruction to repeat the subject. And <code>prior_scenes</code> passed the full
text of previous prompts, so the model simply continued the prose.</p>
<ul>
<li><strong>Split continuity in two.</strong> Hold era, palette, scale and
indoors/outdoors; change what is in front of the camera.</li>
<li><strong>Pass prior subjects, not prior scenes</strong> — a bare noun list,
framed as things to avoid.</li>
<li><strong>A binding visual register per beat</strong>, rotating through human
scale, material, architectural, mechanism, landscape, trace. Camera angle was
never the problem: shot coverage already measured 0.64 while subjects repeated,
so a take could show eight angles of one desk.</li>
<li><strong>Demoted the spoken line</strong> from the top of the template to
context at the bottom. It was anchoring every frame on hardware.</li>
</ul>
<table>
<tr><th>Metric</th><th class="n">v3 baseline</th><th class="n">v4</th><th class="n">v5</th><th class="n">rendered</th></tr>
{row("Tech-tableau rate", "0.413", "0.319", "<span class='win'>0.315</span>", "0.355")}
{row("Scene vocabulary", "0.460", "0.495", "<span class='win'>0.502</span>", "0.437")}
{row("Excess overlap (above 0.161 floor)", "0.157", "0.156", "0.150", "0.102")}
{row("Distinct head nouns", "0.891", "0.958", "0.917", "—")}
</table>
<p class="small">Tableau rate is the share of frames containing a desk, laptop,
screen, monitor, keyboard, phone or office — the number that tracks what a
viewer actually notices. Excess overlap barely moved, and that is reported
rather than buried: it is dominated by prose style rather than subject, so it
was the wrong instrument for this failure. Both are kept, because a future
change that games one will show up in the other.</p>

<h3 class="pb">2 · The script (script.write v1 → v5, and a guard)</h3>
<p>Baseline script metrics were mostly healthy. The visible defects were a rich
article rendered as <strong>six</strong> sections against a requested 10–16, and
section lengths clustering.</p>
<table>
<tr><th>Attempt</th><th>Change</th><th class="n">Sections</th><th class="n">Length variation</th></tr>
<tr><td>v1</td><td>baseline</td><td class="n">16 / <span class="lose">6</span> / 9</td><td class="n">0.224</td></tr>
<tr><td>v3</td><td>numeric rhythm quota + firmer floor</td><td class="n">14 / 15 / 8</td><td class="n"><span class="lose">0.139</span></td></tr>
<tr><td>v4</td><td>function-driven rhythm, softer floor</td><td class="n">10 / 12 / <span class="lose">3</span></td><td class="n">0.146</td></tr>
<tr><td>v5</td><td>v3 floor + plain rhythm line</td><td class="n">14 / 14 / 6</td><td class="n">0.165</td></tr>
<tr><td><strong>guard</strong></td><td><strong>retry under 8 sections</strong></td><td class="n"><span class="win">14 / 12 / 12</span></td><td class="n">0.206</td></tr>
</table>
<div class="callout">
<p><strong>Two changes were reverted, and they are the more useful findings.</strong>
Asking for "at least two sections under ten words and two over twenty-five"
produced <em>fewer</em> of both — short sections went from 2/0/0 to 0/0/0.
A numeric target made the model aim for the middle. Softening the section floor
to a function-driven framing collapsed one script to three sections.</p>
</div>
<p>The real finding is that section count is not a prompt problem at all. The
same story and prompt returned <strong>9, 8, 3 and 6</strong> sections across
four samples. It is unstable run to run, and no wording made it reliable. The
floor is now enforced in code: under eight sections from more than 3,000
characters of source, retry once and keep the fuller script.</p>

<h2>The rule that emerged</h2>
<div class="callout">
<p>Across three rounds the same division held, and it is now the working rule
for this system:</p>
<p><strong>Structural properties need a deterministic guard.</strong> Speaker
run length, teaser subject, section count — wording is unreliable for all three,
and a cheap post-generation check is not. All three are now guarded in code.</p>
<p><strong>Content properties can only be fixed in the prompt.</strong> Which
subject to draw, what register to work in, what to avoid repeating — no
validator can supply these, and the prompt moved them measurably.</p>
</div>

<h2>New capability: narrated digests</h2>
<p>An edition can now be voiced as one continuous listen, built from the same
composed sections the Kindle document is typeset from — deliberately not a
separate audio script, which would drift from the written edition within a
week. Voices alternate per item, so it reads as two presenters trading pieces
rather than one monologue.</p>
<p>The first attempt voiced 3 of 5 sections. The cause is a hard backend limit
worth recording: <strong>Magpie returns audio over gRPC with a 4 MB response
cap</strong>, roughly 95 seconds or 350 words at 22050 Hz. Script lines never
reach it; digest sections are 350–500 words and reach it every time. Length was
not obvious as the cause because 1,584 characters worked fine in isolation.
Narration is now chunked on sentence boundaries — a mid-sentence split is
audible, because the voice drops its intonation contour at the break.</p>
<table>
<tr><th>Same edition</th><th class="n">Before</th><th class="n">After</th></tr>
{row("Sections voiced", "3 of 5", "<span class='win'>12 of 12</span>")}
{row("Duration", "2:09", "<span class='win'>10:45</span>")}
</table>

<h2>Round-by-round record</h2>
<table>
<tr><th>Round</th><th class="n">Switch</th><th class="n">Script vocab</th><th class="n">Length var</th><th class="n">Intent overlap</th></tr>
{row("round1-baseline", g("round1-baseline","switch_rate"), g("round1-baseline","script_lex"), g("round1-baseline","length_variation"), g("round1-baseline","intent_overlap"))}
{row("round3-script", g("round3-script","switch_rate"), g("round3-script","script_lex"), g("round3-script","length_variation"), g("round3-script","intent_overlap"))}
{row("round3b-script", g("round3b-script","switch_rate"), g("round3b-script","script_lex"), g("round3b-script","length_variation"), g("round3b-script","intent_overlap"))}
{row("round3c-script", g("round3c-script","switch_rate"), g("round3c-script","script_lex"), g("round3c-script","length_variation"), g("round3c-script","intent_overlap"))}
{row("round3d-guard", g("round3d-guard","switch_rate"), g("round3d-guard","script_lex"), g("round3d-guard","length_variation"), g("round3d-guard","intent_overlap"))}
</table>
<table>
<tr><th>Scene round</th><th class="n">Subject overlap</th><th class="n">Worst pair</th><th class="n">Vocabulary</th><th class="n">Shot coverage</th></tr>
{row("round1-scenes (v4)", g("round1-scenes","subject_overlap"), g("round1-scenes","max_pair_overlap"), g("round1-scenes","lexical_diversity"), g("round1-scenes","shot_coverage"))}
{row("round2-scenes (v5)", g("round2-scenes","subject_overlap"), g("round2-scenes","max_pair_overlap"), g("round2-scenes","lexical_diversity"), g("round2-scenes","shot_coverage"))}
</table>

<h2>What I would do next</h2>
<ul>
<li><strong>The register rotation deserves a second pass.</strong> It moved
tableau rate 24% as a fixed six-item cycle. Choosing the register from the
beat's own <code>visual_intent</code> — mechanism for a how-it-works beat,
landscape for a consequence beat — should do better than rotating blind.</li>
<li><strong>Video digests</strong> are the obvious counterpart to the narrated
edition: the same composed sections, one card per story, over the existing
image pipeline. The audio side proved the shape works.</li>
<li><strong>Length variation is still unsolved.</strong> Neither prompt approach
produced short sections, and unlike section count it has no obvious
deterministic fix — a validator can detect uniformity but cannot write the
one-line objection that breaks it.</li>
<li><strong>An ASR loop back into scoring.</strong> The pipeline already
transcribes its own audio and scored 0.948 on the last run; that signal is
computed and then discarded.</li>
</ul>
"""

doc = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{body}</body></html>"
open("/app/outputs/reports/prompt-evolution.html", "w").write(doc)
print("html written", len(doc))
