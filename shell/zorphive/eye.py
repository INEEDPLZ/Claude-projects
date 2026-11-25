"""The Mothership Eye: summoned with Super or by flinging the pointer into a screen corner.

Layout: a chrome eye at screen center whose pupil follows the pointer. Favorites orbit on the
inner ring; every other app orbits on up to three outer rings. Scrolling spins the rings
(inner and outer in opposite directions). Typing filters apps; Enter launches the first match.
In Earthling Mode the same overlay becomes a plain, alphabetical, English app grid.
"""
import math
import time

from gi.repository import Gdk, GLib, Gtk

from . import apps as A
from .glyphs import GlyphLabel
from .theme import rgba
from . import layer

POD = 64          # pod diameter (px)
SPACING = 104     # arc distance between pods on a ring
INNER_R = 210
RING_GAP = 120
MAX_OUTER = 3


class Eye:
    def __init__(self, app, config):
        self.app, self.cfg = app, config
        self.win = layer.make(app, "eye", layer="overlay",
                              anchors=("top", "bottom", "left", "right"), keyboard="exclusive")
        self.win.set_visible(False)
        self.ptr = (0.0, 0.0)
        self.spin = [0.0, 0.0]        # user scroll offset per ring group (inner, outer)
        self.t0 = time.monotonic()
        self.query = ""
        self.pods = []                # (button, ring_index, slot, slots_on_ring)
        self.open_anim = 0.0

        root = Gtk.Overlay()
        self.canvas = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.canvas.set_draw_func(self._draw)
        root.set_child(self.canvas)
        self.fixed = Gtk.Fixed()
        root.add_overlay(self.fixed)

        # query readout + earthling toggle under the eye
        self.under = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                             halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=60)
        self.qlabel = Gtk.Label(label="")
        self.qlabel.add_css_class("lcd")
        self.qlabel.add_css_class("eye-query")
        self.under.append(self.qlabel)
        self.hint = GlyphLabel("type to search   scroll to spin   esc to close")
        self.hint.add_css_class("dim")
        self.under.append(self.hint)
        self.earth_btn = Gtk.Button()
        self.earth_btn.add_css_class("chrome-pill")
        self.earth_lbl = GlyphLabel("Earthling Mode", hover_target=self.earth_btn)
        self.earth_btn.set_child(self.earth_lbl)
        self.earth_btn.connect("clicked", lambda *_: (self.cfg.toggle_earthling(), self.hide()))
        self.under.append(self.earth_btn)
        root.add_overlay(self.under)

        # earthling grid (hidden in Hive mode)
        self.grid_scroller = Gtk.ScrolledWindow(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                                                min_content_width=760, min_content_height=520)
        self.grid = Gtk.FlowBox(max_children_per_line=6, selection_mode=Gtk.SelectionMode.NONE,
                                row_spacing=12, column_spacing=12)
        self.grid_scroller.set_child(self.grid)
        self.grid_scroller.add_css_class("dock")
        root.add_overlay(self.grid_scroller)
        self.win.set_child(root)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.win.add_controller(keys)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", lambda _c, x, y: setattr(self, "ptr", (x, y)))
        self.win.add_controller(motion)
        scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._scroll)
        self.win.add_controller(scroll)
        click = Gtk.GestureClick()
        click.connect("released", self._background_click)
        self.canvas.add_controller(click)

        self.win.add_tick_callback(self._tick)
        config.connect("earthling-changed", lambda *_: self.win.get_visible() and self.rebuild())

    # ---------------------------------------------------------------- lifecycle
    def toggle(self):
        self.hide() if self.win.get_visible() else self.show()

    def show(self):
        self.query = ""
        self.open_anim = 0.0
        self.rebuild()
        self.win.set_visible(True)
        self.win.present()

    def hide(self):
        self.win.set_visible(False)

    # ---------------------------------------------------------------- content
    def rebuild(self):
        for b, _r, _i, _n, lbl in self.pods:
            self.fixed.remove(b)
            self.fixed.remove(lbl)
        self.pods.clear()
        child = self.grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt

        earthling = self.cfg.earthling
        self.grid_scroller.set_visible(earthling)
        self.hint.set_visible(not earthling)
        self.earth_lbl.set_label("Leave Earthling Mode" if earthling else "Earthling Mode")
        favs, rest = A.split_favorites(self.cfg.get("favorites"))
        q = self.query.lower()
        match = (lambda a: q in a.get_display_name().lower()) if q else (lambda a: True)
        favs, rest = [a for a in favs if match(a)], [a for a in rest if match(a)]
        self.qlabel.set_label(self.query.upper() if self.query else "")

        if earthling:
            for a in favs + rest:
                self.grid.append(self._grid_item(a))
            return

        self._add_ring(favs, 0, fav=True)
        r_i = 1
        while rest and r_i <= MAX_OUTER:
            cap = max(6, int(2 * math.pi * self._radius(r_i) / SPACING))
            self._add_ring(rest[:cap], r_i)
            rest = rest[cap:]
            r_i += 1

    def _radius(self, ring):
        return INNER_R + ring * RING_GAP if ring else INNER_R

    def _add_ring(self, apps, ring, fav=False):
        n = len(apps)
        for i, a in enumerate(apps):
            b = Gtk.Button(tooltip_text=a.get_display_name())
            b.add_css_class("pod")
            if fav:
                b.add_css_class("fav")
            b.set_child(A.icon_image(a, 34))
            b.connect("clicked", lambda _b, app=a: self._launch(app))
            self.fixed.put(b, 0, 0)
            lbl = GlyphLabel(a.get_display_name()[:18], hover_target=b)
            lbl.add_css_class("pod-label")
            self.fixed.put(lbl, 0, 0)
            self.pods.append((b, ring, i, n, lbl))

    def _grid_item(self, a):
        b = Gtk.Button(has_frame=False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.append(A.icon_image(a, 48))
        lbl = Gtk.Label(label=a.get_display_name(), max_width_chars=12, ellipsize=3)
        box.append(lbl)
        b.set_child(box)
        b.connect("clicked", lambda *_: self._launch(a))
        return b

    def _launch(self, app):
        A.launch(app)
        self.hide()

    # ---------------------------------------------------------------- input
    def _key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            first = next((p for p in self.pods), None)
            if first:
                first[0].emit("clicked")
            elif self.cfg.earthling and self.grid.get_child_at_index(0):
                self.grid.get_child_at_index(0).get_child().emit("clicked")
            return True
        if keyval == Gdk.KEY_BackSpace:
            self.query = self.query[:-1]
            self.rebuild()
            return True
        ch = Gdk.keyval_to_unicode(keyval)
        if ch and chr(ch).isprintable():
            self.query += chr(ch)
            self.rebuild()
            return True
        return False

    def _scroll(self, _c, _dx, dy):
        self.spin[0] += dy * 0.12
        self.spin[1] -= dy * 0.08
        return True

    def _background_click(self, _g, _n, x, y):
        w, h = self.win.get_width(), self.win.get_height()
        outer = self._radius(MAX_OUTER) + POD
        if math.hypot(x - w / 2, y - h / 2) > outer:
            self.hide()

    # ---------------------------------------------------------------- animation
    def _tick(self, _w, _clock):
        if not self.win.get_visible():
            return True
        self.open_anim = min(1.0, self.open_anim + 0.08)
        ease = 1 - (1 - self.open_anim) ** 3
        t = time.monotonic() - self.t0
        w, h = self.win.get_width(), self.win.get_height()
        cx, cy = w / 2, h / 2 - 20
        for b, ring, i, n, lbl in self.pods:
            drift = 0.05 * t if ring == 0 else -0.03 * t / ring
            off = self.spin[0] if ring == 0 else self.spin[1] * (1 + 0.3 * ring)
            ang = 2 * math.pi * i / max(n, 1) + drift + off - math.pi / 2
            r = self._radius(ring) * ease
            # gentle wobble so the rings feel organic, not mechanical
            r += 6 * math.sin(t * 1.7 + i)
            x, y = cx + r * math.cos(ang) - POD / 2, cy + r * math.sin(ang) * 0.92 - POD / 2
            self.fixed.move(b, x, y)
            lw = lbl.get_width() or 60
            self.fixed.move(lbl, x + POD / 2 - lw / 2, y + POD + 2)
            b.set_opacity(ease)
            lbl.set_opacity(ease)
        self.canvas.queue_draw()
        return True

    # ---------------------------------------------------------------- drawing
    def _draw(self, _area, cr, w, h):
        a = 1 - (1 - self.open_anim) ** 3
        # dim glass backdrop
        cr.set_source_rgba(*rgba("void", 0.55 * a))
        cr.paint()
        if self.cfg.earthling:
            return
        import cairo
        cx, cy = w / 2, h / 2 - 20
        t = time.monotonic() - self.t0
        # orbit tracks
        for ring in range(0, MAX_OUTER + 1):
            r = self._radius(ring) * a
            cr.save()
            cr.translate(cx, cy)
            cr.scale(1, 0.92)
            cr.arc(0, 0, r, 0, 2 * math.pi)
            cr.restore()
            cr.set_source_rgba(*rgba("aqua" if ring else "acid", 0.22 if ring else 0.35))
            cr.set_line_width(2 if ring else 3)
            cr.set_dash([2, 10] if ring else [], t * 8 % 12)
            cr.stroke()
        cr.set_dash([])
        R = 120 * a
        if R < 2:
            return
        # outer glow
        g = cairo.RadialGradient(cx, cy, R * 0.8, cx, cy, R * 1.8)
        g.add_color_stop_rgba(0, *rgba("aqua", 0.45))
        g.add_color_stop_rgba(1, *rgba("aqua", 0.0))
        cr.set_source(g)
        cr.arc(cx, cy, R * 1.8, 0, 2 * math.pi)
        cr.fill()
        # chrome bezel (almond eye shape)
        def almond(scale):
            cr.new_path()
            cr.move_to(cx - R * 1.45 * scale, cy)
            cr.curve_to(cx - R * 0.7 * scale, cy - R * 1.15 * scale, cx + R * 0.7 * scale, cy - R * 1.15 * scale, cx + R * 1.45 * scale, cy)
            cr.curve_to(cx + R * 0.7 * scale, cy + R * 1.15 * scale, cx - R * 0.7 * scale, cy + R * 1.15 * scale, cx - R * 1.45 * scale, cy)
            cr.close_path()
        lg = cairo.LinearGradient(cx, cy - R, cx, cy + R)
        for stop, name in ((0, "chrome-hi"), (0.42, "chrome"), (0.5, "chrome-lo"), (0.6, "chrome"), (1, "chrome-dark")):
            lg.add_color_stop_rgb(stop, *rgba(name, 1)[:3])
        almond(1.12)
        cr.set_source(lg)
        cr.fill()
        # glass sclera
        sg = cairo.RadialGradient(cx - R * .3, cy - R * .4, R * .1, cx, cy, R * 1.3)
        sg.add_color_stop_rgb(0, *rgba("aqua-glow", 1)[:3])
        sg.add_color_stop_rgb(0.6, *rgba("teal", 1)[:3])
        sg.add_color_stop_rgb(1, *rgba("abyss", 1)[:3])
        almond(1.0)
        cr.set_source(sg)
        cr.fill_preserve()
        cr.save()
        cr.clip()
        # iris + pupil track the pointer
        px, py = self.ptr
        dx, dy = px - cx, py - cy
        d = math.hypot(dx, dy) or 1
        k = min(1.0, d / 500)
        ix, iy = cx + dx / d * R * 0.42 * k, cy + dy / d * R * 0.32 * k
        blink = 1.0 - max(0.0, math.sin(t * 0.9) ** 400)  # rare quick blink
        ir = R * 0.62
        ig = cairo.RadialGradient(ix - ir * .3, iy - ir * .3, ir * .1, ix, iy, ir)
        ig.add_color_stop_rgb(0, *rgba("acid-glow", 1)[:3])
        ig.add_color_stop_rgb(0.45, *rgba("acid", 1)[:3])
        ig.add_color_stop_rgb(1, *rgba("teal-deep", 1)[:3])
        cr.save()
        cr.translate(ix, iy)
        cr.scale(1, max(0.05, blink))
        cr.arc(0, 0, ir, 0, 2 * math.pi)
        cr.restore()
        cr.set_source(ig)
        cr.fill()
        # vertical slit pupil, pulsing
        pw = R * (0.11 + 0.03 * math.sin(t * 2.3))
        cr.save()
        cr.translate(ix, iy)
        cr.scale(pw / (R * .5), max(0.05, blink))
        cr.arc(0, 0, R * .5, 0, 2 * math.pi)
        cr.restore()
        cr.set_source_rgb(*rgba("void", 1)[:3])
        cr.fill()
        cr.restore()
        # gloss highlight
        hg = cairo.LinearGradient(cx, cy - R, cx, cy)
        hg.add_color_stop_rgba(0, 1, 1, 1, 0.65)
        hg.add_color_stop_rgba(1, 1, 1, 1, 0.0)
        cr.save()
        cr.translate(cx - R * .25, cy - R * .5)
        cr.scale(R * .9, R * .35)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.set_source(hg)
        cr.fill()
