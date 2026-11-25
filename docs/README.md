# ZorpOS

An Arch Linux–based distro that crash-landed from another planet. Its builders copied
Earth's mid-2000s "glossy future" design and got it slightly wrong. Arch underneath, alien on top.

> **Status: all 6 phases done.** Live ISO + installer ([INSTALL.md](INSTALL.md)), gaming stack
> ([GAMING.md](GAMING.md)), **The Hive** alien desktop with Earthling Mode ([HIVE.md](HIVE.md)), the
> **Xenoscribe** word processor ([XENOSCRIBE.md](XENOSCRIBE.md)), and the full theming pass: landing-UFO
> boot splash, alien-eye login, GTK, cursors and Firefox ([THEMING.md](THEMING.md)).
> Why things are the way they are: [DESIGN-DECISIONS.md](DESIGN-DECISIONS.md).

## Quick start

```sh
sudo make iso          # build out/zorpos-*.iso (packages first, then the ISO)
make run-vm            # try it in a QEMU window
# write it to a USB stick (double-check the device!):
sudo dd if=out/zorpos-*.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

Boot it, try the Hive, then open **Install ZorpOS** in the Mothership Eye.

## Repo layout

| Path | What |
|---|---|
| `archiso/` | archiso profile (based on the official `releng` profile) |
| `packages/` | PKGBUILDs built into the local `[zorpos]` repo (see [AUR.md](AUR.md)) |
| `shell/` | The Hive desktop shell + Hyprland config ([HIVE.md](HIVE.md)) |
| `apps/` | Xenoscribe word processor (Rust + GTK4) |
| `themes/tokens.json` | **the only place theme colors are defined** |
| `themes/branding/` | original SVG art (mascot, …) |
| `scripts/` | build, asset and VM-test tooling |
| `docs/` | you are here |

## Building

```sh
sudo make iso          # -> out/zorpos-YYYY.MM.DD-x86_64.iso
sudo make iso-fast     # zstd squashfs, much faster, slightly bigger: for dev iteration
```

`scripts/build-iso.sh` picks a builder automatically:

| Builder | When | Notes |
|---|---|---|
| `native` | Arch host with `archiso` installed | fastest |
| `podman` / `docker` | any Linux with a container engine | runs `archlinux:latest` with `--privileged` |
| `chroot` | any Linux, as root | downloads the official Arch bootstrap tarball into `build/archroot` |

Force one with `ZORP_BUILDER=chroot`. Use a different mirror with `ZORP_MIRROR=https://…`.
If you are behind a TLS-inspecting proxy, set `ZORP_EXTRA_CA=/path/ca.crt`.

Native build dependencies: `archiso librsvg python base-devel git pacman-contrib`.
`make iso` first builds `packages/` into `build/repo/` (`[zorpos]`), then the ISO. To test: `qemu-desktop edk2-ovmf`.

## Testing

```sh
make test-vm           # headless BIOS + UEFI(OVMF) smoke tests; screenshots in out/test/{bios,uefi}/
make test-install      # end-to-end: install onto a virtual disk (UEFI), boot it, check the greeter
make run-vm            # interactive QEMU window, UEFI
ISO=path/to.iso make test-vm-uefi
```

The smoke test passes when the live system reaches `mothership login:` on the serial console **and**
`zorp-gaming-doctor` reports no failures (it logs in as root over serial; `PROBE=0` skips this).
It uses KVM if `/dev/kvm` is writable and falls back to TCG otherwise (slow: allow ~10 min).

## Boot menu

| Entry | Kernel | Purpose |
|---|---|---|
| ZorpOS ~ board the mothership | linux-zen | default |
| ZorpOS ~ LTS kernel, safe graphics | linux-lts + `nomodeset` | known-good fallback; forces Earthling Mode |
| ZorpOS ~ with speech | linux-zen + speakup | screen reader; forces Earthling Mode |
| Memtest86+ | n/a | RAM test |

## Live session

The live user **`specimen`** (no password, passwordless sudo, live ISO only) is logged straight into **the Hive**
by greetd. Log out to see the alien-eye greeter. The first boot offers Hive Mode or Earthling Mode. Root can log in on tty2–6 with an empty
password. From a TTY, `zorp-gamer-hive` boots into Steam Big Picture.

Included apps: Xenoscribe (word processor), Firefox, Amberol (music), Celluloid/mpv (video), Personalize Organism (settings), Specimen
Archive (files), foot (terminal), Steam + ProtonUp-Qt, and games: Chromium B.S.U., SuperTux, Pingus,
Teeworlds, Mines, 2048, Quadrapassel, Chess and Aisleriot solitaire.

## Keybinds

| Keys | Does |
|---|---|
| **Super** (tap) / Super+Space | Mothership Eye: app rings; type to search |
| **Super+Shift+E** | **Earthling Mode** on/off (English labels, normal dock, normal workspaces) |
| Super+1..5 / Super+Shift+1..5 | travel to planet (workspace) / send window there |
| Super+Tab | star map |
| Super+J | put the window in a specimen jar (minimize) |
| Super+D | plain app launcher, always normal |
| Super+Return / Super+E | terminal / Specimen Archive (files) |
| Super+Q / F / V | close / fullscreen / float |
| Super+Shift+Q | leave Hyprland |
| Right Shift+F12 | MangoHud vitals overlay in games |
| Ctrl+Alt+F2..F6 | text consoles, always |

More: [HIVE.md](HIVE.md). Xenoscribe shortcuts: [XENOSCRIBE.md](XENOSCRIBE.md).

## Escaping the weirdness (and recovery)

Weird must never mean bricked. These always work:

- **Ctrl+Alt+F2–F6**: plain text consoles.
- **`zorp-rescue`**: recovery guide (chroot from the live ISO, rebuild initramfs, reinstall the bootloader).
- **`zorp-escape-hatch`**: every way out of the alien UI.
- **Boot param `systemd.unit=multi-user.target`**: no graphics at all.
- **Boot param `zorp.earthling=1`**: forces Earthling Mode.
- **Boot param `zorp.tty=1`**: no graphical login at all (greetd doesn't start).
- **Super+Shift+E**: Earthling Mode toggle. **Super+D**: plain launcher. **Super+Shift+Q**: leave Hyprland.
- **At login**: pick "Hyprland" (no Hive shell) or "Text console" in the greeter's session list.
- **Installed boot menu**: "LTS kernel, text boot, Earthling Mode" and "rescue: text console only".
- **Turn off the strange events**: Personalize Organism → Strange Events (transmissions, cursor trail).
- **Underneath it's Arch Linux**: the Arch Wiki applies to everything.

## Theming rule

Every color lives in `themes/tokens.json`. `make tokens` turns it into
`themes/generated/tokens.{css,sh}` plus the TTY palette. Boot configs use `@NAME@`
placeholders that `scripts/prepare-profile.sh` fills in at build time, and the build fails
if any are left unresolved.

## Art & licensing

All art is original and drawn as SVG in this repo. It contains no third-party logos,
skins, characters or trademarks. The wallpaper is procedurally generated
(`scripts/gen-aurora.py`, deterministic seed). Repo art is CC-BY-SA-4.0 and code is GPL-3.0-or-later
unless a file says otherwise.
