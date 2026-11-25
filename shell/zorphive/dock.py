"""Earthling dock: a deliberately ordinary bottom dock (favorites, running + minimized windows,
workspace numbers, all-apps, clock). Plain English, keyboard reachable. Only shown in Earthling Mode."""
import time

from gi.repository import GLib, Gtk

from . import apps as A
from . import hypr, layer


class Dock:
    def __init__(self, app, config, eye):
        self.cfg, self.eye = config, eye
        self.win = layer.make(app, "dock", layer="top", anchors=("bottom",),
                              margins={"bottom": 8}, exclusive="auto")
        self.box = Gtk.Box(spacing=4)
        self.box.add_css_class("dock")
        self.win.set_child(self.box)
        self.sig = None
        config.connect("earthling-changed", lambda *_: self.refresh(force=True))
        GLib.timeout_add(1500, self.refresh)
        self.refresh(force=True)

    def _btn(self, icon_widget, tooltip, cb, css=()):
        b = Gtk.Button(tooltip_text=tooltip)
        b.set_child(icon_widget)
        for c in css:
            b.add_css_class(c)
        b.connect("clicked", lambda *_: cb())
        return b

    def refresh(self, force=False):
        show = self.cfg.earthling
        self.win.set_visible(show)
        if not show:
            return True
        clients = hypr.clients() if hypr.available() else []
        ws = hypr.active_workspace_id() if hypr.available() else 1
        sig = (tuple((c.get("address"), (c.get("workspace") or {}).get("name")) for c in clients), ws,
               time.strftime("%H:%M"))
        if sig == self.sig and not force:
            return True
        self.sig = sig
        child = self.box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.box.remove(child)
            child = nxt

        self.box.append(self._btn(Gtk.Image(icon_name="view-app-grid-symbolic", pixel_size=24),
                                  "All applications", self.eye.show))
        favs, _ = A.split_favorites(self.cfg.get("favorites"))
        running_classes = {(c.get("class") or "").lower() for c in clients}
        for a in favs:
            stem = a.get_id().removesuffix(".desktop").lower()
            css = ("running",) if any(rc and rc in stem for rc in running_classes) else ()
            self.box.append(self._btn(A.icon_image(a, 28), a.get_display_name(), lambda a=a: A.launch(a), css))
        self.box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        for c in clients:
            name = (c.get("workspace") or {}).get("name", "")
            minimized = name == hypr.JAR
            img = Gtk.Image(icon_name=(c.get("class") or "application-x-executable").lower(), pixel_size=24)
            addr = c["address"]
            cb = (lambda a=addr: hypr.unjar(a)) if minimized else (lambda a=addr: hypr.focus_window(a))
            title = (c.get("title") or c.get("class") or "window") + (" (minimized)" if minimized else "")
            self.box.append(self._btn(img, title, cb, ("minimized",) if minimized else ()))
        self.box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        for n in range(1, int(self.cfg.get("planets")) + 1):
            lbl = Gtk.Label(label=str(n))
            b = self._btn(lbl, f"Workspace {n}", lambda n=n: hypr.focus_workspace(n), ("running",) if n == ws else ())
            self.box.append(b)
        clock = Gtk.Label(label=time.strftime("%H:%M"))
        clock.add_css_class("clock")
        self.box.append(clock)
        return True
