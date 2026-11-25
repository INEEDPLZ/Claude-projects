"""Builds the Hive stylesheet from the ZorpOS design tokens (the only color source)."""
import json
from pathlib import Path

from gi.repository import Gdk, Gtk

TOKENS_PATHS = [Path("/usr/share/zorpos/tokens.json"),
                Path(__file__).resolve().parents[2] / "themes" / "tokens.json"]


def load_tokens():
    for p in TOKENS_PATHS:
        if p.exists():
            return json.loads(p.read_text())
    raise FileNotFoundError("ZorpOS tokens.json not found")


TOKENS = load_tokens()
C = TOKENS["color"]
FONT = TOKENS["font"]


def rgb(name):
    h = C[name].lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgba(name, a):
    return (*rgb(name), a)


CSS = """
* {{ font-family: "{body}", sans-serif; }}
window.hive-layer, window.hive-layer > * {{ background: transparent; }}
/* ZorpOS app windows (Organism, first boot): dark glass, never theme-dependent */
window.zorp-app {{ background: radial-gradient(circle at 30% 20%, {teal_deep} 0%, {abyss} 55%, {void} 100%); color: {text}; }}
window.zorp-app headerbar {{ background: linear-gradient(to bottom, {chrome_hi}, {chrome} 50%, {chrome_lo}); color: {void}; }}
window.zorp-app .pod-body label {{ color: {text}; }}
window.zorp-app .pod-body label.dim {{ color: {text_dim}; }}
window.zorp-app entry, window.zorp-app passwordentry, window.zorp-app dropdown > button, window.zorp-app spinbutton {{
  background: alpha({void}, 0.85); color: {text}; border: 1px solid alpha({aqua}, 0.6); border-radius: 12px; }}
window.zorp-app entry:focus-within, window.zorp-app passwordentry:focus-within {{ border-color: {acid}; box-shadow: 0 0 10px alpha({acid}, 0.6); }}
window.zorp-app passwordentry text, window.zorp-app entry text {{ color: {aqua_glow}; }}
window.zorp-app popover contents {{ background: {abyss}; color: {text}; }}
.lcd {{ font-family: "{lcd}", monospace; font-weight: 800; color: {aqua_glow};
        text-shadow: 0 0 6px alpha({aqua}, 0.9); }}
/* glyph rules come after .lcd so alien script wins until translated */
.glyph {{ font-family: "{glyph}", "{body}"; letter-spacing: 2px; font-size: 15px; }}
.glyph.translated {{ font-family: "{body}", sans-serif; letter-spacing: 0; }}
.glyph.lcd.translated {{ font-family: "{lcd}", monospace; }}
.clock-time {{ font-size: 34px; color: {aqua_glow}; text-shadow: 0 0 10px {aqua}; }}
.clock-time.translated {{ font-size: 30px; }}
.dim {{ color: {text_dim}; }}
label {{ color: {text}; }}

/* app pods orbiting the Eye */
button.pod {{ border-radius: 9999px; padding: 10px; min-width: 52px; min-height: 52px;
  background: radial-gradient(circle at 35% 28%, {chrome_hi} 0%, {chrome} 30%, {chrome_lo} 70%, {chrome_dark} 100%);
  border: 1px solid alpha({aqua_glow}, 0.6);
  box-shadow: 0 0 14px alpha({aqua}, 0.45), inset 0 -4px 8px alpha({void}, 0.5); }}
button.pod:hover {{ box-shadow: 0 0 22px alpha({acid}, 0.9), inset 0 -4px 8px alpha({void}, 0.5);
  border-color: {acid}; }}
button.pod.fav {{ background: radial-gradient(circle at 35% 28%, {chrome_hi} 0%, {zorp_lilac} 35%, {zorp_violet} 75%, {zorp_plum} 100%); }}
.pod-label {{ font-size: 16px; color: {aqua_glow}; text-shadow: 0 0 4px {void}; }}
.eye-query {{ font-size: 26px; }}
button.chrome-pill {{ border-radius: 9999px; padding: 6px 16px;
  background: linear-gradient(to bottom, {chrome_hi}, {chrome} 45%, {chrome_lo} 55%, {chrome} 100%);
  color: {void}; border: 1px solid {chrome_dark}; font-weight: bold; }}
button.chrome-pill label {{ color: {void}; }}
button.chrome-pill:hover {{ box-shadow: 0 0 12px {acid}; }}
button.flat-orb {{ background: none; border: none; box-shadow: none; padding: 0; }}

/* Earthling dock: deliberately ordinary */
.dock {{ background: alpha({abyss}, 0.82); border-radius: 18px; padding: 6px 10px;
  border: 1px solid alpha({aqua}, 0.35); }}
.dock button {{ border-radius: 12px; padding: 6px; background: transparent; }}
.dock button:hover {{ background: alpha({aqua}, 0.18); }}
.dock button.running {{ border-bottom: 3px solid {aqua}; }}
.dock button.minimized {{ opacity: 0.55; }}
.dock label {{ font-size: 13px; }}
.dock .clock {{ font-weight: bold; padding: 0 8px; }}
scale.seek trough {{ min-height: 6px; border-radius: 3px; background: alpha({void}, 0.6); }}
scale.seek highlight {{ border-radius: 3px; background: linear-gradient(to right, {aqua}, {acid}); }}
scale.seek slider {{ min-width: 14px; min-height: 14px; margin: -4px 0; padding: 0; border-radius: 4px;
  background: linear-gradient(to bottom, {chrome_hi}, {glass_blue}); border: 1px solid {glass_deep}; }}
tooltip {{ background: alpha({void}, 0.92); border: 1px solid {aqua}; border-radius: 10px; }}
"""


def install_css():
    fmt = {k.replace("-", "_"): v for k, v in C.items()}
    fmt.update(body=FONT["body"], lcd=FONT["lcd"], glyph=FONT["glyph"])
    prov = Gtk.CssProvider()
    css = CSS.format(**fmt)
    if hasattr(prov, "load_from_string"):
        prov.load_from_string(css)
    else:
        prov.load_from_data(css, -1)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
