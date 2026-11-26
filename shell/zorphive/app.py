"""The Hive application: owns all layer surfaces and exposes actions for zorp-hivectl."""
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, __version__  # noqa: E402
from . import glyphs, hypr, motion, theme  # noqa: E402
from .config import Config  # noqa: E402


class Hive(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.cfg = None
        self.parts = {}

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()  # no regular windows; stay alive
        self.cfg = Config()
        glyphs.bind_config(self.cfg)
        motion.set_level(self.cfg.get("motion"))
        theme.install_css()
        from .dock import Dock
        from .events import Events
        from .eye import Eye
        from .jars import Shelf
        from .planets import Planets
        from .wallpaper import Wallpaper
        from .widgets import Clock, MediaPod, Vitals
        from .corners import Corners
        P = self.parts
        P["wallpaper"] = Wallpaper(self)
        P["eye"] = Eye(self, self.cfg)
        P["planets"] = Planets(self, self.cfg)
        P["shelf"] = Shelf(self, self.cfg)
        P["dock"] = Dock(self, self.cfg, P["eye"])
        P["events"] = Events(self, self.cfg)
        P["media"] = MediaPod(self, self.cfg)
        P["clock"] = Clock(self, self.cfg)
        P["vitals"] = Vitals(self, self.cfg)
        P["corners"] = Corners(self, self.cfg, P["eye"].show)

        def act(name, cb, ptype=None):
            a = Gio.SimpleAction.new(name, GLib.VariantType.new(ptype) if ptype else None)
            a.connect("activate", lambda _a, p: cb(p.unpack() if p is not None else None))
            self.add_action(a)

        act("eye", lambda _p: P["eye"].toggle())
        act("earthling", lambda _p: self.cfg.toggle_earthling())
        act("jar", lambda _p: (hypr.jar_active(), P["shelf"].refresh()))
        act("planet", lambda n: P["planets"].travel(n), "i")
        act("starmap", lambda _p: P["planets"].show_map())
        act("transmission", lambda _p: P["events"].transmission())
        act("trail", lambda _p: P["events"].cursor_trail())
        act("set", lambda kv: self._set(*kv), "(ss)")
        act("quit", lambda _p: self.quit())

        from . import firstboot
        firstboot.maybe_show(self, self.cfg)
        print(f"[hive] The Hive {__version__} online (earthling={self.cfg.earthling}, motion={motion.level()}, "
              f"hyprland={hypr.available()})", file=sys.stderr)

    def _set(self, key, value):
        v = {"on": True, "true": True, "1": True, "off": False, "false": False, "0": False}.get(value.lower(), value)
        if key == "earthling":
            self.cfg.set_earthling(bool(v))
        else:
            self.cfg.set(key, v)

    def do_activate(self):
        pass


def main():
    return Hive().run(sys.argv[:1])
