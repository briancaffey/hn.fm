"""Metrics that judge generated content without asking a model.

Each one exists because a specific failure was observed and could not be seen
from the output alone:

* Image sets that were "really good variations of the same image" — the shot
  list cycles but the SUBJECT repeats, so every frame shows the same thing
  from a different angle. `image_set_report` separates those two axes.
* Scripts that ping-pong between speakers, or open every section the same way.
* Digest prose that reuses the same opening across editions.
"""

import math
import re
from collections import Counter
from typing import Dict, List, Sequence

_WORD = re.compile(r"[a-z][a-z'-]{2,}")

# Words that carry no subject information. Kept small on purpose: an
# over-eager stop list hides genuine repetition.
_STOP = {
    "the", "and", "with", "from", "that", "this", "into", "over", "under",
    "across", "against", "around", "through", "while", "where", "which",
    "their", "there", "these", "those", "then", "than", "them", "they",
    "have", "has", "had", "was", "were", "been", "being", "are", "its",
    "for", "not", "but", "all", "one", "two", "his", "her", "him", "she",
    "shot", "view", "angle", "close", "wide", "macro", "overhead", "low",
    "composition", "perspective", "detail", "scene", "image", "frame",
    "black", "white", "ink", "line", "drawing", "illustration", "style",
}


def _tokens(text: str) -> List[str]:
    return [w for w in _WORD.findall((text or "").lower()) if w not in _STOP]


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def lexical_diversity(texts: Sequence[str]) -> float:
    """Distinct content words as a share of all content words, 0-1.

    Low means the same vocabulary over and over.
    """
    words = [w for t in texts for w in _tokens(t)]
    return round(len(set(words)) / max(1, len(words)), 3)


def repeated_openings(texts: Sequence[str], n: int = 4) -> float:
    """Share of items whose first `n` content words duplicate another item's.

    Catches "every section starts the same way", which reads as formulaic long
    before any individual line looks wrong.
    """
    heads = [" ".join(_tokens(t)[:n]) for t in texts if _tokens(t)]
    if len(heads) < 2:
        return 0.0
    counts = Counter(heads)
    dupes = sum(c for c in counts.values() if c > 1)
    return round(dupes / len(heads), 3)


# The handful of nouns that made every take look alike. Not a filter — the
# pipeline may legitimately draw a laptop — but a measurable symptom: a take
# where most frames contain one of these is the failure being reported.
_TECH_TABLEAU = {
    "laptop", "screen", "screens", "monitor", "desk", "desks", "keyboard",
    "smartphone", "phone", "office", "workstation", "terminal", "display",
}


def tableau_rate(prompts: Sequence[str]) -> float:
    """Share of frames containing a default-tech-tableau noun.

    The Jaccard overlap understates the problem because scene prose shares a
    lot of unavoidable connective vocabulary — measured floor for genuinely
    unrelated scenes is 0.161, not 0. This counts the thing a viewer actually
    notices: how many frames are another picture of a desk.
    """
    if not prompts:
        return 0.0
    hits = sum(
        1 for p in prompts if _TECH_TABLEAU & set(_tokens(p))
    )
    return round(hits / len(prompts), 3)


def distinct_head_nouns(prompts: Sequence[str]) -> float:
    """Distinct leading subjects as a share of frames.

    Approximates "how many different things does this take show" by taking the
    first non-stop noun of each scene. 1.0 means every frame opens on
    something new.
    """
    heads = []
    for p in prompts:
        toks = _tokens(p)
        if toks:
            heads.append(toks[0])
    return round(len(set(heads)) / max(1, len(heads)), 3)


def image_set_report(prompts: Sequence[str]) -> Dict:
    """How varied a take's images actually are.

    Two axes, because they fail independently and the fix is different:

    * `subject_overlap` — mean pairwise word overlap between prompts. High
      means the same thing is being drawn repeatedly. This is the number
      behind "really good variations of the same image".
    * `shot_coverage` — how many distinct camera treatments appear. The shot
      list cycles deterministically, so this is usually fine even when the
      subject never changes, which is exactly why the two must be separate.
    """
    prompts = [p for p in prompts if p and p.strip()]
    if len(prompts) < 2:
        return {"n": len(prompts), "subject_overlap": 0.0, "shot_coverage": 0.0,
                "lexical_diversity": 1.0, "max_pair_overlap": 0.0,
                "near_duplicate_pairs": 0}

    sets = [set(_tokens(p)) for p in prompts]
    pairs = [
        _jaccard(sets[i], sets[j])
        for i in range(len(sets)) for j in range(i + 1, len(sets))
    ]
    mean_overlap = sum(pairs) / len(pairs)

    SHOT_TERMS = [
        "wide", "establishing", "macro", "overhead", "top-down", "low-angle",
        "over-the-shoulder", "close-up", "dutch", "aerial", "profile",
        "silhouette", "cutaway", "isometric",
    ]
    seen_shots = {t for p in prompts for t in SHOT_TERMS if t in p.lower()}

    return {
        "n": len(prompts),
        "subject_overlap": round(mean_overlap, 3),
        "max_pair_overlap": round(max(pairs), 3),
        # Pairs sharing more than half their vocabulary are the ones a viewer
        # reads as "the same picture again".
        "near_duplicate_pairs": sum(1 for p in pairs if p > 0.5),
        "shot_coverage": round(len(seen_shots) / max(1, min(len(prompts), len(SHOT_TERMS))), 3),
        "lexical_diversity": lexical_diversity(prompts),
        "tableau_rate": tableau_rate(prompts),
        "distinct_heads": distinct_head_nouns(prompts),
        # Jaccard minus the measured floor for unrelated scenes. Raw overlap
        # cannot go to zero for prose of this length, so the excess is the
        # only honest reading of "more repetitive than chance".
        "excess_overlap": round(max(0.0, mean_overlap - 0.161), 3),
    }


def script_report(sections: Sequence[Dict]) -> Dict:
    """Rhythm and repetition in a generated script.

    `sections` are dicts with `speaker`, `text`, `beat`, `visual_intent`.
    """
    texts = [s.get("text", "") for s in sections]
    speakers = [s.get("speaker") for s in sections]
    intents = [s.get("visual_intent", "") for s in sections]

    switches = sum(
        1 for a, b in zip(speakers, speakers[1:]) if a != b
    ) / max(1, len(speakers) - 1)

    lengths = [len(_tokens(t)) for t in texts]
    mean_len = sum(lengths) / max(1, len(lengths))
    # Coefficient of variation: a script where every section is the same
    # length reads as machine-paced even when each line is fine.
    var = math.sqrt(sum((x - mean_len) ** 2 for x in lengths) / max(1, len(lengths)))
    length_cv = round(var / mean_len, 3) if mean_len else 0.0

    return {
        "sections": len(sections),
        "speaker_switch_rate": round(switches, 3),
        "repeated_openings": repeated_openings(texts),
        "lexical_diversity": lexical_diversity(texts),
        "mean_words": round(mean_len, 1),
        "length_variation": length_cv,
        "intent_overlap": image_set_report(intents)["subject_overlap"] if intents else 0.0,
    }


def digest_report(sections: Sequence[Dict]) -> Dict:
    """Repetition across an edition's composed prose."""
    bodies = [s.get("body", "") for s in sections]
    return {
        "sections": len(sections),
        "repeated_openings": repeated_openings(bodies, n=5),
        "lexical_diversity": lexical_diversity(bodies),
        "mean_words": round(
            sum(len(_tokens(b)) for b in bodies) / max(1, len(bodies)), 1
        ),
    }
