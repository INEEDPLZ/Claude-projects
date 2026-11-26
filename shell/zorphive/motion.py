"""Motion level for the always-on Hive widgets (jars, clock, vitals, media marquee).

  full   redraw every frame (the original look; fine on any recent GPU)
  lite   ~15 fps for ambient animation: same look, a fraction of the GPU/CPU cost
  still  1 fps: widgets only update their numbers; nothing wobbles

Each ambient redraw also makes Hyprland re-blur whatever sits behind the widget, so on older
laptops (e.g. a 2013/14 MacBook Pro with Intel Iris at 2560x1600) "lite" is the difference
between sluggish and smooth. Opened things (the Eye, planet travel, cursor trail) always run at
full frame rate: they're short and you're looking at them.
"""
import time

from gi.repository import GLib

FPS = {"lite": 15, "still": 1}
_level = "full"


def set_level(level):
    global _level
    _level = level if level in ("full", "lite", "still") else "full"


def level():
    return _level


def drive(widget, tick):
    """Call tick(dt_seconds) repeatedly while `widget` is shown, at the current motion level.

    tick returns True to keep going (like a GTK tick callback)."""
    state = {"t": time.monotonic()}

    def step():
        now = time.monotonic()
        dt, state["t"] = min(now - state["t"], 0.5), now
        return tick(dt)

    if _level == "full":
        widget.add_tick_callback(lambda *_: step())
        return

    def timer():
        if widget.get_mapped():
            return step()
        state["t"] = time.monotonic()
        return True

    GLib.timeout_add(int(1000 / FPS[_level]), timer)


def redraw(widget):
    """Ambient animation that is just 'repaint, the draw function reads the clock'."""
    drive(widget, lambda _dt: (widget.queue_draw(), True)[1])
