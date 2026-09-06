"""DOCX output for the Kindle.

Why not HTML, which is what we used to send: Amazon's HTML converter takes the
document title from the *attachment filename*, ignores `<meta name="author">`
entirely — every edition showed "Unknown" — and will not promote an inline
`<img>` to a cover. Those three things are exactly what a reader sees on the
shelf, and none of them are fixable from HTML.

Why not EPUB, which would be the natural answer: Brevo rejects `.epub`
outright, and the provider cannot change, because Brevo rewrites the From to a
brevosend address and *that* address is the one on Amazon's approved sender
list. A different provider means a different From and silent non-delivery.

DOCX threads the needle. Brevo accepts it, `docProps/core.xml` carries a real
title and creator, images embed, and Amazon reflows it properly on a 6"
screen. Written with stdlib zipfile for the same reason the EPUB is: the file
is a specified zip, and a malformed one fails silently at Amazon.
"""

import base64
import io
import logging
import re
import zipfile
from datetime import datetime
from typing import List, Optional
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

# Twips. Word's unit is 1/20 pt, and the Kindle converter honours the relative
# sizes rather than the absolute ones, so these are about proportion.
PT = 20
EMU_PER_PX = 9525


_MD_EMPHASIS = re.compile(r"(?<!\w)([*_]{1,2})(\S(?:[^*_\n]*\S)?)\1(?!\w)")


def _plain(text: str) -> str:
    """Body prose with its markdown taken off.

    The composer is asked for prose and mostly returns prose, but "a *modified*
    averaged Navier-Stokes equation" arrives with the asterisks intact and DOCX
    has no markdown, so the reader sees the asterisks. Emphasis is unwrapped
    rather than deleted — the word is wanted, the punctuation is not.
    """
    out = _MD_EMPHASIS.sub(r"\2", text or "")
    return out.replace("`", "")


def _t(text: str) -> str:
    return escape(str(text or ""))


def _p(text: str, style: str = "Body", *, italic=False, bold=False) -> str:
    runs = ""
    if text:
        props = ""
        if bold:
            props += "<w:b/>"
        if italic:
            props += "<w:i/>"
        rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
        runs = (
            f'<w:r>{rpr}<w:t xml:space="preserve">{_t(text)}</w:t></w:r>'
        )
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{runs}</w:p>'


def _image_p(rid: str, w_px: int, h_px: int, name: str) -> str:
    cx, cy = w_px * EMU_PER_PX, h_px * EMU_PER_PX
    return (
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
        f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:docPr id="{abs(hash(rid)) % 100000}" name="{_t(name)}"/>'
        "<a:graphic xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\">"
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="0" name="{_t(name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        "</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
    )


_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>
    <w:pPr><w:jc w:val="center"/><w:spacing w:before="240" w:after="120"/></w:pPr>
    <w:rPr><w:sz w:val="56"/><w:b/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Sub"><w:name w:val="Sub"/>
    <w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr>
    <w:rPr><w:sz w:val="22"/><w:i/><w:color w:val="555555"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>
    <w:pPr><w:outlineLvl w:val="0"/><w:spacing w:before="360" w:after="120"/>
      <w:pageBreakBefore/></w:pPr>
    <w:rPr><w:sz w:val="36"/><w:b/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>
    <w:pPr><w:outlineLvl w:val="1"/><w:spacing w:before="240" w:after="80"/></w:pPr>
    <w:rPr><w:sz w:val="26"/><w:b/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Kicker"><w:name w:val="Kicker"/>
    <w:pPr><w:spacing w:after="40"/></w:pPr>
    <w:rPr><w:sz w:val="16"/><w:caps/><w:color w:val="777777"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Body"><w:name w:val="Body"/>
    <w:pPr><w:spacing w:after="140" w:line="300" w:lineRule="auto"/></w:pPr>
    <w:rPr><w:sz w:val="22"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/>
    <w:pPr><w:spacing w:after="200"/><w:ind w:left="200" w:right="200"/></w:pPr>
    <w:rPr><w:sz w:val="15"/><w:i/><w:color w:val="666666"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/>
    <w:pPr><w:ind w:left="400"/><w:spacing w:after="140"/></w:pPr>
    <w:rPr><w:sz w:val="21"/><w:i/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Mono"><w:name w:val="Mono"/>
    <w:pPr><w:spacing w:after="60"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New"/><w:sz w:val="16"/></w:rPr></w:style>
</w:styles>"""


class DocxBuilder:
    """Accumulates paragraphs and images, then zips a valid .docx."""

    def __init__(self, title: str, author: str = "hn.fm"):
        self.title = title
        self.author = author
        self.body: List[str] = []
        self.images: List[tuple] = []   # (rid, filename, bytes)

    # -- content ----------------------------------------------------------
    def para(self, text: str, style="Body", **kw):
        self.body.append(_p(text, style, **kw))

    def image(self, data_uri: str, width_px: int = 470, alt: str = "figure"):
        """Embed a data-URI image. Silently skipped if it cannot be decoded —
        a missing picture must never cost the whole document."""
        try:
            head, b64 = data_uri.split(",", 1)
            raw = base64.b64decode(b64)
            ext = "png" if "png" in head else "jpeg"
            from PIL import Image

            with Image.open(io.BytesIO(raw)) as im:
                w, h = im.size
            rid = f"rId{100 + len(self.images)}"
            self.images.append((rid, f"media/img{len(self.images)}.{ext}", raw))
            height = max(1, round(width_px * h / w))
            self.body.append(_image_p(rid, width_px, height, alt))
        except Exception as e:
            logger.warning(f"docx: skipped an image ({e})")

    # -- output -----------------------------------------------------------
    def _document(self) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
            'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f"<w:body>{''.join(self.body)}</w:body></w:document>"
        )

    def _core(self) -> str:
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<dc:title>{_t(self.title)}</dc:title>"
            f"<dc:creator>{_t(self.author)}</dc:creator>"
            f"<cp:lastModifiedBy>{_t(self.author)}</cp:lastModifiedBy>"
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
            "</cp:coreProperties>"
        )

    def save(self, path: str) -> str:
        ct = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
            '<Default Extension="xml" ContentType="application/xml"/>',
            '<Default Extension="png" ContentType="image/png"/>',
            '<Default Extension="jpeg" ContentType="image/jpeg"/>',
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>',
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>',
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
            "</Types>",
        ]
        rels = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>',
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>',
            "</Relationships>",
        ]
        drels = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
            '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
        ]
        for rid, fname, _ in self.images:
            drels.append(
                f'<Relationship Id="{rid}" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                f'Target="{fname}"/>'
            )
        drels.append("</Relationships>")

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", "".join(ct))
            z.writestr("_rels/.rels", "".join(rels))
            z.writestr("docProps/core.xml", self._core())
            z.writestr("word/document.xml", self._document())
            z.writestr("word/styles.xml", _STYLES)
            z.writestr("word/_rels/document.xml.rels", "".join(drels))
            for _, fname, raw in self.images:
                z.writestr(f"word/{fname}", raw)
        return path


def safe_filename(name: str, when, ext: str = "docx") -> str:
    """A human attachment name.

    Amazon takes the shelf title from the filename on some paths, so
    `hnfm-digest-2026-09-05-illustrated.html` was itself the ugly title being
    reported. Keep it readable and filesystem-safe.
    """
    base = re.sub(r"[^A-Za-z0-9 .·-]+", "", name or "hn.fm Digest").strip()
    base = re.sub(r"\s+", " ", base) or "hn.fm Digest"
    return f"{base} {when:%-m-%-d}.{ext}"


def write_docx(digest, out_path: str, sections=None, illustrations=None,
               cover=None, edition_name: str = "", diagnostics=None) -> str:
    """A digest as a Kindle-ready .docx.

    Mirrors what `render_html` produces, so the two formats cannot drift into
    saying different things.
    """
    name = edition_name or digest.title
    title = f"{name} · {digest.generated_at:%-m/%-d}"
    doc = DocxBuilder(title=title, author="hn.fm")

    if cover is not None:
        doc.image(cover.data_uri, width_px=470, alt=name)
    doc.para(f"hn.fm · {digest.generated_at:%-m/%-d}", "Kicker")
    doc.para(name, "Title")
    doc.para(digest.subtitle, "Sub")

    def _sources(sec):
        """Where the piece came from.

        The HTML edition has carried these since it was written; the DOCX —
        the one that actually goes to the Kindle — dropped them, so the
        reader had no way back to the thread a quote came from. Plain text
        rather than links: this is read on a device that is usually offline,
        and a bare URL can be typed.
        """
        bits = []
        if getattr(sec, "hn_url", None):
            bits.append(f"Discussion: {sec.hn_url}")
        if getattr(sec, "url", None):
            bits.append(f"Source: {sec.url}")
        for src in (getattr(sec, "sources", None) or [])[:3]:
            if src.get("url"):
                bits.append(f"{src.get('title') or 'Reference'}: {src['url']}")
        if bits:
            doc.para("  ·  ".join(bits), "Caption")

    def _figure(illo):
        doc.image(illo.data_uri, width_px=440, alt=illo.style.label)
        doc.para(
            f"{illo.style.label} — {illo.style.technique} · ink {illo.ink:.2f}",
            "Caption",
        )
        doc.para(illo.prompt, "Mono")

    if sections:
        for sec in sections:
            pics = list((illustrations or {}).get(sec.story_id) or [])

            # The teaser is the edition's opening paragraph — it has no
            # headline and is not an item, so labelling it "In brief" printed
            # that kicker twice running with nothing between them. The bonus
            # is a list, not a story. Only quick and deep are items, and
            # theirs is the label that tells a commuter at a glance whether
            # this is a thirty-second read. The HTML renderer already made
            # this distinction; the DOCX path did not.
            if sec.kind == "teaser":
                doc.para(sec.body.strip(), "Body", italic=True)
                continue
            if sec.kind == "bonus":
                doc.para("Also", "Kicker")
                doc.para(sec.title or "Also worth knowing", "Heading1")
                for line in sec.body.splitlines():
                    if line.strip():
                        doc.para(line.strip(), "Body")
                continue

            doc.para("Feature" if sec.kind == "deep" else "In brief", "Kicker")
            doc.para(sec.title, "Heading1")
            if pics:
                _figure(pics.pop(0))
            paras = [p for p in sec.body.split("\n\n") if p.strip()]
            gap = max(2, (len(paras) // (len(pics) + 1)) or 2) if pics else 0
            for i, para in enumerate(paras, start=1):
                doc.para(_plain(para.strip()))
                if pics and gap and i % gap == 0:
                    _figure(pics.pop(0))
            for leftover in pics:
                _figure(leftover)
            _sources(sec)

        if len(sections) == 1 and sections[0].story_id is None:
            # A narrative edition is one essay that names its stories inline
            # but links to none of them, so the reader who wants the thread
            # behind a claim has nowhere to go. Listed once at the end rather
            # than interrupting the prose.
            doc.para("The pieces", "Heading1")
            for st in digest.stories:
                doc.para(st.title, "Body", bold=True)
                doc.para(
                    f"Discussion: {st.hn_url}"
                    + (f"  ·  Source: {st.url}" if st.url else ""),
                    "Caption",
                )
    else:
        for story in digest.stories:
            b = story.brief or {}
            doc.para(b.get("why_now") or "From Hacker News", "Kicker")
            doc.para(story.title, "Heading1")
            for pic in (illustrations or {}).get(story.item_id) or []:
                _figure(pic)
            if b.get("thesis"):
                doc.para(b["thesis"], "Body", italic=True)
            for key, heading in (("angle", "The angle"), ("tension", "The tension"),
                                 ("stakes", "Who it touches")):
                if b.get(key):
                    doc.para(heading, "Heading2")
                    doc.para(b[key])

    if diagnostics:
        _diagnostics_docx(doc, diagnostics)
    return doc.save(out_path)


def _diagnostics_docx(doc: "DocxBuilder", diag: dict) -> None:
    """The closing report: what produced this edition and what it cost."""
    doc.para("Diagnostics", "Heading1")
    doc.para(
        "What produced this edition, and where the effort went. Useful for "
        "spotting which stage actually dominates the cost.", "Sub",
    )

    doc.para("Models", "Heading2")
    for role, model in (diag.get("models") or {}).items():
        doc.para(f"{role}: {model}", "Mono")

    doc.para("Tokens by phase", "Heading2")
    for row in diag.get("phases") or []:
        doc.para(
            f"{row['phase']:<16} {row['calls']:>4} calls   "
            f"{row['tokens_in']:>8,} in   {row['tokens_out']:>7,} out   "
            f"{row['seconds']:>7.1f}s",
            "Mono",
        )
    t = diag.get("totals") or {}
    doc.para(
        f"{'TOTAL':<16} {t.get('calls', 0):>4} calls   "
        f"{t.get('tokens_in', 0):>8,} in   {t.get('tokens_out', 0):>7,} out   "
        f"{t.get('seconds', 0):>7.1f}s",
        "Mono", bold=True,
    )

    doc.para("Research per story", "Heading2")
    for row in diag.get("stories") or []:
        doc.para(
            f"{row['tokens']:>8,} tok  {row['steps']:>3} steps  {row['title'][:52]}",
            "Mono",
        )

    img = diag.get("images") or {}
    if img:
        doc.para("Images", "Heading2")
        doc.para(
            f"{img.get('count', 0)} generated by {img.get('model', '?')} "
            f"at {img.get('dimensions', '?')}, {img.get('seconds', 0):.1f}s total",
            "Mono",
        )
        for st in img.get("styles") or []:
            doc.para(f"  {st}", "Mono")
