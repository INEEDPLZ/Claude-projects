#!/usr/bin/env python3
"""Plymouth 'landing UFO' art (original): UFO with Zorp in the dome, tractor beam, landing pad, UI bits.
usage: gen-plymouth-art.py OUTDIR   -> writes *.svg (the PKGBUILD renders them to PNG with rsvg-convert)"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "themes/tokens.json").read_text())["color"]
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)

mascot = (ROOT / "themes/branding/zorp-mascot.svg").read_text()
mascot = re.sub(r"<\?xml.*?\?>|<!--.*?-->", "", mascot, flags=re.S)
mascot = re.sub(r'<svg ', '<svg x="170" y="34" ', mascot, count=1)
mascot = re.sub(r'width="\d+" height="\d+"', 'width="160" height="160"', mascot, count=1)

ufo = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 300" width="500" height="300">
<defs>
  <linearGradient id="hull" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{C['chrome-hi']}"/><stop offset="0.45" stop-color="{C['chrome']}"/>
    <stop offset="0.55" stop-color="{C['chrome-lo']}"/><stop offset="1" stop-color="{C['chrome-dark']}"/>
  </linearGradient>
  <radialGradient id="dome" cx="40%" cy="30%" r="75%">
    <stop offset="0" stop-color="{C['aqua-glow']}" stop-opacity="0.55"/>
    <stop offset="1" stop-color="{C['teal']}" stop-opacity="0.25"/>
  </radialGradient>
  <clipPath id="domeclip"><path d="M140 172 C 140 20, 360 20, 360 172 Z"/></clipPath>
</defs>
<g clip-path="url(#domeclip)">{mascot}</g>
<path d="M140 172 C 140 20, 360 20, 360 172 Z" fill="url(#dome)" stroke="{C['aqua-glow']}" stroke-width="3"/>
<path d="M165 110 C 180 70, 225 55, 250 56 C 222 74, 196 100, 178 140 Z" fill="#fff" opacity="0.5"/>
<ellipse cx="250" cy="185" rx="240" ry="52" fill="url(#hull)" stroke="{C['chrome-dark']}" stroke-width="2"/>
<ellipse cx="250" cy="172" rx="200" ry="20" fill="#fff" opacity="0.35"/>
<ellipse cx="250" cy="214" rx="120" ry="18" fill="{C['chrome-dark']}"/>
{''.join(f'<circle cx="{x}" cy="{y}" r="9" fill="{C[col]}"/><circle cx="{x}" cy="{y}" r="15" fill="{C[col]}" opacity="0.3"/>'
         for x, y, col in ((70,190,'acid'),(140,207,'aqua'),(250,215,'acid'),(360,207,'aqua'),(430,190,'acid')))}
</svg>"""
(out / "ufo.svg").write_text(ufo)

beam = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 500" width="400" height="500">
<defs><linearGradient id="b" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{C['acid-glow']}" stop-opacity="0.85"/>
  <stop offset="1" stop-color="{C['aqua']}" stop-opacity="0.05"/></linearGradient></defs>
<path d="M150 0 L 250 0 L 400 500 L 0 500 Z" fill="url(#b)"/>
{''.join(f'<ellipse cx="200" cy="{y}" rx="{60 + y * 0.28}" ry="8" fill="none" stroke="{C["acid-glow"]}" stroke-opacity="0.35" stroke-width="3"/>' for y in (90, 200, 310, 420))}
</svg>"""
(out / "beam.svg").write_text(beam)

pad = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 120" width="600" height="120">
<defs><radialGradient id="p" cx="50%" cy="50%" r="50%">
  <stop offset="0" stop-color="{C['acid']}" stop-opacity="0.7"/><stop offset="1" stop-color="{C['acid']}" stop-opacity="0"/></radialGradient></defs>
<ellipse cx="300" cy="60" rx="300" ry="60" fill="url(#p)"/>
<ellipse cx="300" cy="60" rx="190" ry="34" fill="none" stroke="{C['aqua-glow']}" stroke-width="4" stroke-dasharray="14 10"/>
</svg>"""
(out / "pad.svg").write_text(pad)

entry = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 60" width="420" height="60">
<rect x="2" y="2" width="416" height="56" rx="28" fill="{C['void']}" fill-opacity="0.85" stroke="{C['aqua']}" stroke-width="3"/></svg>"""
(out / "entry.svg").write_text(entry)
(out / "bullet.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="20" height="20"><circle cx="10" cy="10" r="7" fill="{C["acid"]}"/></svg>')
(out / "dot.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16"><circle cx="8" cy="8" r="6" fill="{C["aqua-glow"]}"/></svg>')
print(f"plymouth art -> {out}")
