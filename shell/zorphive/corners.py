"""Hot corners: fling the pointer into any screen corner to summon the Mothership Eye.
Tiny 2x2 px layer surfaces; disabled in Earthling Mode or when 'corners' is off."""
from gi.repository import Gtk

from . import layer


class Corners:
    def __init__(self, app, config, summon):
        self.cfg = config
        self.wins = []
        for v in ("top", "bottom"):
            for h in ("left", "right"):
                w = layer.make(app, "corner", layer="overlay", anchors=(v, h))
                w.set_default_size(2, 2)
                box = Gtk.Box()
                box.set_size_request(2, 2)
                w.set_child(box)
                m = Gtk.EventControllerMotion()
                m.connect("enter", lambda *_: summon())
                w.add_controller(m)
                self.wins.append(w)
        config.connect("earthling-changed", lambda *_: self.update())
        config.connect("changed", lambda *_: self.update())
        self.update()

    def update(self):
        on = bool(self.cfg.get("corners")) and not self.cfg.earthling and layer.supported()
        for w in self.wins:
            w.set_visible(on)
