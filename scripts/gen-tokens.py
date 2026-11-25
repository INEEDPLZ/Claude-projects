#!/usr/bin/env python3
"""Generate per-consumer token files from themes/tokens.json.

Outputs (all in themes/generated/, git-ignored):
  tokens.css   -> CSS custom properties (GTK4/AGS/Firefox/web)
  tokens.sh    -> shell vars ZORP_<NAME>=#rrggbb (build scripts, syslinux)
  tokens.lua   -> Lua table name -> rrggbb (Hyprland config)
  vt-params    -> kernel cmdline vt.default_{red,grn,blu}=... for the TTY palette
"""
import json
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
tokens = json.loads((root / "themes/tokens.json").read_text())
out = root / "themes/generated"
out.mkdir(parents=True, exist_ok=True)


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


colors = tokens["color"]

css = [":root {"]
css += [f"  --zorp-{k}: {v};" for k, v in colors.items()]
css += [f"  --zorp-alpha-{k}: {v};" for k, v in tokens["alpha"].items()]
css += [f'  --zorp-font-{k}: "{v}";' for k, v in tokens["font"].items()]
css.append("}")
(out / "tokens.css").write_text("\n".join(css) + "\n")

sh = ["# generated from themes/tokens.json - do not edit"]
for k, v in colors.items():
    sh.append(f"ZORP_{k.upper().replace('-', '_')}='{v}'")
for k, v in tokens["font"].items():
    sh.append(f"ZORP_FONT_{k.upper()}='{v}'")
(out / "tokens.sh").write_text("\n".join(sh) + "\n")

lua = ["-- generated from themes/tokens.json - do not edit", "return {"]
for k, v in colors.items():
    lua.append(f'  ["{k}"] = "{v.lstrip("#")}",')
lua.append("}")
(out / "tokens.lua").write_text("\n".join(lua) + "\n")

pal = [rgb(c) for c in tokens["tty"]["palette"]]
if len(pal) != 16:
    sys.exit("tty.palette must have exactly 16 entries")
vt = " ".join(
    f"vt.default_{name}=" + ",".join(f"0x{p[i]:02x}" for p in pal)
    for i, name in enumerate(("red", "grn", "blu"))
)
(out / "vt-params").write_text(vt + "\n")
print(f"tokens -> {out}")
