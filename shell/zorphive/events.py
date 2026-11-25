"""Random harmless events. Both can be switched off (hive.json, Personalize Organism, or
`zorp-hivectl set transmissions off` / `set cursor_trail off`) and never run in Earthling Mode.

- Transmissions: roughly once every ~2 hours, a short message from the mothership (a normal desktop
  notification, dismissable, never urgent, never sound-only).
- Cursor trail: roughly once an hour, the pointer leaves a glowing trail for 3 seconds.
"""
import math
import random
import subprocess
import time

from gi.repository import GLib, Gtk

from . import hypr, layer
from .theme import rgba

TRANSMISSIONS = [
    "Mothership log: your houseplants have been catalogued. They seem nice.",
    "Reminder from orbit: hydrate your carbon-based unit.",
    "Signal received: someone nearby is thinking about snacks.",
    "The Hive has counted your open tabs and is impressed.",
    "Survey drone reports the moon is still there. Carry on.",
    "Transmission garbled... ...but the vibes were good.",
    "Specimen status: excellent posture detected. Probably.",
    "Your planet's music has been rated: 'acceptable, with bass'.",
    "Orbital weather: 100% chance of glow.",
    "Tractor beam is idle. Your belongings are safe. For now.",
]


class Events:
    def __init__(self, app, config):
        self.cfg = config
        self.rng = random.Random()
        self.trail = None
        GLib.timeout_add_seconds(600, self._maybe_transmission)   # check every 10 min, p=1/12 -> ~2 h
        GLib.timeout_add_seconds(300, self._maybe_trail)          # check every 5 min, p=1/12 -> ~1 h
        self.app = app

    def _active(self, key):
        return self.cfg.get(key) and not self.cfg.earthling

    def _maybe_transmission(self):
        if self._active("transmissions") and self.rng.random() < 1 / 12:
            self.transmission()
        return True

    def _maybe_trail(self):
        if self._active("cursor_trail") and self.rng.random() < 1 / 12:
            self.cursor_trail()
        return True

    def transmission(self, text=None):
        msg = text or self.rng.choice(TRANSMISSIONS)
        try:
            subprocess.Popen(["notify-send", "-a", "Mothership", "-i", "zorpos", "-u", "low",
                              "Incoming transmission", msg])
        except OSError:
            pass

    def cursor_trail(self, seconds=3.0):
        if self.trail or not hypr.available():
            return
        self.trail = Trail(self.app, seconds, lambda: setattr(self, "trail", None))


class Trail:
    """Click-through overlay that paints fading glow dots where the cursor has been."""

    def __init__(self, app, seconds, done):
        self.win = layer.make(app, "trail", layer="overlay", anchors=("top", "bottom", "left", "right"))
        layer.click_through(self.win)
        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.area.set_draw_func(self._draw)
        self.win.set_child(self.area)
        self.points = []
        self.end = time.monotonic() + seconds
        self.done = done
        mon = (hypr.query("monitors") or [{}])[0]
        self.ox, self.oy = mon.get("x", 0), mon.get("y", 0)
        self.win.set_visible(True)
        self.area.add_tick_callback(self._tick)

    def _tick(self, *_):
        now = time.monotonic()
        pos = hypr.cursor_pos()
        if pos and now < self.end:
            self.points.append((pos[0] - self.ox, pos[1] - self.oy, now))
        self.points = [p for p in self.points if now - p[2] < 0.6]
        self.area.queue_draw()
        if now > self.end and not self.points:
            self.win.destroy()
            self.done()
            return False
        return True

    def _draw(self, _a, cr, w, h):
        now = time.monotonic()
        for i, (x, y, t) in enumerate(self.points):
            age = (now - t) / 0.6
            r = 9 * (1 - age) + 2
            cr.arc(x, y, r, 0, 2 * math.pi)
            name = "acid" if i % 2 else "aqua-glow"
            cr.set_source_rgba(*rgba(name, 0.75 * (1 - age)))
            cr.fill()
