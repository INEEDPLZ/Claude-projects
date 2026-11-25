#!/usr/bin/env python3
"""Generate the 'Zorp' icon theme: folders are glowing silk cocoons (original art, tokens palette).

usage: gen-icons.py OUTDIR      -> OUTDIR/Zorp/{index.theme, scalable/places/*.svg}
Inherits Adwaita + hicolor for everything not drawn here.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "themes/tokens.json").read_text())["color"]

# emblem drawings in a 128x128 box, centered around (64, 70); stroke-based, chrome-dark color
EMBLEMS = {
    "folder": "",
    "folder-open": '<ellipse cx="64" cy="66" rx="14" ry="20" fill="{acid_glow}" opacity="0.9"/>',
    "folder-documents": '<path d="M52 52h18l8 8v26H52z" fill="{chrome_hi}" stroke="{chrome_dark}" stroke-width="3"/><path d="M57 66h16M57 73h16M57 80h10" stroke="{chrome_dark}" stroke-width="3"/>',
    "folder-download": '<path d="M64 50v30M52 70l12 12 12-12" fill="none" stroke="{chrome_hi}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>',
    "folder-music": '<path d="M58 82V54l22-5v28" fill="none" stroke="{chrome_hi}" stroke-width="5"/><circle cx="53" cy="82" r="7" fill="{chrome_hi}"/><circle cx="75" cy="77" r="7" fill="{chrome_hi}"/>',
    "folder-pictures": '<path d="M48 84l12-16 9 10 7-8 12 14z" fill="{chrome_hi}"/><circle cx="74" cy="58" r="5" fill="{acid_glow}"/>',
    "folder-videos": '<rect x="48" y="56" width="32" height="26" rx="4" fill="{chrome_hi}"/><path d="M60 62l11 7-11 7z" fill="{chrome_dark}"/>',
    "folder-templates": '<rect x="50" y="52" width="28" height="34" rx="3" fill="none" stroke="{chrome_hi}" stroke-width="4" stroke-dasharray="5 4"/>',
    "folder-publicshare": '<circle cx="64" cy="68" r="15" fill="none" stroke="{chrome_hi}" stroke-width="4"/><path d="M49 68h30M64 53c-8 9-8 21 0 30M64 53c8 9 8 21 0 30" fill="none" stroke="{chrome_hi}" stroke-width="3"/>',
    "folder-remote": '<path d="M50 74a14 14 0 0 1 28 0M56 74a8 8 0 0 1 16 0" fill="none" stroke="{chrome_hi}" stroke-width="4"/><circle cx="64" cy="78" r="4" fill="{chrome_hi}"/>',
    "user-home": '<path d="M48 70l16-14 16 14v16H48z" fill="{chrome_hi}"/><rect x="60" y="74" width="8" height="12" fill="{chrome_dark}"/>',
    "user-desktop": '<rect x="48" y="54" width="32" height="22" rx="3" fill="{chrome_hi}"/><path d="M58 84h12M64 76v8" stroke="{chrome_hi}" stroke-width="4"/>',
    "user-trash": '<path d="M52 58h24l-3 28H55z" fill="{chrome_hi}"/><path d="M49 56h30" stroke="{chrome_hi}" stroke-width="4"/>',
}

COCOON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <radialGradient id="g" cx="40%" cy="32%" r="75%">
      <stop offset="0" stop-color="{aqua_glow}"/>
      <stop offset="0.45" stop-color="{aqua}"/>
      <stop offset="1" stop-color="{teal_deep}"/>
    </radialGradient>
    <radialGradient id="halo" cx="50%" cy="55%" r="50%">
      <stop offset="0.6" stop-color="{acid}" stop-opacity="0.45"/>
      <stop offset="1" stop-color="{acid}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="silk" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{chrome_hi}" stop-opacity="0.15"/>
      <stop offset="0.5" stop-color="{chrome_hi}" stop-opacity="0.85"/>
      <stop offset="1" stop-color="{chrome_hi}" stop-opacity="0.15"/>
    </linearGradient>
  </defs>
  <ellipse cx="64" cy="70" rx="60" ry="56" fill="url(#halo)"/>
  <!-- hanging thread -->
  <path d="M64 2 C 60 8, 68 12, 64 18" fill="none" stroke="{chrome}" stroke-width="2.5" stroke-linecap="round"/>
  <!-- cocoon body: pointed top, round belly -->
  <path d="M64 16 C 92 26, 104 58, 100 84 C 96 110, 80 122, 64 122 C 48 122, 32 110, 28 84 C 24 58, 36 26, 64 16 Z" fill="url(#g)"/>
  <!-- silk wraps -->
  <path d="M34 50 C 52 60, 78 44, 96 54" fill="none" stroke="url(#silk)" stroke-width="4"/>
  <path d="M29 78 C 50 90, 80 70, 99 82" fill="none" stroke="url(#silk)" stroke-width="4"/>
  <path d="M36 104 C 54 114, 76 98, 92 106" fill="none" stroke="url(#silk)" stroke-width="4"/>
  <!-- gloss -->
  <path d="M46 34 C 54 26, 64 24, 70 25 C 60 34, 52 48, 44 60 C 40 52, 40 42, 46 34 Z" fill="#ffffff" opacity="0.55"/>
  {emblem}
</svg>
"""


def main():
    out = pathlib.Path(sys.argv[1]) / "Zorp"
    places = out / "scalable" / "places"
    places.mkdir(parents=True, exist_ok=True)
    fmt = {k.replace("-", "_"): v for k, v in C.items()}
    for name, emblem in EMBLEMS.items():
        svg = COCOON.format(emblem=emblem.format(**fmt), **fmt)
        (places / f"{name}.svg").write_text(svg)
    (out / "index.theme").write_text(
        "[Icon Theme]\nName=Zorp\nComment=ZorpOS: folders are cocoons\nInherits=Adwaita,hicolor\n"
        "Directories=scalable/places\n\n[scalable/places]\nSize=128\nMinSize=16\nMaxSize=512\n"
        "Type=Scalable\nContext=Places\n")
    print(f"icons -> {out}")


if __name__ == "__main__":
    main()
