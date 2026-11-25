"""GlyphLabel: text shown in the Zorpglyph alien script that 'translates' to English on hover.

It's the same string either way. Only the font changes (Zorpglyph <-> Comfortaa), so screen readers
always get real English. In Earthling Mode it's plain English from the start.
"""
from gi.repository import GLib, Gtk

_config = None


def bind_config(cfg):
    global _config
    _config = cfg


class GlyphLabel(Gtk.Label):
    def __init__(self, text="", hover_target=None, **kw):
        super().__init__(label=text, **kw)
        self.add_css_class("glyph")
        self._timer = 0
        self._hovering = False
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", self._enter)
        motion.connect("leave", self._leave)
        (hover_target or self).add_controller(motion)
        self.update_mode()
        if _config:
            _config.connect("earthling-changed", lambda *_: self.update_mode())

    def update_mode(self):
        if _config and _config.earthling:
            self.add_css_class("translated")
        elif not self._hovering:
            self.remove_css_class("translated")

    def _enter(self, *_):
        self._hovering = True
        delay = _config.get("glyph_delay_ms") if _config else 650
        self._cancel()
        self._timer = GLib.timeout_add(delay, self._translate)

    def _translate(self):
        self._timer = 0
        self.add_css_class("translated")
        return False

    def _leave(self, *_):
        self._hovering = False
        self._cancel()
        self.update_mode()

    def _cancel(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
