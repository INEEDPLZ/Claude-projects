#!/usr/bin/env python3
"""Generate the original 'Zorp' Xcursor theme with cairo + xcursorgen.

usage: gen-cursors.py OUTDIR      -> OUTDIR/Zorp/{index.theme, cursors/*}
needs: python-cairo, xcursorgen
"""
import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile

import cairo

ROOT = pathlib.Path(__file__).resolve().parent.parent
C = json.loads((ROOT / "themes/tokens.json").read_text())["color"]
SIZES = (24, 32, 48)


def rgb(name, a=1.0):
    h = C[name].lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


def chrome(cr, y0, y1):
    g = cairo.LinearGradient(0, y0, 0, y1)
    for stop, n in ((0, "chrome-hi"), (0.45, "chrome"), (0.55, "chrome-lo"), (1, "chrome-dark")):
        g.add_color_stop_rgba(stop, *rgb(n))
    return g


def glow_stroke(cr, color="acid", w=1.0):
    for width, alpha in ((w * 5, 0.18), (w * 3, 0.35)):
        cr.set_source_rgba(*rgb(color, alpha))
        cr.set_line_width(width)
        cr.stroke_preserve()
    cr.set_source_rgba(*rgb("void", 0.9))
    cr.set_line_width(w)
    cr.stroke()


# Every drawer works in a 32x32 design space and returns its hotspot.
def arrow(cr, _t):
    cr.move_to(4, 3); cr.line_to(4, 24); cr.line_to(9.5, 19); cr.line_to(13.5, 28)
    cr.line_to(17, 26.5); cr.line_to(13, 17.5); cr.line_to(20.5, 17.5); cr.close_path()
    cr.set_source(chrome(cr, 3, 28)); cr.fill_preserve(); glow_stroke(cr)
    cr.arc(22, 6, 3, 0, 2 * math.pi); cr.set_source_rgba(*rgb("acid")); cr.fill()      # antenna orb
    cr.move_to(17, 10); cr.line_to(20.5, 7.5); cr.set_source_rgba(*rgb("chrome")); cr.set_line_width(1.2); cr.stroke()
    return 4, 3


def pointer(cr, _t):  # glowing orb with a small aiming arrow
    cr.arc(12, 12, 8, 0, 2 * math.pi)
    g = cairo.RadialGradient(9, 9, 1, 12, 12, 8)
    g.add_color_stop_rgba(0, *rgb("acid-glow")); g.add_color_stop_rgba(1, *rgb("teal"))
    cr.set_source(g); cr.fill_preserve(); glow_stroke(cr, "aqua")
    cr.move_to(4, 4); cr.line_to(10, 6); cr.line_to(6, 10); cr.close_path()
    cr.set_source_rgba(*rgb("chrome-hi")); cr.fill()
    return 4, 4


def text(cr, _t):
    for y in (6, 26):
        cr.move_to(12, y); cr.line_to(20, y)
    cr.move_to(16, 6); cr.line_to(16, 26)
    cr.set_source_rgba(*rgb("void", 0.8)); cr.set_line_width(4); cr.stroke_preserve()
    cr.set_source_rgba(*rgb("aqua-glow")); cr.set_line_width(2); cr.stroke()
    return 16, 16


def wait(cr, t):  # spinning ring with an orbiting acid dot
    cr.arc(16, 16, 10, 0, 2 * math.pi)
    cr.set_source_rgba(*rgb("void", 0.6)); cr.set_line_width(5); cr.stroke()
    cr.arc(16, 16, 10, t * 2 * math.pi, t * 2 * math.pi + 4.2)
    cr.set_source_rgba(*rgb("aqua")); cr.set_line_width(3); cr.stroke()
    a = t * 2 * math.pi + 4.2
    cr.arc(16 + 10 * math.cos(a), 16 + 10 * math.sin(a), 3, 0, 2 * math.pi)
    cr.set_source_rgba(*rgb("acid")); cr.fill()
    return 16, 16


def progress(cr, t):  # arrow + small spinner
    arrow(cr, t)
    cr.save(); cr.translate(14, 14); cr.scale(0.55, 0.55); wait(cr, t); cr.restore()
    return 4, 3


def crosshair(cr, _t):
    cr.arc(16, 16, 7, 0, 2 * math.pi)
    for a, b in (((16, 3), (16, 11)), ((16, 21), (16, 29)), ((3, 16), (11, 16)), ((21, 16), (29, 16))):
        cr.move_to(*a); cr.line_to(*b)
    cr.set_source_rgba(*rgb("void", 0.8)); cr.set_line_width(3.5); cr.stroke_preserve()
    cr.set_source_rgba(*rgb("acid")); cr.set_line_width(1.6); cr.stroke()
    return 16, 16


def double_arrow(angle):
    def draw(cr, _t):
        cr.save(); cr.translate(16, 16); cr.rotate(angle)
        cr.move_to(-12, 0); cr.line_to(-6, -6); cr.line_to(-6, -2.5); cr.line_to(6, -2.5); cr.line_to(6, -6)
        cr.line_to(12, 0); cr.line_to(6, 6); cr.line_to(6, 2.5); cr.line_to(-6, 2.5); cr.line_to(-6, 6); cr.close_path()
        cr.restore()
        cr.set_source(chrome(cr, 4, 28)); cr.fill_preserve(); glow_stroke(cr, "aqua")
        return 16, 16
    return draw


def move(cr, t):
    double_arrow(0)(cr, t)
    double_arrow(math.pi / 2)(cr, t)
    return 16, 16


def not_allowed(cr, _t):
    cr.arc(16, 16, 10, 0, 2 * math.pi)
    cr.move_to(9, 9); cr.line_to(23, 23)
    cr.set_source_rgba(*rgb("void", 0.8)); cr.set_line_width(5); cr.stroke_preserve()
    cr.set_source_rgba(*rgb("danger")); cr.set_line_width(3); cr.stroke()
    return 16, 16


CURSORS = {
    "default": (arrow, 1, ["left_ptr", "arrow", "top_left_arrow", "context-menu", "copy", "alias", "dnd-none",
                           "dnd-move", "dnd-copy", "dnd-link", "grab", "openhand", "grabbing", "closedhand", "vertical-text"]),
    "pointer": (pointer, 1, ["hand1", "hand2", "pointing_hand", "hand"]),
    "text": (text, 1, ["xterm", "ibeam"]),
    "wait": (wait, 12, ["watch"]),
    "progress": (progress, 12, ["left_ptr_watch", "half-busy"]),
    "crosshair": (crosshair, 1, ["cross", "tcross", "cell", "color-picker", "help", "question_arrow"]),
    "ns-resize": (double_arrow(math.pi / 2), 1, ["sb_v_double_arrow", "v_double_arrow", "n-resize", "s-resize",
                                                 "top_side", "bottom_side", "row-resize", "size_ver"]),
    "ew-resize": (double_arrow(0), 1, ["sb_h_double_arrow", "h_double_arrow", "e-resize", "w-resize", "left_side",
                                       "right_side", "col-resize", "size_hor"]),
    "nwse-resize": (double_arrow(math.pi / 4), 1, ["nw-resize", "se-resize", "top_left_corner", "bottom_right_corner",
                                                    "size_fdiag", "bd_double_arrow"]),
    "nesw-resize": (double_arrow(-math.pi / 4), 1, ["ne-resize", "sw-resize", "top_right_corner", "bottom_left_corner",
                                                     "size_bdiag", "fd_double_arrow"]),
    "move": (move, 1, ["all-scroll", "fleur", "size_all", "all-resize"]),
    "not-allowed": (not_allowed, 1, ["crossed_circle", "forbidden", "no-drop", "circle"]),
}


def main():
    out = pathlib.Path(sys.argv[1]) / "ZorpCursors"
    cdir = out / "cursors"
    cdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, (draw, frames, aliases) in CURSORS.items():
            cfg = []
            for size in SIZES:
                for f in range(frames):
                    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
                    cr = cairo.Context(surf)
                    cr.scale(size / 32, size / 32)
                    hx, hy = draw(cr, f / frames)
                    png = os.path.join(tmp, f"{name}-{size}-{f}.png")
                    surf.write_to_png(png)
                    delay = " 60" if frames > 1 else ""
                    cfg.append(f"{size} {round(hx * size / 32)} {round(hy * size / 32)} {png}{delay}")
            conf = os.path.join(tmp, f"{name}.cfg")
            pathlib.Path(conf).write_text("\n".join(cfg) + "\n")
            subprocess.run(["xcursorgen", conf, str(cdir / name)], check=True)
            for alias in aliases:
                link = cdir / alias
                if not link.exists():
                    link.symlink_to(name)
    (out / "index.theme").write_text("[Icon Theme]\nName=ZorpCursors\nComment=ZorpOS cursors (original)\nInherits=Adwaita\n")
    print(f"cursors -> {out}")


if __name__ == "__main__":
    main()
