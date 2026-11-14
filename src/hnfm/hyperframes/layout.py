"""Where on a picture words can go, and where its detail is.

A picture is asked to leave one part of the frame empty for words, but the
image model does not always listen, and a section's own pictures were drawn
with no such request. So the finished picture is measured: edge density
(how much is going on) in each place a panel can sit. Words go where the
picture is calmest, among the places that suit the treatment. The busiest
small area is the picture's detail: where a punch-in cuts to.

Cheap (a 320x180 copy and one edge filter), and the same answer every time.
"""

from typing import Dict, List, Tuple

# Fractions of the frame (x0, y0, x1, y1) a panel would cover. The bottom
# band is the captions' and is never offered.
ZONES: Dict[str, Tuple[float, float, float, float]] = {
    "left": (0.05, 0.12, 0.50, 0.78),
    "right": (0.50, 0.12, 0.95, 0.78),
    "low": (0.05, 0.52, 0.95, 0.79),
    "top": (0.05, 0.08, 0.95, 0.42),
}


def _edges(path: str):
    from PIL import Image, ImageFilter

    img = Image.open(path).convert("L").resize((320, 180))
    return img.filter(ImageFilter.FIND_EDGES)


def busyness(path: str) -> Dict[str, float]:
    """Mean edge strength in each zone, 0 (flat) to 255."""
    e = _edges(path)
    w, h = e.size
    px = e.load()
    out = {}
    for name, (x0, y0, x1, y1) in ZONES.items():
        xs, ys = range(int(x0 * w), int(x1 * w), 2), range(int(y0 * h), int(y1 * h), 2)
        vals = [px[x, y] for y in ys for x in xs]
        out[name] = round(sum(vals) / max(1, len(vals)), 2)
    return out


def calm_order(path: str) -> List[str]:
    """Zones from calmest to busiest."""
    b = busyness(path)
    return sorted(b, key=b.get)


def focus(path: str, grid: Tuple[int, int] = (8, 6)) -> Tuple[int, int]:
    """The busiest cell's centre, in percent of width and height: the detail
    a punch-in goes to. Kept off the very edges."""
    e = _edges(path)
    w, h = e.size
    px = e.load()
    gx, gy = grid
    best, at = -1.0, (50, 50)
    for j in range(1, gy - 1):
        for i in range(1, gx - 1):
            x0, y0 = i * w // gx, j * h // gy
            vals = [px[x, y] for y in range(y0, y0 + h // gy, 2) for x in range(x0, x0 + w // gx, 2)]
            v = sum(vals) / max(1, len(vals))
            if v > best:
                best, at = v, (round(100 * (i + 0.5) / gx), round(100 * (j + 0.5) / gy))
    return at
