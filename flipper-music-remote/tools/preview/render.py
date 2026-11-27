#!/usr/bin/env python3
"""Replay a scripted session through the real Flipper drawing code and write a GIF.

    python3 extract_fonts.py ~/.ufbt/current/firmware.elf > fonts.h
    gcc -O2 -Istubs -o fliptune_preview preview.c -lm
    python3 render.py ./fliptune_preview out_dir/
"""
import math
import os
import subprocess
import sys
import types

from PIL import Image, ImageDraw

sys.modules.setdefault("bleak", types.SimpleNamespace(BleakClient=object, BleakScanner=object))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "companion-mac"))
import fliptune_mac as ft  # noqa: E402  (reuses the real framing + dithering code)

binary, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)


def cover_sunset(path):
    im = Image.new("RGB", (300, 300))
    d = ImageDraw.Draw(im)
    for y in range(300):
        d.line([(0, y), (300, y)], fill=(40 + y // 3, 10, 90 + y // 4))
    d.ellipse([70, 50, 230, 210], fill=(255, 170, 60))
    for i, y in enumerate(range(120, 210, 14)):
        d.rectangle([60, y, 240, y + 3 + i], fill=(60, 20, 110))
    d.rectangle([0, 200, 300, 300], fill=(20, 5, 40))
    for x in range(-300, 600, 40):
        d.line([(150, 200), (x, 300)], fill=(200, 60, 200), width=2)
    for y in (215, 235, 262, 295):
        d.line([(0, y), (300, y)], fill=(200, 60, 200), width=2)
    im.save(path)


def cover_portrait(path):
    im = Image.new("RGB", (300, 300), (235, 230, 220))
    d = ImageDraw.Draw(im)
    for r in range(150, 0, -18):
        d.ellipse([150 - r, 150 - r, 150 + r, 150 + r], outline=(30, 30, 30), width=5)
    d.ellipse([105, 105, 195, 195], fill=(20, 20, 20))
    d.ellipse([135, 135, 165, 165], fill=(235, 230, 220))
    im.save(path)


def frames_hex(frames):
    return "".join(f.hex() for f in frames)


def art_frames(path):
    bits = ft.dither_art(path)
    fr = [ft.frame(ft.MSG_ART_CHUNK, off.to_bytes(2, "little") + bits[off:off + ft.ART_CHUNK])
          for off in range(0, len(bits), ft.ART_CHUNK)]
    return fr + [ft.frame(ft.MSG_ART_DONE)]


def state(playing, pos_s, dur_s, vol):
    return ft.frame(ft.MSG_STATE, bytes([playing]) + int(pos_s * 1000).to_bytes(4, "little")
                    + int(dur_s * 1000).to_bytes(4, "little") + bytes([vol]))


def track(t, a, al):
    return ft.frame(ft.MSG_TRACK, f"{t}\0{a}\0{al}\0".encode())


cover_sunset(os.path.join(out, "cover_a.png"))
cover_portrait(os.path.join(out, "cover_b.png"))
OK, RIGHT, UP, LEFT = 4, 2, 0, 3
SHORT, LONG, REPEAT = 2, 3, 4
script = [
    ("C", 1800, "1"),
    ("R", 3200, frames_hex([track("Night Drive", "Neon Static", "Coastline"), state(1, 62, 214, 50)])),
    ("R", 3900, frames_hex(art_frames(os.path.join(out, "cover_a.png")))),
    ("I", 7000, f"{RIGHT} {SHORT}"),
    ("R", 7300, frames_hex([track("Everything Echoes Back When The Lights Go Out", "The Hollow Arcade", "Signal / Noise"),
                            state(1, 0, 245, 50)])),
    ("R", 7700, frames_hex(art_frames(os.path.join(out, "cover_b.png")))),
    ("I", 11500, f"{UP} {SHORT}"),
    ("I", 11800, f"{UP} {SHORT}"),
    ("R", 12000, frames_hex([state(1, 4.7, 245, 62)])),
    ("I", 13600, f"{RIGHT} {LONG}"),
    ("I", 15000, f"{OK} {SHORT}"),
    ("E", 17500, ""),
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
imgs[0].save(os.path.join(out, "fliptune.gif"), save_all=True, append_images=imgs[1:],
             duration=33, loop=0, optimize=True)
for name, ms in {"waiting": 1000, "idle": 2600, "loading": 3500, "player": 6000,
                 "next_fx": 7100, "marquee": 10400, "volume": 12100, "paused": 16000}.items():
    imgs[ms // 33].save(os.path.join(out, f"{name}.png"))
print(f"{len(frames)} frames -> {out}")
