# Theming

Every color comes from `themes/tokens.json`. Every piece of art is original and generated from code
at package build time (`scripts/gen-*.py`). Packages: `zorpos-themes` (GTK, cursors, Firefox,
Plymouth) and `zorpos-hive` (greeter, session, Hive shell).

| Piece | What it looks like | Source |
|---|---|---|
| Boot splash (Plymouth) | Zorp's scout saucer descends over the aurora as the system boots; on final approach a pulsing tractor beam hits a glowing landing pad; dot-matrix "LANDING". Disk-encryption password prompts are themed too. | `themes/plymouth/zorp/`, `scripts/gen-plymouth-art.py` |
| Login (greetd + cage) | A pulsing chrome alien eye. Each typed character is a glowing pellet fed into the pupil, which dilates. Right password: a contented blink. Wrong: the eye shakes and spits the pellets out. Pick user and session (The Hive, Gamer Hive, Hyprland, text console). | `shell/zorphive/greeter.py` |
| GTK | GTK4 + libadwaita: tokens palette, chrome header bars, acid accents (`~/.config/gtk-4.0/gtk.css`). GTK3: theme "Zorp" on top of Adwaita-dark. | `scripts/gen-gtk-theme.py` |
| Icons | "Zorp": folders are silk cocoons (inherits Adwaita) | `scripts/gen-icons.py` |
| Cursors | "ZorpCursors": chrome arrow with antenna orb, glowing pointer orb, aqua I-beam, spinning wait ring, chrome resize arrows (24/32/48 px) | `scripts/gen-cursors.py` |
| Firefox | Glossy chrome pill tabs, teal glass toolbar, acid-glow URL bar; the new tab and home page are an alien page with a Zorpglyph clock (hover for Earth time) | `themes/firefox/` |
| Terminal, notifications, launcher | foot, mako, fuzzel configs from tokens | `packages/zorpos-hive/` |

## How the Firefox skin is installed

- `policies.json` (in `/usr/lib/firefox/distribution/`) enables `toolkit.legacyUserProfileCustomizations.stylesheets`,
  sets the home page and turns off telemetry and first-run nags.
- `autoconfig.js` + `zorpos.cfg` (a privileged startup script) copies `userChrome.css` into whatever profile
  Firefox uses and points new tabs at the ZorpOS page. That works whether Firefox keeps its profiles in
  `~/.mozilla` or `~/.config/mozilla`.
- **Your own `userChrome.css` is never overwritten.** ZorpOS only manages the file while its
  `.zorpos-managed` marker sits next to it. Delete the marker to take over the file.
- Don't want it at all? Remove `zorpos-themes`, or delete `/usr/lib/firefox/defaults/pref/autoconfig.js`.

## Escape hatches

| Want | Do |
|---|---|
| Text boot (no splash) | Boot menu "LTS, safe graphics", or remove `quiet splash` from the entry (`e` / Tab) |
| No graphical login | Boot param `zorp.tty=1` (greetd won't start), or `systemd.unit=multi-user.target` |
| Plain GTK | Delete `~/.config/gtk-4.0/gtk.css`; choose Adwaita in `~/.config/gtk-3.0/settings.ini` |
| Different splash | `sudo plymouth-set-default-theme -R spinner` |
