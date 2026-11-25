# Design decisions & pushback

These are the parts of the brief that were technically a bad idea, or couldn't ship as written,
with the alien-themed alternative chosen for each.

## 1. Boot icon: original mascot, not the reference image
The face in the first reference image is a character from an animated film, which is
copyrighted art. ZorpOS can't ship it or a lookalike. Instead, **Zorp**
(`themes/branding/zorp-mascot.svg`) is an original lavender bulb-headed alien with three
eyes, an acid-green antenna orb and a chrome collar pod. It is the boot icon in the BIOS
boot splash now, and becomes the Plymouth boot animation in Phase 5 (Zorp riding a landing UFO).

## 2. "Assets from Garuda Linux"
Garuda's wobbly windows aren't a Garuda asset. They come from **KWin's built-in Wobbly Windows
effect** (KDE). Garuda's actual artwork is their own branding, so we don't copy it.
Hyprland (the compositor the brief recommends) has no stock wobbly-window effect.

**Decided (owner, Phase 1): stay on Hyprland and use jelly animations.** Phase 3 ships
Hyprland's built-in animation engine with overshoot/spring bezier curves on window move,
resize, open, close and workspace switches ("gelatinous membrane" motion). It needs no plugins,
so a Hyprland update can't break login. KWin/Plasma is not being pursued.

## 3. Reference skins are inspiration only
No Microsoft logos, no media-player skins and no trademarked names. Every widget is drawn from
scratch as SVG/CSS with the tokens palette.

## 4. "Fling the mouse to any corner"
Hyprland has no native hot corners. The Hive draws 1px layer-shell trigger zones at each
corner. They are cheap, and Earthling Mode can disable them.

## 5. `vm.max_map_count` / esync limits
Arch already ships `vm.max_map_count = 1048576` and a 524288 hard `nofile` limit. Phase 2
only verifies these and does not override them, so we don't fight upstream.

## 6. `steam-devices`
That's a Debian/Fedora package name. On Arch the udev rules come with the `steam` package
itself, and `game-devices-udev` (AUR) covers third-party pads.

## 7. Calamares & other AUR-only packages
The ISO can't pull from the AUR at boot. Phase 2+ builds every AUR dependency into a local
signed pacman repo `[zorpos]` that ships on the ISO and on a hosted mirror.
Each package is listed with its justification in [AUR.md](AUR.md).

## 8. UEFI boot menu shows no image
systemd-boot (used for UEFI on the ISO) is text-only. The mascot appears on the BIOS menu
splash now, and on both paths through Plymouth once Phase 5 lands. That's also where a
Windows-style boot logo really lives: after the bootloader, not in it.
