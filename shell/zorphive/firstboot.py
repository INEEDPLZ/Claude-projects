"""First-boot choice: Hive Mode (weird) or Earthling Mode (normal). Shown once, plain English."""
from gi.repository import Gtk

from .config import FIRSTBOOT_DONE


def maybe_show(app, config, on_done=None):
    if FIRSTBOOT_DONE.exists():
        return
    win = Gtk.Window(application=app, title="Welcome to ZorpOS", modal=True, resizable=False)
    win.set_default_size(560, -1)
    win.add_css_class("zorp-app")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_top=28, margin_bottom=24,
                  margin_start=28, margin_end=28)
    pic = Gtk.Picture.new_for_filename("/usr/share/pixmaps/zorpos.svg")
    pic.set_size_request(-1, 150)
    box.append(pic)
    title = Gtk.Label(label="You have landed.")
    title.add_css_class("lcd")
    title.add_css_class("eye-query")
    box.append(title)
    body = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, label=(
        "ZorpOS can run as the Hive: an alien desktop with no taskbar, labels in an alien "
        "script, and workspaces that are planets. Or it can run in Earthling Mode: English labels, a "
        "normal dock and normal workspaces.\n\nYou can switch any time with Super+Shift+E."))
    box.append(body)
    row = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER, margin_top=8)

    def choose(earthling):
        config.set_earthling(earthling)
        FIRSTBOOT_DONE.touch()
        win.destroy()
        if on_done:
            on_done()

    hive = Gtk.Button(label="Enter the Hive")
    hive.add_css_class("chrome-pill")
    hive.connect("clicked", lambda *_: choose(False))
    earth = Gtk.Button(label="Earthling Mode (normal desktop)")
    earth.add_css_class("chrome-pill")
    earth.connect("clicked", lambda *_: choose(True))
    row.append(hive)
    row.append(earth)
    box.append(row)
    win.set_child(box)
    win.present()
    earth.grab_focus()
