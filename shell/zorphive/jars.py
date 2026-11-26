"""Specimen jars: minimized windows live in glass jars on a shelf docked to the right screen edge.

Minimizing (Super+J, or an app's own minimize button) moves a window to Hyprland's hidden
special:jar workspace. Clicking a jar releases the specimen onto the current planet (workspace).
In Earthling Mode the shelf hides and minimized windows show in the normal dock instead.
"""
import math
import time

import cairo
from gi.repository import GLib, Gtk

from . import apps as A, motion
from . import hypr, layer
from .glyphs import GlyphLabel
from .theme import rgba

JAR_W, JAR_H = 74, 104


class Jar(Gtk.Box):
    def __init__(self, client, on_release):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.address = client["address"]
        self.t0 = time.monotonic() + hash(self.address) % 7
        ov = Gtk.Overlay()
        self.area = Gtk.DrawingArea(content_width=JAR_W, content_height=JAR_H)
        self.area.set_draw_func(self._draw)
        ov.set_child(self.area)
        icon = Gtk.Image.new_from_icon_name(_icon_for(client))
        icon.set_pixel_size(36)
        icon.set_valign(Gtk.Align.CENTER)
        icon.set_margin_top(14)
        ov.add_overlay(icon)
        btn = Gtk.Button(tooltip_text=client.get("title") or client.get("class"))
        btn.add_css_class("flat-orb")
        btn.set_child(ov)
        btn.connect("clicked", lambda *_: on_release(self.address))
        self.append(btn)
        lbl = GlyphLabel((client.get("class") or "specimen")[:12], hover_target=btn)
        lbl.add_css_class("pod-label")
        self.append(lbl)
        motion.redraw(self.area)

    def _draw(self, _a, cr, w, h):
        t = time.monotonic() - self.t0
        x0, y0, x1, y1 = 6, 16, w - 6, h - 4
        r = 16
        # lid (chrome)
        lg = cairo.LinearGradient(0, 4, 0, 18)
        lg.add_color_stop_rgb(0, *rgba("chrome-hi", 1)[:3])
        lg.add_color_stop_rgb(0.5, *rgba("chrome-lo", 1)[:3])
        lg.add_color_stop_rgb(1, *rgba("chrome", 1)[:3])
        _rrect(cr, x0 + 4, 4, x1 - x0 - 8, 14, 5)
        cr.set_source(lg)
        cr.fill()
        # glass body
        _rrect(cr, x0, y0, x1 - x0, y1 - y0, r)
        gg = cairo.LinearGradient(x0, 0, x1, 0)
        gg.add_color_stop_rgba(0, *rgba("aqua-glow", 0.35))
        gg.add_color_stop_rgba(0.5, *rgba("teal", 0.18))
        gg.add_color_stop_rgba(1, *rgba("aqua", 0.38))
        cr.set_source(gg)
        cr.fill_preserve()
        cr.set_source_rgba(*rgba("aqua-glow", 0.8))
        cr.set_line_width(1.5)
        cr.stroke()
        # preservation fluid with a slow wave
        level = y0 + (y1 - y0) * 0.38
        cr.save()
        _rrect(cr, x0 + 2, y0 + 2, x1 - x0 - 4, y1 - y0 - 4, r - 2)
        cr.clip()
        cr.move_to(x0, y1)
        for i in range(0, int(x1 - x0) + 1, 3):
            cr.line_to(x0 + i, level + 3 * math.sin(t * 2 + i * 0.15))
        cr.line_to(x1, y1)
        cr.close_path()
        fg = cairo.LinearGradient(0, level, 0, y1)
        fg.add_color_stop_rgba(0, *rgba("acid", 0.35))
        fg.add_color_stop_rgba(1, *rgba("teal-deep", 0.55))
        cr.set_source(fg)
        cr.fill()
        # bubbles
        for k in range(3):
            by = y1 - ((t * 18 + k * 30) % (y1 - level))
            cr.arc(x0 + 14 + k * 16, by, 2.2, 0, 2 * math.pi)
            cr.set_source_rgba(*rgba("acid-glow", 0.7))
            cr.fill()
        cr.restore()
        # gloss streak
        cr.rectangle(x0 + 7, y0 + 8, 5, y1 - y0 - 20)
        cr.set_source_rgba(1, 1, 1, 0.35)
        cr.fill()


def _rrect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _icon_for(client):
    cls = (client.get("class") or client.get("initialClass") or "").lower()
    for cand in (f"{cls}.desktop", f"org.gnome.{cls}.desktop"):
        app = A.by_id(cand)
        if app and app.get_icon():
            return app.get_icon().to_string()
    return cls or "application-x-executable"


class Shelf:
    def __init__(self, app, config):
        self.cfg = config
        self.win = layer.make(app, "jars", layer="top", anchors=("right",), margins={"right": 6})
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=12, margin_bottom=12)
        self.box.add_css_class("dock")
        self.win.set_child(self.box)
        self.known = []
        GLib.timeout_add(1200, self.refresh)
        config.connect("earthling-changed", lambda *_: self.refresh())
        self.refresh()

    def jarred(self):
        return hypr.jarred() if hypr.available() else []

    def refresh(self):
        clients = self.jarred()
        addrs = [c["address"] for c in clients]
        if addrs != self.known:
            self.known = addrs
            child = self.box.get_first_child()
            while child:
                nxt = child.get_next_sibling()
                self.box.remove(child)
                child = nxt
            for c in clients:
                self.box.append(Jar(c, self.release))
        self.win.set_visible(bool(clients) and not self.cfg.earthling)
        return True

    def release(self, address):
        hypr.unjar(address)
        GLib.timeout_add(150, lambda: (self.refresh(), False)[1])
