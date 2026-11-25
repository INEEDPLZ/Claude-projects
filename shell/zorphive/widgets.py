"""Desktop widgets (all original designs): Orbital Media Pod, alien clock, Vitals heartbeat monitor."""
import math
import os
import time
from collections import deque
from glob import glob

import cairo
import gi
from gi.repository import GLib, Gtk

from . import layer
from .glyphs import GlyphLabel
from .theme import rgba

try:
    gi.require_version("Playerctl", "2.0")
    from gi.repository import Playerctl
except (ValueError, ImportError):
    Playerctl = None

try:
    import psutil
except ImportError:
    psutil = None


def _chrome(cr, y0, y1):
    g = cairo.LinearGradient(0, y0, 0, y1)
    for stop, name in ((0, "chrome-hi"), (0.4, "chrome"), (0.5, "chrome-lo"), (0.62, "chrome"), (1, "chrome-dark")):
        g.add_color_stop_rgb(stop, *rgba(name, 1)[:3])
    return g


def _pill(cr, x, y, w, h):
    r = h / 2
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, math.pi / 2)
    cr.arc(x + r, y + r, r, math.pi / 2, 3 * math.pi / 2)
    cr.close_path()


# ======================================================================= media pod
class MediaPod:
    W, H = 520, 150

    def __init__(self, app, config):
        self.cfg = config
        self.win = layer.make(app, "media", layer="bottom", anchors=("top", "left"),
                              margins={"top": 40, "left": 40})
        self.player = None
        self.title = ""
        self.scroll = 0.0
        self.playing = False
        self.pos = self.length = 0.0

        ov = Gtk.Overlay()
        shell = Gtk.DrawingArea(content_width=self.W, content_height=self.H)
        shell.set_draw_func(self._draw_shell)
        ov.set_child(shell)

        row = Gtk.Box(spacing=14, margin_start=14, margin_end=26, margin_top=14, margin_bottom=14)
        self.orb = Gtk.DrawingArea(content_width=118, content_height=118)
        self.orb.set_draw_func(self._draw_orb)
        orb_btn = Gtk.Button(tooltip_text="Play / pause")
        orb_btn.add_css_class("flat-orb")
        orb_btn.set_child(self.orb)
        orb_btn.connect("clicked", lambda *_: self._cmd("play_pause"))
        row.append(orb_btn)

        lcd = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True, valign=Gtk.Align.CENTER)
        top = Gtk.Box(spacing=8)
        self.state_lbl = GlyphLabel("Playing", xalign=0, hexpand=True)
        self.state_lbl.add_css_class("dim")
        self.time_lbl = Gtk.Label(label="0:00 / 0:00")
        self.time_lbl.add_css_class("lcd")
        top.append(self.state_lbl)
        top.append(self.time_lbl)
        lcd.append(top)
        self.marquee = Gtk.DrawingArea(content_height=34, hexpand=True)
        self.marquee.set_draw_func(self._draw_marquee)
        lcd.append(self.marquee)
        ctl = Gtk.Box(spacing=6)
        for icon, cmd in (("media-skip-backward-symbolic", "previous"),):
            b = Gtk.Button(icon_name=icon)
            b.add_css_class("chrome-pill")
            b.connect("clicked", lambda _b, c=cmd: self._cmd(c))
            ctl.append(b)
        self.seek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.001)
        self.seek.set_draw_value(False)
        self.seek.set_hexpand(True)
        self.seek.add_css_class("seek")
        self.seek.connect("change-value", self._seek)
        ctl.append(self.seek)
        nb = Gtk.Button(icon_name="media-skip-forward-symbolic")
        nb.add_css_class("chrome-pill")
        nb.connect("clicked", lambda *_: self._cmd("next"))
        ctl.append(nb)
        lcd.append(ctl)
        row.append(lcd)
        ov.add_overlay(row)
        self.win.set_child(ov)

        if Playerctl:
            self.manager = Playerctl.PlayerManager()
            self.manager.connect("name-appeared", self._on_name)
            self.manager.connect("player-vanished", lambda *_: self._pick())
            for name in self.manager.props.player_names:
                self._on_name(self.manager, name)
        GLib.timeout_add(500, self._poll)
        self.marquee.add_tick_callback(self._tick)
        config.connect("earthling-changed", lambda *_: self._refresh_meta())
        self._refresh_meta()
        self.win.set_visible(True)

    # --- MPRIS ---
    def _on_name(self, manager, name):
        p = Playerctl.Player.new_from_name(name)
        p.connect("metadata", lambda *_: self._refresh_meta())
        p.connect("playback-status", lambda *_: self._refresh_meta())
        manager.manage_player(p)
        self._pick()

    def _pick(self):
        players = list(self.manager.props.players) if Playerctl else []
        playing = [p for p in players if p.props.playback_status == Playerctl.PlaybackStatus.PLAYING]
        self.player = (playing or players or [None])[0]
        self._refresh_meta()

    def _cmd(self, what):
        if self.player:
            try:
                getattr(self.player, what)()
            except GLib.Error:
                pass

    def _seek(self, _s, _scroll, value):
        if self.player and self.length:
            try:
                self.player.set_position(int(value * self.length * 1e6))
            except GLib.Error:
                pass
        return False

    def _refresh_meta(self):
        earth = self.cfg.earthling
        if not self.player:
            self.title = "Nothing playing" if earth else "NO TRANSMISSION DETECTED"
            self.playing = False
            self.state_lbl.set_label("Idle")
            return
        try:
            artist = self.player.get_artist() or ""
            title = self.player.get_title() or ""
            self.playing = self.player.props.playback_status == Playerctl.PlaybackStatus.PLAYING
            md = self.player.props.metadata
            self.length = (md["mpris:length"] / 1e6) if md and "mpris:length" in md.keys() else 0
        except GLib.Error:
            artist, title = "", ""
        text = f"{artist} - {title}" if artist else title
        self.title = text.upper() if text else "UNKNOWN SIGNAL"
        self.state_lbl.set_label("Playing" if self.playing else "Paused")

    def _poll(self):
        if self.player:
            try:
                self.pos = self.player.get_position() / 1e6
            except GLib.Error:
                self.pos = 0
            if self.length:
                self.seek.set_value(min(1.0, self.pos / self.length))
        f = lambda s: f"{int(s) // 60}:{int(s) % 60:02d}"  # noqa: E731
        self.time_lbl.set_label(f"{f(self.pos)} / {f(self.length)}")
        return True

    def _tick(self, *_):
        self.scroll += 1.2
        self.marquee.queue_draw()
        self.orb.queue_draw()
        return True

    # --- drawing ---
    def _draw_shell(self, _a, cr, w, h):
        _pill(cr, 4, 6, w - 8, h - 12)
        cr.set_source(_chrome(cr, 6, h - 6))
        cr.fill()
        # glass LCD window
        _pill(cr, 140, 18, w - 160, h - 36)
        g = cairo.LinearGradient(0, 18, 0, h - 18)
        g.add_color_stop_rgb(0, *rgba("glass-blue", 1)[:3])
        g.add_color_stop_rgb(0.5, *rgba("glass-deep", 1)[:3])
        g.add_color_stop_rgb(1, *rgba("abyss", 1)[:3])
        cr.set_source(g)
        cr.fill()
        _pill(cr, 150, 22, w - 180, 22)
        cr.set_source_rgba(1, 1, 1, 0.22)
        cr.fill()

    def _draw_orb(self, _a, cr, w, h):
        cx, cy, r = w / 2, h / 2, min(w, h) / 2 - 4
        glow = 0.5 + 0.5 * math.sin(time.monotonic() * (3 if self.playing else 1))
        cr.arc(cx, cy, r + 3, 0, 2 * math.pi)
        cr.set_source_rgba(*rgba("acid" if self.playing else "aqua", 0.35 + 0.35 * glow))
        cr.fill()
        g = cairo.RadialGradient(cx - r * .35, cy - r * .4, r * .1, cx, cy, r)
        g.add_color_stop_rgb(0, *rgba("aqua-glow", 1)[:3])
        g.add_color_stop_rgb(0.55, *rgba("glass-blue", 1)[:3])
        g.add_color_stop_rgb(1, *rgba("glass-deep", 1)[:3])
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source(g)
        cr.fill()
        cr.set_source_rgba(*rgba("chrome-dark", 0.85))
        if self.playing:  # pause bars
            cr.rectangle(cx - r * .32, cy - r * .38, r * .2, r * .76)
            cr.rectangle(cx + r * .12, cy - r * .38, r * .2, r * .76)
        else:             # play triangle
            cr.move_to(cx - r * .22, cy - r * .38)
            cr.line_to(cx + r * .38, cy)
            cr.line_to(cx - r * .22, cy + r * .38)
            cr.close_path()
        cr.fill()
        hg = cairo.LinearGradient(0, cy - r, 0, cy)
        hg.add_color_stop_rgba(0, 1, 1, 1, 0.75)
        hg.add_color_stop_rgba(1, 1, 1, 1, 0)
        cr.save()
        cr.translate(cx, cy - r * .45)
        cr.scale(r * .7, r * .4)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.set_source(hg)
        cr.fill()

    def _draw_marquee(self, _a, cr, w, h):
        cr.select_font_face("Doto", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(26)
        text = self.title + "   ::   "
        tw = cr.text_extents(text).x_advance or 1
        x = -(self.scroll % tw)
        cr.set_source_rgba(*rgba("aqua-glow", 1))
        while x < w:
            cr.move_to(x, h - 8)
            cr.show_text(text)
            x += tw


# ======================================================================= clock
class Clock:
    S = 176

    def __init__(self, app, config):
        self.cfg = config
        self.win = layer.make(app, "clock", layer="bottom", anchors=("top", "right"),
                              margins={"top": 40, "right": 40})
        ov = Gtk.Overlay()
        self.area = Gtk.DrawingArea(content_width=self.S, content_height=self.S)
        self.area.set_draw_func(self._draw)
        ov.set_child(self.area)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.time = GlyphLabel("", hover_target=ov)
        self.time.add_css_class("lcd")
        self.time.add_css_class("clock-time")
        self.sub = GlyphLabel("", hover_target=ov)
        self.sub.add_css_class("dim")
        box.append(self.time)
        box.append(self.sub)
        ov.add_overlay(box)
        self.win.set_child(ov)
        GLib.timeout_add(1000, self._update)
        self._update()
        self.area.add_tick_callback(lambda *_: (self.area.queue_draw(), True)[1])
        self.win.set_visible(True)

    def _update(self):
        now = time.localtime()
        # digits render as alien numerals (Zorpglyph) until hovered / Earthling Mode
        self.time.set_label(time.strftime("%H:%M", now))
        self.sub.set_label(time.strftime("%a %d %b", now))
        return True

    def _draw(self, _a, cr, w, h):
        cx, cy, r = w / 2, h / 2, w / 2 - 6
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source(_chrome(cr, cy - r, cy + r))
        cr.fill()
        g = cairo.RadialGradient(cx, cy - r * .3, r * .1, cx, cy, r * .82)
        g.add_color_stop_rgb(0, *rgba("teal", 1)[:3])
        g.add_color_stop_rgb(1, *rgba("void", 1)[:3])
        cr.arc(cx, cy, r * .82, 0, 2 * math.pi)
        cr.set_source(g)
        cr.fill()
        # seconds as an orbiting acid dot + arc
        sec = time.time() % 60
        cr.set_line_width(4)
        cr.set_source_rgba(*rgba("acid", 0.8))
        cr.arc(cx, cy, r * .9, -math.pi / 2, -math.pi / 2 + 2 * math.pi * sec / 60)
        cr.stroke()
        a = -math.pi / 2 + 2 * math.pi * sec / 60
        cr.arc(cx + math.cos(a) * r * .9, cy + math.sin(a) * r * .9, 6, 0, 2 * math.pi)
        cr.set_source_rgba(*rgba("acid-glow", 1))
        cr.fill()


# ======================================================================= vitals
def _gpu_busy():
    for p in glob("/sys/class/drm/card*/device/gpu_busy_percent"):
        try:
            return int(open(p).read().strip())
        except (OSError, ValueError):
            pass
    return None


def _temp():
    if not psutil:
        return None
    try:
        temps = psutil.sensors_temperatures()
    except (AttributeError, OSError):
        return None
    for key in ("k10temp", "coretemp", "zenpower", "cpu_thermal", "acpitz"):
        if temps.get(key):
            return temps[key][0].current
    for v in temps.values():
        if v:
            return v[0].current
    return None


class Vitals:
    W, H = 340, 150

    def __init__(self, app, config):
        self.cfg = config
        self.win = layer.make(app, "vitals", layer="bottom", anchors=("bottom", "left"),
                              margins={"bottom": 40, "left": 40})
        self.trace = deque([0.0] * 160, maxlen=160)
        self.phase = 0.0
        self.cpu = 0.0
        self.gpu = None
        self.temp = None
        ov = Gtk.Overlay()
        self.area = Gtk.DrawingArea(content_width=self.W, content_height=self.H)
        self.area.set_draw_func(self._draw)
        ov.set_child(self.area)
        row = Gtk.Box(spacing=16, halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=14)
        self.labels = {}
        for key, name in (("cpu", "Cpu"), ("gpu", "Gpu"), ("temp", "Heat")):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            t = GlyphLabel(name, hover_target=ov)
            t.add_css_class("dim")
            v = Gtk.Label(label="--")
            v.add_css_class("lcd")
            col.append(t)
            col.append(v)
            row.append(col)
            self.labels[key] = v
        ov.add_overlay(row)
        self.win.set_child(ov)
        if psutil:
            psutil.cpu_percent(None)
        GLib.timeout_add(1000, self._sample)
        self.area.add_tick_callback(self._tick)
        self.win.set_visible(True)

    def _sample(self):
        self.cpu = psutil.cpu_percent(None) if psutil else 0.0
        self.gpu = _gpu_busy()
        self.temp = _temp()
        self.labels["cpu"].set_label(f"{self.cpu:.0f}%")
        self.labels["gpu"].set_label(f"{self.gpu}%" if self.gpu is not None else "n/a")
        self.labels["temp"].set_label(f"{self.temp:.0f}°" if self.temp is not None else "n/a")
        return True

    def _tick(self, *_):
        # heartbeat: beat rate rises with CPU load; spike height with load too
        bpm = 50 + self.cpu * 1.1
        self.phase += bpm / 60 / 60
        p = self.phase % 1.0
        amp = 0.35 + self.cpu / 160
        if p < 0.05:
            v = amp * math.sin(p / 0.05 * math.pi) * 0.25
        elif p < 0.09:
            v = -amp * 0.3
        elif p < 0.13:
            v = amp
        elif p < 0.17:
            v = -amp * 0.45
        elif 0.3 < p < 0.42:
            v = amp * 0.3 * math.sin((p - 0.3) / 0.12 * math.pi)
        else:
            v = 0.0
        self.trace.append(v)
        self.area.queue_draw()
        return True

    def _draw(self, _a, cr, w, h):
        _pill(cr, 4, 4, w - 8, h - 8)
        cr.set_source(_chrome(cr, 4, h - 4))
        cr.fill()
        _pill(cr, 14, 14, w - 28, h - 28)
        cr.set_source_rgba(*rgba("void", 0.95))
        cr.fill()
        # grid
        cr.set_source_rgba(*rgba("teal", 0.35))
        cr.set_line_width(1)
        for x in range(30, w - 20, 18):
            cr.move_to(x, 20)
            cr.line_to(x, h - 20)
        cr.stroke()
        # trace
        mid = h * 0.40
        n = len(self.trace)
        cr.set_line_width(2.5)
        for i, v in enumerate(self.trace):
            x = 24 + (w - 48) * i / (n - 1)
            y = mid - v * h * 0.35
            cr.line_to(x, y) if i else cr.move_to(x, y)
        cr.set_source_rgba(*rgba("acid", 1))
        cr.stroke()
