"""Typesetting a digest: HTML for the browser, EPUB for the Kindle.

Both come from one `_story_body()` so the two formats cannot say different
things. EPUB is written with stdlib zipfile rather than a library: the file is
a small, well-specified zip, and Send to Kindle rejects a malformed one
silently — no bounce, no error, the book simply never arrives — so it is worth
controlling the bytes directly.

Kindle constraints that shape the markup:
  * A Paperwhite is 6", greyscale, and reflows. Fixed widths, columns, and
    floats are pointless or harmful; the device owns the margins.
  * Amazon's converter honours a small CSS subset. Anything here is deliberately
    boring — no flex, no grid, no custom fonts.
  * EPUB 2's toc.ncx is what older devices read, so it is emitted alongside the
    EPUB 3 nav document rather than relying on nav alone.
"""

import html
import logging
import os
import zipfile
from datetime import datetime
from typing import List

from .select import Digest, DigestStory

logger = logging.getLogger(__name__)

# Serif, generous leading, and a hyphen-free ragged right: the Kindle's own
# justification is poor at this measure, so left-align rather than justify.
_CSS = """\
body { font-family: Georgia, "Times New Roman", serif; line-height: 1.5;
       text-align: left; margin: 0; padding: 0; }
h1 { font-size: 1.6em; line-height: 1.2; margin: 0 0 .2em; }
h2 { font-size: 1.25em; line-height: 1.25; margin: 1.2em 0 .3em;
     page-break-after: avoid; }
h3 { font-size: 1em; text-transform: uppercase; letter-spacing: .08em;
     margin: 1.4em 0 .4em; page-break-after: avoid; }
p { margin: 0 0 .7em; }
.kicker { font-size: .8em; text-transform: uppercase; letter-spacing: .1em;
          margin: 0 0 .6em; }
.meta { font-size: .8em; margin: 0 0 1.2em; }
.thesis { font-size: 1.08em; font-style: italic; margin: 0 0 1em; }
blockquote { margin: .4em 0 .8em 1em; padding-left: .8em;
             border-left: 2px solid #999; font-style: italic; }
.claim { margin: 0 0 .2em; font-weight: bold; }
ul { margin: 0 0 .8em 1.1em; padding: 0; }
li { margin: 0 0 .35em; }
.rule { border: 0; border-top: 1px solid #999; margin: 1.6em 0; }
.footer { font-size: .8em; margin-top: 1.6em; }
"""


def _esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def _story_body(story: DigestStory) -> str:
    """One story as XHTML, shared by both output formats.

    Sections are emitted only when the brief actually has them. An empty
    `entities` list or a brief with no `numbers` is normal, and printing an
    empty heading would look like a rendering bug rather than a quiet story.
    """
    b = story.brief or {}
    out: List[str] = []

    out.append(f'<p class="kicker">{_esc(b.get("why_now") or "From Hacker News")}</p>')
    out.append(f"<h2>{_esc(story.title)}</h2>")

    meta = f"{story.hn_score} points on Hacker News"
    if story.interest is not None:
        meta += f" · interest {story.interest}"
    out.append(f'<p class="meta">{_esc(meta)}</p>')

    if b.get("thesis"):
        out.append(f'<p class="thesis">{_esc(b["thesis"])}</p>')
    for key, heading in (("angle", "The angle"), ("tension", "The tension"),
                         ("stakes", "Who it touches")):
        if b.get(key):
            out.append(f"<h3>{heading}</h3><p>{_esc(b[key])}</p>")

    facts = [f for f in (b.get("key_facts") or []) if f.get("claim")]
    if facts:
        out.append("<h3>What we know</h3>")
        for f in facts:
            out.append(f'<p class="claim">{_esc(f["claim"])}</p>')
            if f.get("quote"):
                attrib = f.get("hn_user") or f.get("source") or ""
                cite = f" — {_esc(attrib)}" if attrib else ""
                out.append(f"<blockquote>{_esc(f['quote'])}{cite}</blockquote>")

    numbers = [n for n in (b.get("numbers") or []) if n.get("value")]
    if numbers:
        out.append("<h3>By the numbers</h3><ul>")
        for n in numbers:
            ctx = n.get("context") or n.get("of") or ""
            out.append(f"<li>{_esc(n['value'])}{' — ' + _esc(ctx) if ctx else ''}</li>")
        out.append("</ul>")

    unknowns = [u for u in (b.get("unknowns") or []) if u]
    if unknowns:
        out.append("<h3>Still open</h3><ul>")
        # Capped: briefs routinely produce a dozen, which reads as padding on a
        # 6" screen and buries the story that follows.
        for u in unknowns[:5]:
            out.append(f"<li>{_esc(u)}</li>")
        out.append("</ul>")

    links = [f'<a href="{_esc(story.hn_url)}">Discussion</a>']
    if story.url:
        links.append(f'<a href="{_esc(story.url)}">Source</a>')
    out.append(f'<p class="footer">{" · ".join(links)}</p>')
    return "\n".join(out)


def _section_body(sec) -> str:
    """One composed section as XHTML, shared by both output formats."""
    out = []
    if sec.kind == "teaser":
        out.append(f'<p class="thesis">{_esc(sec.body)}</p>')
        return "\n".join(out)

    if sec.kind == "bonus":
        out.append(f"<h2>{_esc(sec.title)}</h2><ul>")
        for line in sec.body.splitlines():
            if line.strip():
                out.append(f"<li>{_esc(line.strip())}</li>")
        out.append("</ul>")
        return "\n".join(out)

    # quick | deep. The kicker is what tells a commuter, at a glance, whether
    # this is a 30-second item or the one to settle into.
    out.append(
        f'<p class="kicker">{"Feature" if sec.kind == "deep" else "In brief"}</p>'
    )
    out.append(f"<h2>{_esc(sec.title)}</h2>")
    for para in [p for p in sec.body.split("\n\n") if p.strip()]:
        out.append(f"<p>{_esc(para.strip())}</p>")

    links = []
    if sec.hn_url:
        links.append(f'<a href="{_esc(sec.hn_url)}">Discussion</a>')
    if sec.url:
        links.append(f'<a href="{_esc(sec.url)}">Source</a>')
    for src in sec.sources or []:
        if src.get("url"):
            links.append(f'<a href="{_esc(src["url"])}">{_esc(src.get("title") or "Reference")}</a>')
    if links:
        out.append(f'<p class="footer">{" · ".join(links)}</p>')
    return "\n".join(out)


def render_html(digest: Digest, sections=None) -> str:
    """One self-contained HTML document — browser view and Send-to-Kindle HTML."""
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_esc(digest.title)} — {digest.generated_at:%d %B %Y}</title>",
        f"<style>{_CSS}\nbody{{max-width:38em;margin:0 auto;padding:2em 1.2em;}}</style>",
        "</head><body>",
        f"<h1>{_esc(digest.title)}</h1>",
        f'<p class="meta">{_esc(digest.subtitle)}</p>',
    ]
    if sections:
        # Composed edition: teaser, quick hits, feature, bonus. No rule before
        # the teaser — it reads as part of the masthead.
        for sec in sections:
            if sec.kind != "teaser":
                parts.append('<hr class="rule"/>')
            parts.append(_section_body(sec))
    else:
        for story in digest.stories:
            parts.append('<hr class="rule"/>')
            parts.append(_story_body(story))
    if not digest.stories:
        parts.append("<p>No stories with a Story Brief were available.</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _xhtml(title: str, body: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" lang="en"><head>'
        f"<title>{_esc(title)}</title>"
        '<link rel="stylesheet" type="text/css" href="style.css"/>'
        f"</head><body>{body}</body></html>"
    )


def write_epub(digest: Digest, out_path: str, sections=None) -> str:
    """Write an EPUB and return its path.

    `mimetype` must be the first entry and stored uncompressed — readers check
    it at a fixed offset, and a deflated one is the usual reason a hand-built
    EPUB is rejected without explanation.
    """
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    uid = f"urn:uuid:hnfm-{digest.generated_at:%Y%m%d%H%M%S}"
    stamp = digest.generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    chapters = []
    if sections:
        # The teaser rides on the cover rather than becoming a chapter of its
        # own — a one-paragraph entry in the table of contents is noise.
        teaser = next((s for s in sections if s.kind == "teaser"), None)
        body_sections = [s for s in sections if s.kind != "teaser"]
        for i, sec in enumerate(body_sections, start=1):
            label = sec.title or ("Also worth knowing" if sec.kind == "bonus" else f"Item {i}")
            chapters.append((f"s{i}.xhtml", label, _xhtml(label, _section_body(sec))))
    else:
        teaser = None
        for i, story in enumerate(digest.stories, start=1):
            chapters.append((f"s{i}.xhtml", story.title, _xhtml(story.title, _story_body(story))))

    cover = _xhtml(
        digest.title,
        f"<h1>{_esc(digest.title)}</h1><p class='meta'>{_esc(digest.subtitle)}</p>"
        + (f'<p class="thesis">{_esc(teaser.body)}</p>' if teaser else "")
        + "<ul>" + "".join(
            f'<li><a href="{fn}">{_esc(t)}</a></li>' for fn, t, _ in chapters
        ) + "</ul>",
    )

    manifest = [
        '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" '
        'properties="nav"/>',
    ]
    spine = ['<itemref idref="cover"/>']
    for i, (fn, _t, _c) in enumerate(chapters, start=1):
        manifest.append(
            f'<item id="s{i}" href="{fn}" media-type="application/xhtml+xml"/>'
        )
        spine.append(f'<itemref idref="s{i}"/>')

    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        'unique-identifier="bookid">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:identifier id=\"bookid\">{uid}</dc:identifier>"
        f"<dc:title>{_esc(digest.title)} — {digest.generated_at:%d %B %Y}</dc:title>"
        "<dc:language>en</dc:language>"
        "<dc:creator>hn.fm</dc:creator>"
        f'<meta property="dcterms:modified">{stamp}</meta>'
        "</metadata>"
        f"<manifest>{''.join(manifest)}</manifest>"
        f"<spine toc=\"ncx\">{''.join(spine)}</spine>"
        "</package>"
    )

    navpoints = "".join(
        f'<navPoint id="n{i}" playOrder="{i}"><navLabel><text>{_esc(t)}</text>'
        f'</navLabel><content src="{fn}"/></navPoint>'
        for i, (fn, t, _c) in enumerate(chapters, start=1)
    )
    ncx = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
        f'<head><meta name="dtb:uid" content="{uid}"/></head>'
        f"<docTitle><text>{_esc(digest.title)}</text></docTitle>"
        f"<navMap>{navpoints}</navMap></ncx>"
    )
    nav = _xhtml(
        "Contents",
        '<nav xmlns:epub="http://www.idpf.org/2007/ops" epub:type="toc" id="toc">'
        "<h1>Contents</h1><ol>"
        + "".join(f'<li><a href="{fn}">{_esc(t)}</a></li>' for fn, t, _ in chapters)
        + "</ol></nav>",
    )

    with zipfile.ZipFile(out_path, "w") as z:
        z.writestr(
            zipfile.ZipInfo("mimetype"), "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        z.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
            zipfile.ZIP_DEFLATED,
        )
        z.writestr("OEBPS/content.opf", opf, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", _CSS, zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/cover.xhtml", cover, zipfile.ZIP_DEFLATED)
        for fn, _t, content in chapters:
            z.writestr(f"OEBPS/{fn}", content, zipfile.ZIP_DEFLATED)

    logger.info(f"digest: wrote EPUB {out_path} ({os.path.getsize(out_path)} bytes)")
    return out_path
