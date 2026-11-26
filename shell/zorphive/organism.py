"""Personalize Organism: ZorpOS settings. Every panel is a differently-shaped organic pod.

Writes ~/.config/zorpos/hive.json (and the Earthling flag), then pokes the running Hive through
zorp-hivectl so changes apply live. In Earthling Mode the labels are plain English (they always
are underneath; GlyphLabels just render them in the alien script until hovered).
"""
import math
import os
import random
import subprocess
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
import cairo  # noqa: E402
from gi.repository import Gtk  # noqa: E402

from . import glyphs, theme  # noqa: E402
from .config import Config  # noqa: E402
from .glyphs import GlyphLabel  # noqa: E402
from .theme import rgba  # noqa: E402

USER_WALL = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "zorpos" / "aurora.png"
GEN_AURORA = "/usr/lib/zorpos/scripts/gen-aurora.py"


def hivectl(*args):
    try:
        subprocess.Popen(["zorp-hivectl", *args])
    except OSError:
        pass


class Pod(Gtk.Overlay):
    """A settings panel inside a seeded organic blob (glass fill, chrome rim)."""

    def __init__(self, title, seed, tint="aqua"):
        super().__init__()
        self.rng = random.Random(seed)
        self.harm = [(self.rng.randint(2, 5), self.rng.uniform(0.03, 0.08), self.rng.uniform(0, 6.28)) for _ in range(3)]
        self.tint = tint
        bg = Gtk.DrawingArea(hexpand=True, vexpand=True)
        bg.set_draw_func(self._draw)
        self.set_child(bg)
        # content sits in the blob's calm middle: centered, with margins clear of the wobbly rim
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                            margin_top=70, margin_bottom=70, margin_start=80, margin_end=80)
        self.body.add_css_class("pod-body")
        self.set_size_request(440, 360)
        head = GlyphLabel(title, xalign=0)
        head.add_css_class("lcd")
        self.body.append(head)
        self.add_overlay(self.body)

    def row(self, label, widget, hint=None):
        r = Gtk.Box(spacing=12)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        col.append(GlyphLabel(label, xalign=0))
        if hint:
            h = Gtk.Label(label=hint, xalign=0, wrap=True, max_width_chars=34)
            h.add_css_class("dim")
            col.append(h)
        r.append(col)
        widget.set_valign(Gtk.Align.CENTER)
        r.append(widget)
        self.body.append(r)
        return widget

    def _blob(self, cr, cx, cy, rx, ry, grow=0.0):
        steps = 90
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            k = 1 + sum(amp * math.sin(n * a + ph) for n, amp, ph in self.harm)
            x = cx + (rx + grow) * k * math.cos(a)
            y = cy + (ry + grow) * k * math.sin(a)
            cr.line_to(x, y) if i else cr.move_to(x, y)
        cr.close_path()

    def _draw(self, _a, cr, w, h):
        cx, cy, rx, ry = w / 2, h / 2, w / 2 - 14, h / 2 - 12
        self._blob(cr, cx, cy, rx * 0.93, ry * 0.86, 6)
        g = cairo.LinearGradient(0, 0, 0, h)
        for stop, name in ((0, "chrome-hi"), (0.45, "chrome"), (0.55, "chrome-lo"), (1, "chrome-dark")):
            g.add_color_stop_rgb(stop, *rgba(name, 1)[:3])
        cr.set_source(g)
        cr.fill()
        self._blob(cr, cx, cy, rx * 0.93, ry * 0.86)
        rg = cairo.RadialGradient(cx - rx * .3, cy - ry * .4, 10, cx, cy, max(rx, ry))
        rg.add_color_stop_rgba(0, *rgba(self.tint, 0.55))
        rg.add_color_stop_rgba(0.6, *rgba("teal-deep", 0.92))
        rg.add_color_stop_rgba(1, *rgba("void", 0.96))
        cr.set_source(rg)
        cr.fill()


class Organism(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="os.zorp.PersonalizeOrganism")

    def do_activate(self):
        self.cfg = Config()
        glyphs.bind_config(self.cfg)
        theme.install_css()
        win = Gtk.ApplicationWindow(application=self, title="Personalize Organism")
        win.add_css_class("zorp-app")
        win.set_default_size(980, 760)
        scroller = Gtk.ScrolledWindow()
        grid = Gtk.FlowBox(max_children_per_line=2, min_children_per_line=1, selection_mode=Gtk.SelectionMode.NONE,
                           row_spacing=6, column_spacing=6, margin_top=10, margin_bottom=10,
                           margin_start=10, margin_end=10, homogeneous=False)
        scroller.set_child(grid)
        win.set_child(scroller)

        def switch(key, active):
            s = Gtk.Switch(active=active)
            s.connect("notify::active", lambda sw, _p: self._set(key, sw.get_active()))
            return s

        mode = Pod("Mode", 11, "acid")
        mode.row("Earthling Mode", switch("earthling", self.cfg.earthling),
                 "English labels, a normal dock and normal workspaces. Super+Shift+E toggles it anywhere.")
        if self.cfg.forced:
            mode.row("Forced on", Gtk.Label(label="zorp.earthling=1"), "Set by the boot menu for this session.")
        levels = ["full", "lite", "still"]
        mot = Gtk.DropDown.new_from_strings(["Full (every frame)", "Lite (calm, ~15 fps)", "Still (numbers only)"])
        cur = self.cfg.get("motion")
        mot.set_selected(levels.index(cur) if cur in levels else 0)
        mot.connect("notify::selected", lambda d, _p: (self.cfg.set("motion", levels[d.get_selected()]),
                                                       hivectl("quit"), self._restart_hive()))
        mode.row("Motion", mot, "How often the jars, clock, vitals and media pod animate. "
                 "Lite or Still makes older laptops much smoother.")
        grid.append(mode)

        ev = Pod("Strange Events", 23, "zorp-lilac")
        ev.row("Transmissions", switch("transmissions", self.cfg.get("transmissions")),
               "A rare, harmless message from the mothership (about once every two hours).")
        ev.row("Cursor trail", switch("cursor_trail", self.cfg.get("cursor_trail")),
               "Occasionally the pointer leaves a 3-second glowing trail.")
        test = Gtk.Button(label="Send a test transmission")
        test.add_css_class("chrome-pill")
        test.connect("clicked", lambda *_: hivectl("transmission"))
        ev.body.append(test)
        grid.append(ev)

        nav = Pod("Navigation", 37, "glass-blue")
        nav.row("Hot corners", switch("corners", self.cfg.get("corners")),
                "Fling the pointer into a corner to summon the Mothership Eye.")
        delay = Gtk.SpinButton.new_with_range(0, 3000, 50)
        delay.set_value(self.cfg.get("glyph_delay_ms"))
        delay.connect("value-changed", lambda s: self.cfg.set("glyph_delay_ms", int(s.get_value())))
        nav.row("Glyph translate delay (ms)", delay, "How long to hover before alien text turns into English.")
        planets = Gtk.SpinButton.new_with_range(3, 9, 1)
        planets.set_value(self.cfg.get("planets"))
        planets.connect("value-changed", lambda s: self.cfg.set("planets", int(s.get_value())))
        nav.row("Planets (workspaces)", planets)
        grid.append(nav)

        look = Pod("Skin", 53, "aqua")
        regrow = Gtk.Button(label="Regrow aurora")
        regrow.add_css_class("chrome-pill")
        regrow.connect("clicked", lambda *_: self._regrow())
        look.row("Wallpaper", regrow, "Grow a new procedural aurora (takes a few seconds).")
        reset = Gtk.Button(label="Original aurora")
        reset.add_css_class("chrome-pill")
        reset.connect("clicked", lambda *_: (USER_WALL.unlink(missing_ok=True), hivectl("quit"), self._restart_hive()))
        look.row("", reset)
        grid.append(look)
        win.present()

    def _set(self, key, value):
        if key == "earthling":
            self.cfg.set_earthling(value)
        else:
            self.cfg.set(key, value)
        hivectl("set", key, "on" if value is True else "off" if value is False else str(value))

    def _regrow(self):
        USER_WALL.parent.mkdir(parents=True, exist_ok=True)
        svg = USER_WALL.with_suffix(".svg")
        seed = str(random.randint(1, 10 ** 6))
        try:
            subprocess.run([sys.executable, GEN_AURORA, "wallpaper", str(svg), "--seed", seed,
                            "--w", "2560", "--h", "1440"], check=True)
            subprocess.run(["rsvg-convert", str(svg), "-o", str(USER_WALL)], check=True)
        except (OSError, subprocess.CalledProcessError) as e:
            print(f"[organism] regrow failed: {e}", file=sys.stderr)
            return
        hivectl("quit")
        self._restart_hive()

    def _restart_hive(self):
        subprocess.Popen(["sh", "-c", "sleep 0.5; exec zorp-hive"], start_new_session=True)


def main():
    return Organism().run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
