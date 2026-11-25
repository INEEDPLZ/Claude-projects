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
itself, and `game-devices-udev` (our upstream build) covers third-party pads.

## 7. No AUR at all
The ISO can't pull from the AUR, and AUR PKGBUILDs can change under us. Every non-official package
gets its own PKGBUILD in `packages/`, built from upstream at a pinned version into the `[zorpos]` repo.
`protontricks`, `wine-staging` and `nvidia-open-dkms` turned out to be official already.
Details: [AUR.md](AUR.md).

## 8. UEFI boot menu shows no image
systemd-boot (used for UEFI on the ISO) is text-only. The mascot appears on the BIOS menu
splash now, and on both paths through Plymouth once Phase 5 lands. That's also where a
Windows-style boot logo really lives: after the bootloader, not in it.

## 9. "Themed first-run Steam login"
Steam's login and UI are Valve's client and can't be skinned in a supported way. Patching it breaks
on every Steam update. **Alternative:** ZorpOS themes what it owns: a full-screen "Docking with
Steam…" splash (original mascot + Doto dot-matrix type) that covers Steam's startup and hands off
when the client is up. Earthling Mode turns it into plain "Starting Steam…".

## 10. Gamer Hive instead of `gamescope-session-steam`
The common AUR session pulls in a whole -git stack. Ours is about 60 lines of bash plus three SteamOS stubs,
with a crash-loop guard so a broken GPU driver drops you to a TTY with advice instead of a black
screen loop.

## 11. Live ISO user
Steam refuses to run as root, so tty1 now auto-logs in as `specimen` (passwordless sudo, live only).
Root still has tty2–6.

## 12. The Hive: Python + GTK4 + gtk4-layer-shell (not AGS/Astal)
**Decided (owner, Phase 3).** AGS/Astal aren't in Arch's official repos, and building them from
source would add a large, fast-moving dependency. Python + GTK4 + `gtk4-layer-shell` are all official
packages. They're the same stack as the Docking splash, so ZorpOS's UI code shares one toolkit.
Hyprland stays the compositor (with jelly animations, see #2). The shell talks to it over
Hyprland's IPC socket.

## 13. Hyprland 0.57 uses a Lua config
Hyprland switched from hyprlang to Lua (`hl.config`, `hl.bind`, `hl.dsp.*`). ZorpOS's config
(`shell/hypr/zorpos.lua`) is written for it and checked with `Hyprland --verify-config`. Jelly is done
with Hyprland's native **spring** curves (underdamped: they overshoot and settle), so it needs no plugin.

## 14. Glyph labels swap fonts, not text
Zorpglyph maps every Latin letter and digit to an invented alien glyph. A label's text is always real
English; "translation" only switches the font. Screen readers, copy-paste and search keep working,
and Earthling Mode is just a CSS class.

## 15. Specimen Archive is Nautilus + an icon theme, not a fork
Forking a file manager means owning a file manager. Nautilus wearing the original "Zorp" icon theme
(cocoon folders) gets the look while upstream keeps doing the hard parts (gvfs, trash, search).

## 16. Minimize = special workspace
Hyprland has no minimize. Jars are its hidden `special:jar` workspace. A `window.minimize` hook routes
apps' own minimize buttons there, and the shelf shows what's inside.

## 17. Session start before the greeter
Phase 5 brings the greetd eye greeter. Until then, a tty1 login starts Hyprland from
`/etc/profile.d`, and a crash or exit drops back to a working shell, never a black screen.
