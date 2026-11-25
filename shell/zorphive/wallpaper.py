"""Wallpaper on the background layer (no extra daemon needed)."""
import os
from pathlib import Path

from gi.repository import Gtk

from . import layer

SYSTEM_WALL = Path("/usr/share/backgrounds/zorpos/aurora.png")
USER_WALL = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "zorpos" / "aurora.png"


class Wallpaper:
    def __init__(self, app):
        self.win = layer.make(app, "wallpaper", layer="background",
                              anchors=("top", "bottom", "left", "right"), exclusive=-1)
        wall = USER_WALL if USER_WALL.exists() else SYSTEM_WALL   # "Regrow aurora" writes USER_WALL
        if wall.exists():
            pic = Gtk.Picture.new_for_filename(str(wall))
            pic.set_content_fit(Gtk.ContentFit.COVER)
            self.win.set_child(pic)
        self.win.set_visible(layer.supported())
