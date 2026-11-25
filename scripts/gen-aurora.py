#!/usr/bin/env python3
"""Procedural teal/green aurora generator (original artwork, stdlib only).

Usage:
  gen-aurora.py wallpaper OUT.svg [--w 3840 --h 2160 --seed 42]
  gen-aurora.py splash    OUT.svg [--mascot themes/branding/zorp-mascot.svg]

Colors come exclusively from themes/tokens.json.
"""
import argparse
import json
import math
import pathlib
import random
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "themes/tokens.json").read_text())["color"]


def ribbon(rng, w, h, base_y, amp, thick, phase, freq):
    """A closed wavy band across the canvas built from cubic segments."""
    steps = 24
    top, bot = [], []
    for i in range(steps + 1):
        x = -w * 0.1 + (w * 1.2) * i / steps
        t = i / steps
        y = (base_y
             + amp * math.sin(2 * math.pi * freq * t + phase)
             + amp * 0.35 * math.sin(2 * math.pi * freq * 2.3 * t + phase * 1.7))
        th = thick * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * t * 1.3 + phase)))
        top.append((x, y - th / 2))
        bot.append((x, y + th / 2))
    pts = top + bot[::-1]
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f} "
    # Catmull-Rom -> smooth polyline approximation via quadratic midpoints
    for a, b in zip(pts, pts[1:] + pts[:1]):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        d += f"Q{a[0]:.1f},{a[1]:.1f} {mx:.1f},{my:.1f} "
    return d + "Z"


def aurora(w, h, seed):
    rng = random.Random(seed)
    s = []
    s.append(f"""<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0.35" y2="1">
    <stop offset="0" stop-color="{C['void']}"/>
    <stop offset="0.45" stop-color="{C['teal-deep']}"/>
    <stop offset="0.8" stop-color="{C['teal']}"/>
    <stop offset="1" stop-color="{C['abyss']}"/>
  </linearGradient>
  <linearGradient id="bandA" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{C['aqua']}" stop-opacity="0"/>
    <stop offset="0.3" stop-color="{C['aqua']}" stop-opacity="0.55"/>
    <stop offset="0.7" stop-color="{C['acid']}" stop-opacity="0.45"/>
    <stop offset="1" stop-color="{C['acid']}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="bandB" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{C['acid-glow']}" stop-opacity="0"/>
    <stop offset="0.5" stop-color="{C['aqua-glow']}" stop-opacity="0.5"/>
    <stop offset="1" stop-color="{C['glass-blue']}" stop-opacity="0"/>
  </linearGradient>
  <filter id="blurBig" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="{w/90:.1f}"/></filter>
  <filter id="blurSmall" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="{w/700:.1f}"/></filter>
</defs>
<rect width="{w}" height="{h}" fill="url(#sky)"/>""")
    # soft wide aurora curtains
    for i in range(5):
        d = ribbon(rng, w, h, h * rng.uniform(0.35, 0.8), h * rng.uniform(0.06, 0.16),
                   h * rng.uniform(0.12, 0.3), rng.uniform(0, 6.28), rng.uniform(0.6, 1.4))
        grad = "bandA" if i % 2 == 0 else "bandB"
        s.append(f'<path d="{d}" fill="url(#{grad})" opacity="{rng.uniform(0.45, 0.8):.2f}" filter="url(#blurBig)"/>')
    # vertical light curtains (the "rays")
    for _ in range(26):
        x = rng.uniform(0, w)
        bw = rng.uniform(w * 0.002, w * 0.02)
        s.append(f'<rect x="{x:.0f}" y="0" width="{bw:.1f}" height="{h}" fill="{C["aqua-glow"]}" '
                 f'opacity="{rng.uniform(0.03, 0.12):.2f}" filter="url(#blurSmall)"/>')
    # thin crisp light streaks
    for i in range(7):
        d = ribbon(rng, w, h, h * rng.uniform(0.55, 0.95), h * rng.uniform(0.04, 0.1),
                   h * rng.uniform(0.004, 0.012), rng.uniform(0, 6.28), rng.uniform(0.5, 1.1))
        col = C["acid-glow"] if i % 3 == 0 else C["aqua-glow"]
        s.append(f'<path d="{d}" fill="{col}" opacity="{rng.uniform(0.35, 0.75):.2f}" filter="url(#blurSmall)"/>')
    return "\n".join(s)


def embed(svg_path, x, y, size):
    raw = pathlib.Path(svg_path).read_text()
    raw = re.sub(r"<\?xml.*?\?>", "", raw)
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    raw = re.sub(r"<svg ", f'<svg x="{x}" y="{y}" ', raw, count=1)
    raw = re.sub(r'width="\d+" height="\d+"', f'width="{size}" height="{size}"', raw, count=1)
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["wallpaper", "splash"])
    ap.add_argument("out")
    ap.add_argument("--w", type=int)
    ap.add_argument("--h", type=int)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--mascot", default=str(ROOT / "themes/branding/zorp-mascot.svg"))
    a = ap.parse_args()
    if a.kind == "wallpaper":
        w, h = a.w or 3840, a.h or 2160
        body = aurora(w, h, a.seed)
    else:  # syslinux splash: 640x480, mascot top-center, menu drawn below by vesamenu
        w, h = a.w or 640, a.h or 480
        body = aurora(w, h, a.seed)
        body += f'\n<rect width="{w}" height="{h}" fill="{C["void"]}" opacity="0.25"/>'
        body += "\n" + embed(a.mascot, (w - 190) // 2, 6, 190)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'viewBox="0 0 {w} {h}" width="{w}" height="{h}">\n{body}\n</svg>\n')
    pathlib.Path(a.out).write_text(svg)


if __name__ == "__main__":
    main()
