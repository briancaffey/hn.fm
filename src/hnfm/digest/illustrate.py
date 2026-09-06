"""Illustrations for a digest, sized and toned for a Kindle.

The device is the whole design constraint. A Paperwhite is 6", **greyscale**,
and reflows — so anything that carries meaning in hue is lost, and anything
with subtle mid-tones turns to mud. What survives is line, contrast and
negative space, which is why every recipe here is some variety of ink, print
or diagram rather than a rendered scene.

Images are embedded as data URIs. A digest arrives as an email attachment and
Amazon's converter does not reliably fetch remote images, so a self-contained
file is the only kind that works.
"""

import base64
import io
import logging
import random
from dataclasses import dataclass
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

# Wide enough to look deliberate at 6", small enough that twenty of them do not
# push the email past a provider attachment limit.
RENDER_W, RENDER_H = 768, 512
EMBED_W = 640
JPEG_QUALITY = 72


def _norm(subject: str) -> str:
    """Make a subject safe to drop into the middle of a sentence.

    The model returns a standalone sentence — "A weathered fence post at dawn."
    — which reads as "depicting A weathered fence post at dawn.. Rendered as…"
    once embedded. Strip the terminal stop and lowercase the leading article.
    """
    t = (subject or "").strip().strip('"').rstrip(".")
    if t[:1].isupper() and not t[:4].isupper():
        t = t[0].lower() + t[1:]
    return t


@dataclass
class Style:
    key: str
    label: str
    """How the prompt is built — the technique under test, not just the words."""
    technique: str
    build: Callable[[str, str], str]
    steps: int = 28
    cfg: float = 4.0


# --- prompt techniques -----------------------------------------------------
#
# Each of these composes the prompt differently on purpose. The point of the
# experiment is to compare *techniques* (how the instruction is framed) as well
# as *styles* (what it asks for), so two recipes that name the same medium may
# still read very differently to the model.


def _medium_first(medium: str, extras: str = "", negatives: str = ""):
    """Lead with the medium, then the subject. Anchors the model on process."""
    def build(subject: str, _title: str) -> str:
        subject = _norm(subject)
        parts = [f"{medium} of {subject}"]
        if extras:
            parts.append(extras)
        if negatives:
            parts.append(f"no {negatives}")
        return ". ".join(parts) + "."
    return build


def _constraint_list(medium: str, constraints: List[str]):
    """Subject first, then an explicit checklist. Reads like a brief."""
    def build(subject: str, _title: str) -> str:
        return (
            f"{_norm(subject).capitalize()}. Rendered as {medium}. "
            + " ".join(f"{c}." for c in constraints)
        )
    return build


def _negative_space(medium: str):
    """Leads with what to leave out. Produces airier, more Kindle-friendly art."""
    def build(subject: str, _title: str) -> str:
        return (
            f"Mostly empty white page. A small, precise {medium} of {_norm(subject)} "
            f"occupies less than half the frame, positioned off-centre. "
            f"The remaining space is untouched paper."
        )
    return build


def _period_reference(period: str, medium: str):
    """Names an era and artefact rather than describing the look directly."""
    def build(subject: str, _title: str) -> str:
        return (
            f"A plate from {period}. {medium} depicting {_norm(subject)}. "
            f"Printed in black ink on aged paper stock, no colour."
        )
    return build


def _material_metaphor(material: str, verb: str):
    """Describes the image as a physical object made of something."""
    def build(subject: str, _title: str) -> str:
        return (
            f"{_norm(subject).capitalize()}, {verb} entirely from {material}. Photographed flat "
            f"against white, hard directional light, strong shadows, no colour."
        )
    return build


def _diagram(kind: str):
    """Asks for an explanatory artefact rather than a picture."""
    def build(subject: str, title: str) -> str:
        return (
            f"A {kind} explaining {_norm(subject)}. Hand-lettered labels, leader lines, "
            f"arrows, measurement marks. Black ink on white grid paper. "
            f"Title reads \"{title[:40]}\"."
        )
    return build


def _instrument(instrument: str):
    """Names the tool that made the mark rather than the style it produces."""
    def build(subject: str, _title: str) -> str:
        return (
            f"Drawn with {instrument}. Subject: {_norm(subject)}. "
            f"The mark of the tool is visible throughout — nothing smoothed or "
            f"cleaned up afterwards. Black on white."
        )
    return build


def _absence(present: str, absent: str):
    """Describes the image by what is missing from it."""
    def build(subject: str, _title: str) -> str:
        return (
            f"{_norm(subject).capitalize()}, rendered so that only the {present} "
            f"is drawn and the {absent} is left as bare white paper. "
            f"High contrast, no midtones."
        )
    return build


def _single_constraint(rule: str):
    """One rule, stated absolutely. Terse prompts sometimes beat long ones."""
    def build(subject: str, _title: str) -> str:
        return f"{_norm(subject).capitalize()}. {rule}"
    return build


# --- the catalogue ---------------------------------------------------------

STYLES: List[Style] = [
    Style("ink-line", "Single-weight ink line", "medium-first + negatives",
          _medium_first(
              "Minimalist single-weight black ink line drawing on pure white",
              "Clean unbroken contours, generous negative space, editorial illustration",
              "shading, colour, gradients, texture, background")),

    Style("hand-sketch", "Loose pen sketch", "medium-first + negatives",
          _medium_first(
              "Loose hand-drawn pen and ink sketch with visible crosshatching",
              "Confident imperfect strokes, sketchbook feel, off-white paper",
              "colour, digital smoothness, photorealism"), steps=30),

    Style("bauhaus", "Flat geometric", "constraint list",
          _constraint_list("a flat geometric poster", [
              "Only circles, triangles and rectangles",
              "Pure black shapes on white, no outlines",
              "Bauhaus composition, strong asymmetric balance",
              "No text, no gradient, no perspective",
          ])),

    Style("woodcut", "Woodcut print", "period reference",
          _period_reference("a 1930s woodcut broadside", "High-contrast relief print")),

    Style("engraving", "Stipple engraving", "period reference",
          _period_reference(
              "an 1890s scientific encyclopedia", "Fine stipple and line engraving"),
          steps=34),

    Style("blueprint", "Technical schematic", "diagram-as-artefact",
          _diagram("technical cutaway diagram")),

    Style("isometric", "Isometric line", "constraint list",
          _constraint_list("an isometric line illustration", [
              "Thin uniform black strokes on white",
              "Exact 30 degree isometric projection",
              "No fill, no shadow, wireframe clarity",
          ])),

    Style("sumi", "Brush ink wash", "medium-first",
          _medium_first(
              "Sumi-e brush and ink painting",
              "A few decisive strokes, wet edges, large areas of untouched paper",
              "colour, fine detail, outlines"), cfg=3.5),

    Style("papercut", "Paper cutout", "material metaphor",
          _material_metaphor("torn black paper", "cut and assembled")),

    Style("wire", "Bent wire sculpture", "material metaphor",
          _material_metaphor("a single continuous bent black wire", "formed")),

    Style("negative", "Negative-space vignette", "negative-space led",
          _negative_space("black ink drawing")),

    Style("contour", "Topographic contour", "constraint list",
          _constraint_list("a topographic contour map abstraction", [
              "Concentric black contour lines only",
              "Line density carries the form",
              "Pure white ground, no labels, no colour",
          ])),
]

STYLES += [
    Style("charcoal", "Charcoal on newsprint", "instrument-named",
          _instrument("a stick of compressed charcoal held flat"), steps=30),

    Style("technical-pen", "0.1mm technical pen", "instrument-named",
          _instrument("a 0.1mm technical pen and a straight edge")),

    Style("silhouette", "Silhouette only", "absence",
          _absence("silhouette", "interior detail")),

    Style("shadow", "Cast shadow only", "absence",
          _absence("cast shadow on the ground", "object itself")),

    Style("one-line", "Single continuous line", "single constraint",
          _single_constraint(
              "Drawn as ONE continuous black line that never lifts from the "
              "page and never crosses itself. White ground.")),

    Style("halftone", "Newspaper halftone", "single constraint",
          _single_constraint(
              "Reproduced as a coarse newspaper halftone: visible black dots "
              "of varying size on white, no continuous tone, 1960s print.")),

    Style("blackout", "Inverted blackout", "single constraint",
          _single_constraint(
              "Rendered in reverse: solid black page, the subject scratched "
              "out in fine white lines like a scraperboard engraving.")),

    Style("diagram-exploded", "Exploded assembly", "diagram-as-artefact",
          _diagram("exploded assembly diagram, parts separated along an axis")),
]

STYLE_BY_KEY = {s.key: s for s in STYLES}


def _to_kindle_bytes(raw: bytes) -> bytes:
    """Greyscale, resized, JPEG. The device shows grey whatever we send, and
    converting here means what we review is what the Kindle renders."""
    from PIL import Image

    im = Image.open(io.BytesIO(raw)).convert("L")
    if im.width > EMBED_W:
        h = round(im.height * EMBED_W / im.width)
        im = im.resize((EMBED_W, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def ink_coverage(jpeg_bytes: bytes) -> float:
    """Share of the image darker than mid-grey.

    A useful proxy for whether a recipe will read on e-ink: near zero is a
    blank-looking page, above ~0.35 is a grey slab. The sweet spot for line art
    is roughly 0.03-0.20.
    """
    from PIL import Image

    im = Image.open(io.BytesIO(jpeg_bytes)).convert("L")
    hist = im.histogram()
    total = sum(hist) or 1
    return round(sum(hist[:128]) / total, 3)


@dataclass
class Illustration:
    style: Style
    prompt: str
    data_uri: str
    ink: float
    seconds: float


def _catalogue(illo: "Illustration", kind: str, item_id=None,
               slug=None, title=None) -> None:
    """Record the picture so it is findable later with its prompt intact.

    A digest image lives inside the document, so the catalogue keeps a small
    thumbnail rather than a path — otherwise the only copy of a prompt that
    produced something good would be buried in an email attachment.
    """
    try:
        from ..db import repo

        repo.record_generated_image(
            kind=kind, item_id=item_id, slug=slug, title=title,
            prompt=illo.prompt, style_key=illo.style.key,
            style_label=illo.style.label, technique=illo.style.technique,
            model="flux2-klein", width=RENDER_W, height=RENDER_H,
            ink=illo.ink, seconds=illo.seconds, thumb=illo.data_uri,
        )
    except Exception as e:
        logger.debug(f"catalogue skipped: {e}")


def render(subject: str, title: str, style: Style,
           seed: Optional[int] = None, kind: str = "digest",
           item_id=None, slug=None) -> Optional[Illustration]:
    """One illustration, or None. Never raises: a digest missing a picture is
    far better than a digest that failed to build."""
    import time

    from ..video.image_generator import ImageGenerationService

    prompt = style.build(subject, title)
    t0 = time.time()
    try:
        svc = ImageGenerationService()
        res = svc.generate_image(
            prompt=prompt, width=RENDER_W, height=RENDER_H,
            steps=style.steps, cfg_scale=style.cfg, seed=seed,
        )
        raw = base64.b64decode(res["artifacts"][0]["base64"])
        jpeg = _to_kindle_bytes(raw)
        illo = Illustration(
            style=style,
            prompt=prompt,
            data_uri="data:image/jpeg;base64," + base64.b64encode(jpeg).decode(),
            ink=ink_coverage(jpeg),
            seconds=round(time.time() - t0, 1),
        )
        _catalogue(illo, kind=kind, item_id=item_id, slug=slug, title=title)
        return illo
    except Exception as e:
        logger.warning(f"illustration failed ({style.key}): {e}")
        return None


def subject_for(story) -> str:
    """A concrete, drawable subject for a story.

    Deliberately one short LLM call rather than passing the headline straight
    through: "Formalizing Fermat's Last Theorem" is a topic, not a picture, and
    the model will render text-on-a-page if asked to draw an abstraction.
    """
    from ..content.llm_service import LLMService, LLMError

    b = story.brief or {}
    context = (b.get("thesis") or b.get("angle") or "")[:400]
    prompt = (
        "Name ONE concrete physical scene that could illustrate this story for "
        "a print magazine printed in BLACK INK ONLY.\n"
        "Rules:\n"
        "- A physical subject, doing something, somewhere.\n"
        "- Never a screen, monitor, laptop, phone, terminal or UI. Those are "
        "the one thing that cannot be drawn well in ink.\n"
        "- No colour words at all — the page is greyscale, so 'glowing blue' "
        "and 'warm golden' describe nothing.\n"
        "- No text, logos, charts, diagrams or recognisable faces.\n"
        "- Favour objects, materials, hands, tools, landscapes, architecture.\n"
        "Answer with the scene only, under 18 words, no preamble, no full stop."
        "\n\n"
        f"Headline: {story.title}\n{context}"
    )
    try:
        out = LLMService(task="image.scene").generate_content(prompt).strip()
        out = out.strip('"').split("\n")[0]
        return out[:200] or story.title
    except (LLMError, Exception) as e:
        logger.info(f"subject fallback for {story.item_id}: {e}")
        return story.title


def plan(stories, per_story: int = 2, seed: int = 7) -> dict:
    """Assign styles across the digest so no two adjacent images match and
    every style gets used before any repeats."""
    rng = random.Random(seed)
    deck: List[Style] = []
    out: dict = {}
    for s in stories:
        picks = []
        while len(picks) < per_story:
            if not deck:
                deck = STYLES[:]
                rng.shuffle(deck)
            cand = deck.pop()
            if cand.key not in {p.key for p in picks}:
                picks.append(cand)
        out[s.item_id] = picks
    return out


# --- edition furniture -----------------------------------------------------

COVER_STYLE = Style(
    "cover", "Cover plate", "constraint list",
    _constraint_list("a bold black-ink cover illustration", [
        "One strong central motif, symmetrical, filling the frame",
        "Heavy confident line weight so it survives a low-contrast screen",
        "Pure black on white, no grey wash, no text, no lettering",
        "Woodblock poster feel",
    ]),
    steps=32,
)


def edition_name(stories) -> str:
    """A short name for the edition, taken from what is actually in it.

    "hn.fm Digest — 05 September 2026" is a filename, not a title: on the
    Kindle shelf every edition looks identical, so there is no way to tell
    yesterday's from today's without opening them.
    """
    from ..content.llm_service import LLMService, LLMError

    titles = "\n".join(f"- {s.title}" for s in stories[:8])
    prompt = (
        "Below are the stories in one edition of a tech reading digest. "
        "Give the edition a short name: 2-4 words, title case, concrete, "
        "drawn from what these stories have in common. It goes on a Kindle "
        "shelf beside other editions, so it must be distinguishable at a "
        "glance. No colon, no subtitle, no quotes, no date, no preamble.\n\n"
        f"{titles}"
    )
    try:
        out = LLMService(task="image.scene").generate_content(prompt).strip()
        out = out.strip('"').split("\n")[0].rstrip(".")
        # A model that ignores the word limit gives a sentence; a sentence is
        # worse than the fallback, so take the fallback.
        return out if 0 < len(out.split()) <= 6 else ""
    except (LLMError, Exception) as e:
        logger.info(f"edition name fallback: {e}")
        return ""


def cover_for(stories, name: str, slug: str = None):
    """One cover plate for the edition, or None."""
    if not stories:
        return None
    subject = subject_for(stories[0])
    return render(subject, name or stories[0].title, COVER_STYLE, seed=3,
                  kind="cover", slug=slug, item_id=stories[0].item_id)
