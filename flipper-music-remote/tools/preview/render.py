#!/usr/bin/env python3
"""Replay a scripted session through the real TAPE//DECK drawing code -> PNGs + GIF.

    python3 extract_fonts.py <firmware.elf> > fonts.h      # Flipper's real fonts
    gcc -O2 -Istubs -o deck_preview preview.c -lm
    python3 render.py ./deck_preview out/
"""
import os
import subprocess
import sys

from PIL import Image

binary, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

UP, DOWN, RIGHT, LEFT, OK = 0, 1, 2, 3, 4
PRESS, RELEASE, SHORT, LONG, REPEAT = 0, 1, 2, 3, 4
script = [
    ("C", 2600, "1"),                       # iPhone connects
    ("I", 7000, f"{RIGHT} {SHORT}"),        # skip -> eject + new tape
    ("I", 9500, f"{UP} {PRESS}"),
    ("I", 9700, f"{UP} {REPEAT}"),
    ("I", 10600, f"{RIGHT} {LONG}"),        # hold fast-forward
    ("I", 11800, f"{RIGHT} {RELEASE}"),
    ("I", 12800, f"{LEFT} {SHORT}"),        # >3 s in -> rewind/restart
    ("I", 14300, f"{LEFT} {SHORT}"),        # <3 s in -> previous tape
    ("I", 16200, f"{OK} {SHORT}"),          # pause
    ("E", 18000, ""),
]
text = "\n".join(f"{k} {t} {v}" for k, t, v in script) + "\n"
raw = subprocess.run([binary], input=text.encode(), capture_output=True, check=True).stdout
N = 128 * 64
frames = [raw[i:i + N] for i in range(0, len(raw), N)]

SCALE = 4
FG, BG = (0, 0, 0), (255, 130, 0)


def to_img(fb):
    im = Image.new("RGB", (128, 64), BG)
    im.putdata([FG if b else BG for b in fb])
    return im.resize((128 * SCALE, 64 * SCALE), Image.NEAREST)


imgs = [to_img(f) for f in frames]
imgs[0].save(os.path.join(out, "tapedeck.gif"), save_all=True, append_images=imgs[1:],
             duration=33, loop=0, optimize=True)
shots = {"boot": 2400, "link": 2900, "insert": 3500, "play": 6000, "skip_ff": 7150,
         "eject": 7500, "load": 7900, "volume": 9800, "ff_hold": 11400, "restart": 13000,
         "prev": 14500, "paused": 17000}
for name, ms in shots.items():
    imgs[ms // 33].save(os.path.join(out, f"{name}.png"))
print(f"{len(frames)} frames -> {out}")
