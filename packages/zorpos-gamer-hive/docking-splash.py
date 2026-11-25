#!/usr/bin/env python3
"""'Docking with Steam...' splash. Fullscreen, closes itself when Steam's own UI is up.

Closes on: Steam client process running for a few seconds, any key / click, or a 45 s cap.
Earthling Mode (~/.config/zorpos/earthling or zorp.earthling=1) shows plain English.
"""
import os
import subprocess
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

MASCOT = "/usr/share/pixmaps/zorpos.svg"
CAP_S = 45
SETTLE_S = 4

CSS = """
window.dock { background: radial-gradient(circle at 50% 42%, #@TEAL@ 0%, #@TEAL_DEEP@ 45%, #@VOID@ 100%); }
.dock-title { font-family: "Doto", monospace; font-weight: 900; font-size: 44px;
              color: #@AQUA_GLOW@; letter-spacing: 6px;
              text-shadow: 0 0 18px #@AQUA@, 0 0 4px #@ACID@; }
.dock-sub   { font-family: "Comfortaa", sans-serif; font-size: 18px; color: #@TEXT_DIM@; }
.dock-ring  { border-radius: 9999px; padding: 26px;
              background: radial-gradient(circle, alpha(#@ACID@,0.18) 0%, alpha(#@AQUA@,0.05) 60%, transparent 70%); }
"""


def earthling():
    try:
        if "zorp.earthling=1" in open("/proc/cmdline").read().split():
            return True
    except OSError:
        pass
    cfg = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.exists(os.path.join(cfg, "zorpos", "earthling"))


def steam_up():
    r = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", "ubuntu12_32/steam|steamwebhelper"],
                       stdout=subprocess.DEVNULL)
    return r.returncode == 0


class Splash(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="os.zorp.DockingSplash")
        self.t0 = time.monotonic()
        self.seen = None
        self.dots = 0

    def do_activate(self):
        prov = Gtk.CssProvider()
        if hasattr(prov, "load_from_string"):
            prov.load_from_string(CSS)
        else:
            prov.load_from_data(CSS, -1)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        win = Gtk.ApplicationWindow(application=self, title="Docking with Steam")
        win.add_css_class("dock")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        ring = Gtk.Box(halign=Gtk.Align.CENTER)
        ring.add_css_class("dock-ring")
        if os.path.exists(MASCOT):
            pic = Gtk.Picture.new_for_filename(MASCOT)
            pic.set_size_request(260, 260)
            pic.set_can_shrink(True)
            ring.append(pic)
        box.append(ring)
        plain = earthling()
        self.base = "Starting Steam" if plain else "DOCKING WITH STEAM"
        self.title = Gtk.Label(label=self.base)
        self.title.add_css_class("dock-title")
        sub = Gtk.Label(label="Press any key to hide this screen" if plain
                        else "aligning tractor beam with the Valve mothership…")
        sub.add_css_class("dock-sub")
        box.append(self.title)
        box.append(sub)
        win.set_child(box)
        for ctl in (Gtk.EventControllerKey(), Gtk.GestureClick()):
            ctl.connect("key-pressed" if isinstance(ctl, Gtk.EventControllerKey) else "pressed",
                        lambda *a: self.quit())
            win.add_controller(ctl)
        win.fullscreen()
        win.present()
        GLib.timeout_add(450, self.tick)

    def tick(self):
        self.dots = (self.dots + 1) % 4
        self.title.set_label(self.base + "." * self.dots + " " * (3 - self.dots))
        now = time.monotonic()
        if steam_up():
            self.seen = self.seen or now
            if now - self.seen > SETTLE_S:
                self.quit()
        if now - self.t0 > CAP_S:
            self.quit()
        return True


if __name__ == "__main__":
    sys.exit(Splash().run([sys.argv[0]]))
