#!/usr/bin/env python3
"""Generate ZorpOS GTK styling from the design tokens.

usage: gen-gtk-theme.py OUTDIR
  OUTDIR/gtk-4.0/gtk.css               -> per-user override (libadwaita + plain GTK4 apps)
  OUTDIR/themes/Zorp/gtk-3.0/gtk.css   -> GTK3 theme 'Zorp' (Adwaita-dark underneath)
  OUTDIR/themes/Zorp/index.theme
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
T = json.loads((ROOT / "themes/tokens.json").read_text())
C = T["color"]
out = pathlib.Path(sys.argv[1])

palette = {
    "accent_color": C["acid"],
    "accent_bg_color": C["teal"],
    "accent_fg_color": C["chrome-hi"],
    "destructive_bg_color": C["danger"],
    "success_bg_color": C["acid"],
    "warning_bg_color": C["warn"],
    "window_bg_color": C["abyss"],
    "window_fg_color": C["text"],
    "view_bg_color": C["void"],
    "view_fg_color": C["text"],
    "headerbar_bg_color": C["chrome"],
    "headerbar_fg_color": C["void"],
    "headerbar_backdrop_color": C["chrome-lo"],
    "sidebar_bg_color": C["teal-deep"],
    "sidebar_fg_color": C["text"],
    "card_bg_color": C["teal-deep"],
    "card_fg_color": C["text"],
    "popover_bg_color": C["abyss"],
    "popover_fg_color": C["text"],
    "dialog_bg_color": C["abyss"],
    "dialog_fg_color": C["text"],
}

legacy = "\n".join(f"@define-color {k} {v};" for k, v in palette.items())
variables = ":root {\n" + "\n".join(f"  --{k.replace('_', '-')}: {v};" for k, v in palette.items()) + "\n}"

chrome = f"linear-gradient(to bottom, {C['chrome-hi']}, {C['chrome']} 45%, {C['chrome-lo']} 55%, {C['chrome']} 100%)"
extra = f"""
/* ZorpOS: glossy chrome header bars, glassy windows, acid focus rings */
headerbar, .titlebar {{ background-image: {chrome}; color: {C['void']}; box-shadow: inset 0 -1px {C['chrome-dark']}; }}
headerbar button, .titlebar button {{ color: {C['void']}; }}
window, .background {{ background-image: radial-gradient(circle at 15% 0%, alpha({C['teal']}, 0.35), transparent 60%); }}
*:focus-visible {{ outline-color: {C['acid']}; }}
button.suggested-action {{ background-image: radial-gradient(circle at 40% 25%, {C['acid-glow']}, {C['acid']} 55%, {C['teal']}); color: {C['void']}; }}
selection, *:selected {{ background-color: alpha({C['aqua']}, 0.45); }}
scrollbar slider {{ background-color: alpha({C['aqua']}, 0.6); border-radius: 99px; }}
"""

g4 = out / "gtk-4.0"
g4.mkdir(parents=True, exist_ok=True)
(g4 / "gtk.css").write_text(f"/* generated from themes/tokens.json */\n{legacy}\n{variables}\n{extra}")

g3 = out / "themes" / "Zorp" / "gtk-3.0"
g3.mkdir(parents=True, exist_ok=True)
(g3 / "gtk.css").write_text(
    '@import url("resource:///org/gtk/libgtk/theme/Adwaita/gtk-contained-dark.css");\n'
    f"/* generated from themes/tokens.json */\n{legacy}\n"
    f"@define-color theme_bg_color {C['abyss']};\n@define-color theme_fg_color {C['text']};\n"
    f"@define-color theme_base_color {C['void']};\n@define-color theme_text_color {C['text']};\n"
    f"@define-color theme_selected_bg_color {C['teal']};\n@define-color theme_selected_fg_color {C['chrome-hi']};\n"
    f"{extra}")
(out / "themes" / "Zorp" / "index.theme").write_text(
    "[Desktop Entry]\nType=X-GNOME-Metatheme\nName=Zorp\nComment=ZorpOS glossy alien theme\n\n"
    "[X-GNOME-Metatheme]\nGtkTheme=Zorp\nIconTheme=Zorp\nCursorTheme=Zorp\n")
print(f"gtk theme -> {out}")
