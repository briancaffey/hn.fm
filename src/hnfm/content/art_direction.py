"""Art direction for hn.fm image generation.

The old pipeline used one fixed "detailed cartoon style" for everything, so every
video looked the same. This module defines a library of distinct **visual themes**.
Each *take* (segment) is assigned one theme, giving every take a cohesive look
while different takes of the same story look dramatically different — which is the
whole point of generating multiple takes and comparing them.

A final image prompt = LLM-written SCENE (subject/action/composition) + the theme's
STYLE block (medium/palette/lighting/render) + quality tags. The scene stays varied
per shot; the style stays consistent per take.
"""

import os
import random
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Theme:
    key: str
    name: str
    style: str          # the style directives appended to every scene in the take
    negative: str = ""  # things to avoid (for backends that support it)
    mood: str = ""


# A deliberately diverse set — different media, eras, palettes, energy levels.
THEMES: List[Theme] = [
    Theme(
        "synthwave", "Neon Synthwave",
        "1980s synthwave aesthetic, glowing neon magenta and cyan, chrome reflections, "
        "dramatic rim lighting, retro-futurist, volumetric haze, sun-grid horizon, "
        "high-contrast cinematic render, 35mm anamorphic",
        mood="energetic, nostalgic-futuristic",
    ),
    Theme(
        "risograph", "Risograph Print",
        "risograph print illustration, 2-3 spot colors (fluorescent pink, blue, yellow), "
        "visible halftone grain, slight misregistration, flat bold shapes, paper texture, "
        "indie zine aesthetic, limited palette, screenprint look",
        mood="playful, handmade, editorial",
    ),
    Theme(
        "watercolor", "Editorial Watercolor",
        "loose editorial watercolor illustration, soft washes, bleeding pigments, "
        "expressive ink linework, generous white space, New Yorker style, muted earthy palette, "
        "delicate and contemplative",
        mood="thoughtful, literary",
    ),
    Theme(
        "isometric", "Isometric Low-Poly 3D",
        "clean isometric low-poly 3D render, soft studio lighting, pastel gradient palette, "
        "tilt-shift miniature feel, subtle ambient occlusion, tidy geometric forms, "
        "Blender-style, depth of field",
        mood="precise, modern, friendly",
    ),
    Theme(
        "noir", "Ink Noir Comic",
        "high-contrast black-and-white noir comic ink, heavy chiaroscuro shadows, "
        "dramatic single light source, cross-hatching, rain-soaked atmosphere, "
        "graphic novel panel, bold negative space, a single accent of red",
        mood="moody, tense, cinematic",
    ),
    Theme(
        "blueprint", "Technical Blueprint",
        "cyanotype technical blueprint, white schematic linework on deep blue, "
        "annotated diagram callouts, dimension lines, drafting grid, exploded-view detail, "
        "engineering aesthetic, crisp vector lines",
        mood="analytical, precise",
    ),
    Theme(
        "claymation", "Claymation Diorama",
        "stop-motion claymation diorama, hand-molded plasticine characters with fingerprints, "
        "soft practical lighting, shallow macro depth of field, tactile handmade props, "
        "Aardman-style, warm cozy palette",
        mood="charming, tactile, whimsical",
    ),
    Theme(
        "vaporwave", "Surreal Vaporwave Collage",
        "surreal vaporwave digital collage, classical statue fragments, gridded floors, "
        "pastel pink and teal, glitch artifacts, floating 3D shapes, dreamy and uncanny, "
        "retro computing motifs, soft glow",
        mood="dreamy, ironic, surreal",
    ),
    Theme(
        "papercut", "Layered Papercut",
        "layered paper-cut craft illustration, stacked construction-paper depth, soft drop shadows "
        "between layers, warm directional light, handcrafted storybook feel, bold simple shapes, "
        "rich saturated paper colors",
        mood="warm, tactile, storybook",
    ),
    Theme(
        "oilpaint", "Dramatic Oil Painting",
        "dramatic oil painting, thick impasto brushwork, chiaroscuro lighting, rich jewel tones, "
        "Baroque composition, painterly texture, museum masterpiece, deep shadows and golden highlights",
        mood="grand, dramatic, timeless",
    ),
    Theme(
        "pixelart", "Retro Pixel Art",
        "detailed 16-bit pixel art, limited retro palette, crisp dithering, chunky pixels, "
        "side-scroller game scene, glowing CRT vibe, cozy nostalgic computing",
        mood="nostalgic, playful, techy",
    ),
    Theme(
        "infographic", "Bold Flat Infographic",
        "bold flat-design vector infographic, confident geometric shapes, vibrant duotone with one "
        "punchy accent, clean negative space, modern tech-editorial look, crisp icons, Helvetica energy",
        mood="clear, confident, modern",
    ),
]

_THEMES_BY_KEY = {t.key: t for t in THEMES}

# Universal quality tags appended to every prompt.
QUALITY_TAGS = "highly detailed, striking composition, professional, 16:9"


def list_themes() -> List[Theme]:
    return THEMES


def get_theme(key: Optional[str]) -> Optional[Theme]:
    return _THEMES_BY_KEY.get(key or "")


def pick_theme(seed: Optional[int] = None, exclude: Optional[List[str]] = None) -> Theme:
    """Pick a theme. Optionally avoid keys already used (for distinct takes)."""
    exclude = set(exclude or [])
    pool = [t for t in THEMES if t.key not in exclude] or THEMES
    rng = random.Random(seed) if seed is not None else random
    return rng.choice(pool)


def compose_prompt(scene: str, theme: Optional[Theme]) -> str:
    """Combine an LLM-written scene with a theme's style block + quality tags."""
    scene = (scene or "").strip().rstrip(".")
    if not theme:
        return f"{scene}. {QUALITY_TAGS}"
    return f"{scene}. {theme.style}. {QUALITY_TAGS}"
