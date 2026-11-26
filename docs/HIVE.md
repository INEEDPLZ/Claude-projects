# The Hive

The Hive is ZorpOS's desktop: Hyprland (jelly animations) plus a shell written in Python + GTK4 +
gtk4-layer-shell (`shell/zorphive/`, packaged as `zorpos-hive`). There's no taskbar and no start menu.
Labels are written in **Zorpglyph**, an invented alien script, and translate to English when you hover them.

Everything weird has a normal twin: **Earthling Mode** (Super+Shift+E).

## Keybinds

| Keys | Hive Mode | Earthling Mode |
|---|---|---|
| **Super** (tap) / **Super+Space** | summon the Mothership Eye | open the plain app grid |
| **Super+Shift+E** | toggle Earthling Mode | toggle Earthling Mode |
| **Super+1..5** | travel to planet N (star map animation) | switch workspace (instant) |
| **Super+Shift+1..5** | move window to planet N | move window to workspace N |
| **Super+Tab** | open the star map | n/a |
| **Super+J** | put the window in a specimen jar (minimize) | minimize (shows in the dock) |
| **Super+D** | plain app launcher (fuzzel); always normal | same |
| **Super+Return** | terminal (foot) | same |
| **Super+E** | Specimen Archive (files) | same |
| **Super+Q** | close window (dematerialize) | close window |
| **Super+F / Super+V** | fullscreen / float | same |
| **Super+drag** | move (left) / resize (right) | same |
| **Super+Shift+Q** | leave Hyprland, back to the text console | same |
| **Ctrl+Alt+F3** | text console, always | same |
| **Print** | screenshot a region to the clipboard | same |

## Pieces

| Piece | What it does | Where |
|---|---|---|
| **Mothership Eye** | Chrome eye at screen center; the pupil follows your pointer. Favorites orbit the inner ring, everything else orbits the outer rings. Scroll spins the rings. **Type to search**, Enter launches. Fling the pointer into any corner to summon it. | `eye.py`, `corners.py` |
| **Glyph labels** | Same English text rendered in Zorpglyph; hovering ~0.65 s switches the font back to English. Screen readers always get English. | `glyphs.py`, `scripts/gen-glyphs.py` |
| **Specimen jars** | Minimized windows go to Hyprland's `special:jar` workspace and appear as glass jars with bubbling fluid on a shelf at the right edge. Click a jar to release the specimen onto the current planet. Apps' own minimize buttons do the same. | `jars.py`, `zorpos.lua` |
| **Planets** | Workspaces are planets on an orbit. Switching zooms out to the star map, a beacon travels the orbit, then the camera dives into the target planet. Planets with windows grow a little moon. | `planets.py` |
| **Dematerialize** | Closing a window sucks it inward with an overshooting curve. | `zorpos.lua` (`windowsOut`) |
| **Jelly** | Windows move and open on underdamped springs (they wobble and settle). | `zorpos.lua` |
| **Orbital Media Pod** | Chrome pill MPRIS player: big glossy play/pause orb, dot-matrix scrolling title, seek bar, prev/next. Follows whichever player is active (Amberol, Celluloid, Firefox...). | `widgets.py` |
| **Alien clock** | Chrome disc with alien numerals and an orbiting seconds dot; hover for Earth time. | `widgets.py` |
| **Vitals** | Heartbeat monitor: beat rate and spike height follow CPU load; CPU / GPU / temperature readouts. | `widgets.py` |
| **Personalize Organism** | Settings; every panel is a differently shaped organic pod. | `organism.py` |
| **Specimen Archive** | Nautilus with the Zorp icon theme: every folder is a silk cocoon. | `scripts/gen-icons.py` |
| **Transmissions** | About once every two hours, a harmless message from the mothership. | `events.py` |
| **Cursor trail** | About once an hour, the pointer leaves a 3-second glowing trail. | `events.py` |

### Reading Zorpglyph numerals

0 is a ring. For 1 through 5, count the dots beside the stem. For 6 through 9, a crossbar appears and
the extra dots sit on the left. The clock and Xenoscribe's word count use these numerals.

## Earthling Mode

Super+Shift+E, the button under the Eye, Personalize Organism, or the first-boot screen.
It gives you:

- English labels everywhere (the glyph font is switched off).
- A normal bottom dock: all-apps, favorites, running and minimized windows, workspace numbers, clock.
- Instant workspace switching (no star map), no hot corners, no transmissions or trails.
- The Eye becomes a plain alphabetical app grid with search.

It's stored as `~/.config/zorpos/earthling`, so `touch ~/.config/zorpos/earthling` from a TTY works.
The boot parameter `zorp.earthling=1` forces it for that boot (the "LTS, safe graphics" and
"speech" boot entries set it).

## Turning things off

| Want | Do |
|---|---|
| No transmissions | Personalize Organism → Strange Events, or `zorp-hivectl set transmissions off` |
| No cursor trail | `zorp-hivectl set cursor_trail off` |
| No hot corners | `zorp-hivectl set corners off` |
| Smoother on an old or weak GPU | Personalize Organism → Mode → Motion: **Lite** (~15 fps ambient widgets) or **Still**. The MacBook edition defaults to Lite. |
| Faster or slower glyph translation | Personalize Organism → Navigation, or edit `glyph_delay_ms` in `~/.config/zorpos/hive.json` |
| No Hive at login | `touch ~/.config/zorpos/no-autostart`, or the boot parameter `zorp.tty=1` |
| Hive crashed | Keybinds keep working: `zorp-hivectl` falls back to plain Hyprland actions and Super+D opens fuzzel. Restart it with `zorp-hive &`. |

## Session start

Login goes through **greetd** and the ZorpOS eye greeter ([THEMING.md](THEMING.md)). Pick "The Hive"
(`zorp-session`, which starts Hyprland), "Gamer Hive", plain Hyprland, or a text console. On the live ISO,
`specimen` logs straight into the Hive, and the greeter appears after logout. From a text console,
`zorp-session` starts the Hive by hand (its log: `~/.local/state/zorpos/session.log`). Boot with `zorp.tty=1` to skip graphical login entirely.

## Developing

```sh
# run the shell from the repo inside any wlroots/Hyprland session
PYTHONPATH=shell LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so python3 -m zorphive
shell/bin/zorp-hivectl eye
# validate the Hyprland config
Hyprland --verify-config -c shell/hypr/hyprland.lua
```

The shell also runs under headless sway (that's how its screenshots are tested). Without Hyprland,
IPC calls fail soft and jars and planets go quiet.

## Virtual machines

The Hive runs in VMs without 3D acceleration: Hyprland uses software GL, and this is tested in QEMU
for both BIOS and UEFI. On those machines (virtio-gpu, QXL, VMware SVGA, bochs, simpledrm) the login
script sets `GSK_RENDERER=cairo`, because GTK4's GPU renderers draw blank text on software GL.
Real GPUs keep GTK's default renderer. Set `GSK_RENDERER` yourself to override.
