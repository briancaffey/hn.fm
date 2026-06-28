"""Design identity for HyperFrames compositions.

HyperFrames' authoring skill has a hard rule: every composition must trace its
palette + typography to a defined identity — no generic `#333` / Roboto / Inter.
We already have per-take art-direction themes, so we map each theme to a small
identity (background, foreground, accent, a tasteful font pairing, weight
contrast). This gives every video a *common design language* across its
hyperframe clips, while different takes/themes look genuinely different.

Typography follows the skill's guardrails: NO banned AI-tell fonts (Inter,
Roboto, Poppins, Outfit, Sora, Syne, Playfair…); pair serif+sans or sans+mono;
extreme weight contrast (300 vs 900). Fonts load from Google Fonts at render
time (the render env has network — it already pulls GSAP from a CDN).
"""

from dataclasses import dataclass


@dataclass
class DesignIdentity:
    key: str
    bg: str          # canvas background
    fg: str          # primary text
    muted: str       # secondary text
    accent: str      # highlight / kicker / rules
    display_font: str  # headline (one expressive font per scene)
    body_font: str     # body / labels (recedes)
    display_weight: int = 800
    body_weight: int = 300
    # Google Fonts family list to load (display + body)
    def font_query(self) -> str:
        fams = []
        for fam, w in ((self.display_font, self.display_weight), (self.body_font, self.body_weight)):
            fams.append(f"family={fam.replace(' ', '+')}:wght@{w};{min(900, w + 100)}")
        return "&".join(fams)


# One identity per art-direction theme. Distinctive, non-banned pairings.
_IDENTITIES = {
    "synthwave":   DesignIdentity("synthwave", "#0d0221", "#f6f6ff", "#b39ddb", "#ff2e97", "Unbounded", "Space Grotesk", 800, 300),
    "risograph":   DesignIdentity("risograph", "#f4ecd8", "#1a1a1a", "#5a5a5a", "#ff4d2e", "Bricolage Grotesque", "IBM Plex Mono", 800, 400),
    "watercolor":  DesignIdentity("watercolor", "#fbf7f0", "#2b2b2b", "#7a7a7a", "#3a7ca5", "Fraunces", "Hanken Grotesk", 600, 300),
    "isometric":   DesignIdentity("isometric", "#101418", "#eef2f6", "#9aa7b2", "#4cc9f0", "Space Grotesk", "IBM Plex Mono", 700, 300),
    "noir":        DesignIdentity("noir", "#0a0a0a", "#f5f5f5", "#8a8a8a", "#d4af37", "Gloock", "Archivo", 400, 300),
    "blueprint":   DesignIdentity("blueprint", "#0a2740", "#dbeafe", "#7fa8c9", "#7dd3fc", "Archivo", "IBM Plex Mono", 800, 300),
    "claymation":  DesignIdentity("claymation", "#fff3e6", "#3b2a20", "#8a6f5e", "#ff8c42", "Bricolage Grotesque", "Hanken Grotesk", 800, 400),
    "vaporwave":   DesignIdentity("vaporwave", "#1a1033", "#ffe6ff", "#c9a0dc", "#54f2f2", "Unbounded", "Space Grotesk", 700, 300),
    "papercut":    DesignIdentity("papercut", "#faf3e0", "#222222", "#6b6b6b", "#e63946", "Fraunces", "Archivo", 700, 300),
    "oilpaint":    DesignIdentity("oilpaint", "#1c1610", "#f3e9d2", "#b09a78", "#c1502e", "Gloock", "Spectral", 400, 300),
    "pixelart":    DesignIdentity("pixelart", "#0f1020", "#e8f0ff", "#8b9bb4", "#ffd166", "Space Grotesk", "IBM Plex Mono", 700, 400),
    "infographic": DesignIdentity("infographic", "#ffffff", "#111827", "#6b7280", "#2563eb", "Archivo", "IBM Plex Mono", 800, 300),
}

_DEFAULT = DesignIdentity(
    "default", "#0b0b0f", "#f5f5f7", "#9aa0aa", "#5eead4",
    "Bricolage Grotesque", "Space Grotesk", 800, 300,
)


def identity_for(theme_key: str) -> DesignIdentity:
    """Design identity for an art-direction theme key (falls back gracefully)."""
    return _IDENTITIES.get((theme_key or "").lower(), _DEFAULT)
