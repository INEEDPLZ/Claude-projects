"""Hive settings + Earthling Mode state.

Settings live in ~/.config/zorpos/hive.json, over defaults from /etc/zorpos/hive-defaults.json. Earthling Mode is a plain flag file
(~/.config/zorpos/earthling) so it can be set from a TTY with `touch`, and is forced on by the
kernel parameter zorp.earthling=1.
"""
import json
import os
from pathlib import Path

from gi.repository import GObject

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "zorpos"
SETTINGS = CONFIG_DIR / "hive.json"
EARTHLING_FLAG = CONFIG_DIR / "earthling"
FIRSTBOOT_DONE = CONFIG_DIR / "firstboot-done"

DEFAULTS = {
    "transmissions": True,      # very occasional alien notifications
    "cursor_trail": True,       # occasional short glowing cursor trail
    "corners": True,            # fling the mouse into a corner to summon the Eye
    "glyph_delay_ms": 650,      # hover time before a glyph label translates
    "favorites": [
        "firefox.desktop", "zorp-steam.desktop", "os.zorp.Xenoscribe.desktop",
        "os.zorp.SpecimenArchive.desktop", "io.bassi.Amberol.desktop", "foot.desktop",
        "os.zorp.PersonalizeOrganism.desktop", "net.davidotek.pupgui2.desktop",
    ],
    "planets": 5,
    "motion": "full",           # full | lite | still: redraw rate of the always-on widgets (see motion.py)
}

# Editions (e.g. the MacBook edition) ship different defaults here; the user's hive.json still wins.
SYSTEM_DEFAULTS = Path("/etc/zorpos/hive-defaults.json")
try:
    DEFAULTS.update(json.loads(SYSTEM_DEFAULTS.read_text()))
except (OSError, ValueError):
    pass


def cmdline_earthling():
    try:
        return "zorp.earthling=1" in Path("/proc/cmdline").read_text().split()
    except OSError:
        return False


class Config(GObject.Object):
    __gsignals__ = {
        "earthling-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.data = dict(DEFAULTS)
        try:
            self.data.update(json.loads(SETTINGS.read_text()))
        except (OSError, ValueError):
            pass
        self.forced = cmdline_earthling()

    # --- earthling ---
    @property
    def earthling(self):
        return self.forced or EARTHLING_FLAG.exists()

    def set_earthling(self, on):
        if self.forced and not on:
            return  # kernel parameter wins for this boot
        if on:
            EARTHLING_FLAG.touch()
        else:
            EARTHLING_FLAG.unlink(missing_ok=True)
        self.emit("earthling-changed", self.earthling)

    def toggle_earthling(self):
        self.set_earthling(not self.earthling)

    # --- generic ---
    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        tmp = SETTINGS.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2))
        tmp.replace(SETTINGS)
        self.emit("changed", key)
