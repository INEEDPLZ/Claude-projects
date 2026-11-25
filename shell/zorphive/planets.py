"""Workspaces are planets. Switching zooms out to a star map, then dives into the next planet.

Super+1..5 -> `zorp-hivectl planet N` -> travel animation (~0.8 s), then Hyprland switches workspace.
Super+Tab  -> star map stays open; click a planet to travel.
Earthling Mode: no star map, the workspace switch is immediate.
If the Hive isn't running, zorp-hivectl dispatches the workspace switch itself, so keys never break.
"""
import math
import random
import time

import cairo
from gi.repository import Gtk

from . import hypr, layer
from .theme import rgba

# Invented planet names; shown in Zorpglyph (they're plain Latin letters underneath).
NAMES = ["Vreen", "Oolux", "Tazmir", "Quorbel", "Ninthe", "Skelloo", "Prax", "Umbrae", "Yiltz"]
PALETTE = [("aqua", "teal-deep"), ("acid", "teal"), ("zorp-lilac", "zorp-plum"),
           ("glass-blue", "glass-deep"), ("warn", "zorp-plum"), ("aqua-glow", "glass-deep"),
           ("acid-glow", "abyss"), ("danger", "zorp-plum"), ("chrome-hi", "chrome-dark")]

ZOOM_OUT, TRAVEL, DIVE = 0.22, 0.30, 0.28


class Planets:
    def __init__(self, app, config):
        self.cfg = config
        self.win = layer.make(app, "planets", layer="overlay",
                              anchors=("top", "bottom", "left", "right"), keyboard="exclusive")
        self.win.set_visible(False)
        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.area.set_draw_func(self._draw)
        self.win.set_child(self.area)
        rng = random.Random(7)
        self.stars = [(rng.random(), rng.random(), rng.random()) for _ in range(260)]
        self.src = self.dst = 1
        self.t_start = 0.0
        self.mode = "idle"   # idle | travel | map
        click = Gtk.GestureClick()
        click.connect("released", self._click)
        self.area.add_controller(click)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.win.add_controller(keys)
        self.area.add_tick_callback(self._tick)

    @property
    def count(self):
        return int(self.cfg.get("planets"))

    # ------------------------------------------------------------ public
    def travel(self, n):
        n = max(1, int(n))
        if self.cfg.earthling or not hypr.available():
            hypr.focus_workspace(n)
            return
        cur = hypr.active_workspace_id()
        if cur == n and self.mode != "map":
            return
        self.src, self.dst = (cur if self.mode != "map" else self.src), n
        self.mode = "travel"
        self.t_start = time.monotonic()
        self.switched = False
        self.win.set_visible(True)
        self.win.present()

    def show_map(self):
        if self.cfg.earthling:
            return
        self.src = self.dst = hypr.active_workspace_id() or 1
        self.mode = "map"
        self.t_start = time.monotonic()
        self.win.set_visible(True)
        self.win.present()

    # ------------------------------------------------------------ geometry
    def _pos(self, i, w, h):
        """Planets sit on a tilted elliptical orbit around a small sun."""
        ang = 2 * math.pi * (i - 1) / self.count - math.pi / 2
        return w / 2 + math.cos(ang) * w * 0.32, h / 2 + math.sin(ang) * h * 0.30

    def _radius(self, i):
        return 34 + (i * 37 % 5) * 6

    # ------------------------------------------------------------ input
    def _click(self, _g, _n, x, y):
        w, h = self.win.get_width(), self.win.get_height()
        for i in range(1, self.count + 1):
            px, py = self._pos(i, w, h)
            if math.hypot(x - px, y - py) < self._radius(i) + 18:
                self.travel(i)
                return
        self.mode = "idle"
        self.win.set_visible(False)

    def _key(self, _c, keyval, *_):
        from gi.repository import Gdk
        if keyval == Gdk.KEY_Escape:
            self.mode = "idle"
            self.win.set_visible(False)
            return True
        name = Gdk.keyval_name(keyval) or ""
        if name.isdigit() and 1 <= int(name) <= self.count:
            self.travel(int(name))
            return True
        return False

    # ------------------------------------------------------------ animation
    def _tick(self, *_):
        if self.mode == "idle":
            return True
        if self.mode == "travel":
            el = time.monotonic() - self.t_start
            if not self.switched and el >= ZOOM_OUT + TRAVEL + DIVE * 0.6:
                hypr.focus_workspace(self.dst)
                self.switched = True
            if el >= ZOOM_OUT + TRAVEL + DIVE:
                self.mode = "idle"
                self.win.set_visible(False)
        self.area.queue_draw()
        return True

    def _camera(self, w, h):
        """Returns (scale, focus_x, focus_y, fade) for the current moment."""
        if self.mode == "map":
            k = min(1.0, (time.monotonic() - self.t_start) / ZOOM_OUT)
            sx, sy = self._pos(self.src, w, h)
            e = 1 - (1 - k) ** 3
            return 4 - 3 * e, sx + (w / 2 - sx) * e, sy + (h / 2 - sy) * e, e
        el = time.monotonic() - self.t_start
        sx, sy = self._pos(self.src, w, h)
        dx, dy = self._pos(self.dst, w, h)
        if el < ZOOM_OUT:
            e = 1 - (1 - el / ZOOM_OUT) ** 3
            return 4 - 3 * e, sx + (w / 2 - sx) * e, sy + (h / 2 - sy) * e, e
        if el < ZOOM_OUT + TRAVEL:
            return 1.0, w / 2, h / 2, 1.0
        k = min(1.0, (el - ZOOM_OUT - TRAVEL) / DIVE)
        e = k ** 2.2
        return 1 + 7 * e, w / 2 + (dx - w / 2) * e, h / 2 + (dy - h / 2) * e, 1 - max(0, (k - 0.7) / 0.3)

    def _draw(self, _a, cr, w, h):
        if self.mode == "idle":
            return
        s, fx, fy, fade = self._camera(w, h)
        cr.set_source_rgba(*rgba("void", 0.92 * fade))
        cr.paint()
        t = time.monotonic()
        cr.save()
        cr.translate(w / 2, h / 2)
        cr.scale(s, s)
        cr.translate(-fx, -fy)
        for x, y, b in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * (1 + b * 3) + b * 40)
            cr.arc(x * w, y * h, 0.6 + b * 1.4, 0, 2 * math.pi)
            cr.set_source_rgba(*rgba("aqua-glow", (0.25 + 0.6 * tw * b) * fade))
            cr.fill()
        # orbit + sun
        cr.save()
        cr.translate(w / 2, h / 2)
        cr.scale(w * 0.32, h * 0.30)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgba(*rgba("aqua", 0.25 * fade))
        cr.set_line_width(1.5)
        cr.stroke()
        sg = cairo.RadialGradient(w / 2, h / 2, 2, w / 2, h / 2, 60)
        sg.add_color_stop_rgba(0, *rgba("acid-glow", fade))
        sg.add_color_stop_rgba(1, *rgba("acid", 0))
        cr.set_source(sg)
        cr.arc(w / 2, h / 2, 60, 0, 2 * math.pi)
        cr.fill()
        # traveller on the orbit
        if self.mode == "travel":
            el = time.monotonic() - self.t_start
            k = min(1.0, max(0.0, (el - ZOOM_OUT) / TRAVEL))
            a0 = 2 * math.pi * (self.src - 1) / self.count - math.pi / 2
            a1 = 2 * math.pi * (self.dst - 1) / self.count - math.pi / 2
            if a1 - a0 > math.pi:
                a1 -= 2 * math.pi
            elif a0 - a1 > math.pi:
                a1 += 2 * math.pi
            e = k * k * (3 - 2 * k)
            ang = a0 + (a1 - a0) * e
            ux, uy = w / 2 + math.cos(ang) * w * 0.32, h / 2 + math.sin(ang) * h * 0.30
            cr.arc(ux, uy, 7, 0, 2 * math.pi)
            cr.set_source_rgba(*rgba("acid-glow", fade))
            cr.fill()
        occupied = {c.get("workspace", {}).get("id") for c in hypr.clients()} if hypr.available() else set()
        for i in range(1, self.count + 1):
            px, py = self._pos(i, w, h)
            r = self._radius(i)
            hi, lo = PALETTE[(i - 1) % len(PALETTE)]
            g = cairo.RadialGradient(px - r * .35, py - r * .35, r * .1, px, py, r)
            g.add_color_stop_rgba(0, *rgba(hi, fade))
            g.add_color_stop_rgba(1, *rgba(lo, fade))
            cr.arc(px, py, r, 0, 2 * math.pi)
            cr.set_source(g)
            cr.fill()
            if i in (self.dst if self.mode == "travel" else self.src,):
                cr.arc(px, py, r + 8 + 2 * math.sin(t * 4), 0, 2 * math.pi)
                cr.set_source_rgba(*rgba("acid", 0.9 * fade))
                cr.set_line_width(2.5)
                cr.stroke()
            if i in occupied:  # life signs: small moon orbiting inhabited planets
                ma = t * 1.5 + i
                cr.arc(px + math.cos(ma) * (r + 14), py + math.sin(ma) * (r + 14) * 0.5, 4, 0, 2 * math.pi)
                cr.set_source_rgba(*rgba("chrome-hi", fade))
                cr.fill()
            # name in alien glyphs (Latin underneath) + number for the keyboard-minded
            cr.select_font_face("Zorpglyph")
            cr.set_font_size(20)
            name = NAMES[(i - 1) % len(NAMES)]
            ext = cr.text_extents(name)
            cr.move_to(px - ext.width / 2, py + r + 34)
            cr.set_source_rgba(*rgba("aqua-glow", fade))
            cr.show_text(name)
            cr.select_font_face("Comfortaa")
            cr.set_font_size(13)
            cr.move_to(px - 4, py + r + 54)
            cr.set_source_rgba(*rgba("text-dim", fade))
            cr.show_text(str(i))
        cr.restore()
