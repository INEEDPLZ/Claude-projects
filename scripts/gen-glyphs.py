#!/usr/bin/env python3
"""Generate 'Zorpglyph', the invented ZorpOS alien script, as a TTF (requires fontforge's python module).

Each Latin letter A-Z / a-z and digit 0-9 maps to an original alien glyph, so any English string
rendered in this font *is* the alien translation. Swapping the font back to Comfortaa "translates" it.

Letters: built deterministically from a small kit of primitives (stems, rings, dots, arcs, crossbars)
seeded by the letter, so the alphabet is stable across builds.
Digits ("alien numerals"): a ring for 0, otherwise a vertical stem with N notch-dots beside it
(1-5 on the right, 6-9 add a crossbar + dots on the left), readable once you know the rule.

usage: gen-glyphs.py OUT.ttf [--svg-preview OUT.svg]
"""
import argparse
import math
import random

EM, ASC, DESC = 1000, 800, 200
ADV = 640          # advance width
X0, X1 = 110, 530  # drawable box
Y0, Y1 = 0, 700
W = 64             # stroke weight


class Shape:
    """Collects closed polygons/bezier contours in font units (y up)."""

    def __init__(self):
        self.contours = []  # list of list of ('M'|'L'|'C', pts)

    def bar(self, x1, y1, x2, y2, w=W):
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L * w / 2, dx / L * w / 2
        ex, ey = dx / L * w / 2, dy / L * w / 2  # square caps
        pts = [(x1 + nx - ex, y1 + ny - ey), (x2 + nx + ex, y2 + ny + ey),
               (x2 - nx + ex, y2 - ny + ey), (x1 - nx - ex, y1 - ny - ey)]
        self.contours.append([("M", pts[0])] + [("L", p) for p in pts[1:]])

    def circle(self, cx, cy, r, clockwise=False):
        k = 0.5523 * r
        if not clockwise:
            seg = [((cx + r, cy), (cx + r, cy + k), (cx + k, cy + r), (cx, cy + r)),
                   (None, (cx - k, cy + r), (cx - r, cy + k), (cx - r, cy)),
                   (None, (cx - r, cy - k), (cx - k, cy - r), (cx, cy - r)),
                   (None, (cx + k, cy - r), (cx + r, cy - k), (cx + r, cy))]
        else:
            seg = [((cx + r, cy), (cx + r, cy - k), (cx + k, cy - r), (cx, cy - r)),
                   (None, (cx - k, cy - r), (cx - r, cy - k), (cx - r, cy)),
                   (None, (cx - r, cy + k), (cx - k, cy + r), (cx, cy + r)),
                   (None, (cx + k, cy + r), (cx + r, cy + k), (cx + r, cy))]
        c = [("M", seg[0][0])]
        for s in seg:
            c.append(("C", (s[1], s[2], s[3])))
        self.contours.append(c)

    def dot(self, cx, cy, r=W * 0.75):
        self.circle(cx, cy, r)

    def ring(self, cx, cy, r, w=W):
        self.circle(cx, cy, r + w / 2)
        self.circle(cx, cy, r - w / 2, clockwise=True)

    def arc(self, cx, cy, r, a0, a1, w=W, steps=10):
        for i in range(steps):
            t0 = math.radians(a0 + (a1 - a0) * i / steps)
            t1 = math.radians(a0 + (a1 - a0) * (i + 1) / steps)
            self.bar(cx + r * math.cos(t0), cy + r * math.sin(t0),
                     cx + r * math.cos(t1), cy + r * math.sin(t1), w)


def letter(ch):
    rng = random.Random(f"zorp-{ch.upper()}-v1")
    s = Shape()
    cx = (X0 + X1) / 2
    spine = rng.choice(["stem", "ring", "arc", "twin", "hook"])
    if spine == "stem":
        x = rng.choice([cx, X0 + 80, X1 - 80])
        s.bar(x, Y0 + 40, x, Y1 - 40)
    elif spine == "ring":
        s.ring(cx, rng.choice([230, 350, 470]), rng.choice([120, 150, 170]))
    elif spine == "arc":
        a = rng.choice([0, 90, 180, 270])
        s.arc(cx, 350, 190, a + 30, a + 300)
    elif spine == "twin":
        s.bar(X0 + 70, Y0 + 40, X0 + 70, Y1 - 40)
        s.bar(X1 - 70, Y0 + 40, X1 - 70, Y1 - 40 - rng.choice([0, 200]))
    else:  # hook
        s.bar(cx, Y1 - 40, cx, 240)
        s.arc(cx + 110, 240, 110, 180, 360 if rng.random() < .5 else 300)
    for _ in range(rng.randint(1, 3)):
        kind = rng.choice(["dot", "dot", "tick", "cross", "minring", "chev"])
        px, py = rng.uniform(X0 + 40, X1 - 40), rng.uniform(Y0 + 80, Y1 - 60)
        if kind == "dot":
            s.dot(px, py)
        elif kind == "tick":
            ang = math.radians(rng.choice([0, 45, 135]))
            s.bar(px, py, px + 120 * math.cos(ang), py + 120 * math.sin(ang), W * .8)
        elif kind == "cross":
            s.bar(X0 + 30, py, X1 - 30, py, W * .8)
        elif kind == "minring":
            s.ring(px, py, 52, W * .6)
        else:
            s.bar(px - 90, py, px, py + 90, W * .8)
            s.bar(px, py + 90, px + 90, py, W * .8)
    return s


def digit(d):
    s = Shape()
    cx = (X0 + X1) / 2
    if d == 0:
        s.ring(cx, 350, 180)
        s.dot(cx, 350, W * .6)
        return s
    stem_x = cx - 60
    s.bar(stem_x, 40, stem_x, 660)
    right = min(d, 5)
    for i in range(right):
        s.dot(stem_x + 150, 600 - i * 130)
    if d > 5:
        s.bar(stem_x - 120, 350, stem_x + 120, 350, W * .8)
        for i in range(d - 5):
            s.dot(stem_x - 150, 600 - i * 130)
    return s


def to_svg_path(shape, ox=0):
    d = []
    for c in shape.contours:
        for op, p in c:
            if op == "M":
                d.append(f"M{p[0] + ox:.0f},{ASC - p[1]:.0f}")
            elif op == "L":
                d.append(f"L{p[0] + ox:.0f},{ASC - p[1]:.0f}")
            else:
                d.append("C" + " ".join(f"{q[0] + ox:.0f},{ASC - q[1]:.0f}" for q in p))
        d.append("Z")
    return " ".join(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--svg-preview")
    a = ap.parse_args()
    chars = {c: letter(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
    chars.update({str(d): digit(d) for d in range(10)})

    if a.svg_preview:
        keys = list(chars)
        cols = 13
        rows = math.ceil(len(keys) / cols)
        parts = []
        for i, k in enumerate(keys):
            ox, oy = (i % cols) * ADV, (i // cols) * (EM + 200)
            parts.append(f'<g transform="translate(0 {oy})"><path d="{to_svg_path(chars[k], ox)}" fill="#2fd3d0" fill-rule="nonzero"/>'
                         f'<text x="{ox + ADV / 2}" y="{EM + 120}" font-size="110" fill="#8fb8c0" text-anchor="middle" font-family="sans-serif">{k}</text></g>')
        with open(a.svg_preview, "w") as f:
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -50 {cols * ADV} {rows * (EM + 200)}">'
                    f'<rect x="0" y="-50" width="100%" height="100%" fill="#03161c"/>{"".join(parts)}</svg>')

    import fontforge  # noqa: E402  (only needed for the TTF)
    font = fontforge.font()
    font.encoding = "UnicodeFull"
    font.fontname, font.familyname, font.fullname = "Zorpglyph-Regular", "Zorpglyph", "Zorpglyph Regular"
    font.copyright = "ZorpOS. SIL Open Font License 1.1. Original invented script."
    font.em, font.ascent, font.descent = EM, ASC, DESC
    sp = font.createChar(32, "space")
    sp.width = ADV // 2
    for k, shape in chars.items():
        targets = [k] + ([k.lower()] if k.isalpha() else [])
        for t in targets:
            g = font.createChar(ord(t))
            pen = g.glyphPen()
            for c in shape.contours:
                for op, p in c:
                    if op == "M":
                        pen.moveTo(p)
                    elif op == "L":
                        pen.lineTo(p)
                    else:
                        pen.curveTo(*p)
                pen.closePath()
            pen = None
            g.removeOverlap()
            g.correctDirection()
            g.width = ADV
    font.generate(a.out)


if __name__ == "__main__":
    main()
