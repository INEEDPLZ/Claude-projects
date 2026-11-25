# ZorpOS

An Arch Linux–based distro that crash-landed from another planet. Its builders copied
Earth's mid-2000s "glossy future" design and got it slightly wrong. Arch underneath, alien on top.

> **Status: Phase 2 of 6.** This is a bootable, branded live ISO with a TTY base system and the full
> gaming stack ([GAMING.md](GAMING.md)). The Hive desktop, Xenoscribe, theming and installer arrive in later phases
> (see [ROADMAP.md](ROADMAP.md)).

## Repo layout

| Path | What |
|---|---|
| `archiso/` | archiso profile (based on the official `releng` profile) |
| `packages/` | PKGBUILDs built into the local `[zorpos]` repo (see [AUR.md](AUR.md)) |
| `shell/` | The Hive desktop shell (Phase 3) |
| `apps/` | Xenoscribe and other first-party apps (Phase 4) |
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

tty1 auto-logs in as **`specimen`** (no password, passwordless sudo, live ISO only). Steam refuses to run as
root. Root can log in on tty2–6 with an empty password. Run `zorp-gamer-hive` to boot into Steam Big Picture.

## Escaping the weirdness (and recovery)

Weird must never mean bricked. These always work:

- **Ctrl+Alt+F2–F6**: plain text consoles.
- **`zorp-rescue`**: recovery guide (chroot from the live ISO, rebuild initramfs, reinstall the bootloader).
- **`zorp-escape-hatch`**: every way out of the alien UI.
- **Boot param `systemd.unit=multi-user.target`**: no graphics at all.
- **Boot param `zorp.earthling=1`**: forces Earthling Mode (honored from Phase 3).
- **Super+Shift+E**: Earthling Mode toggle (Phase 3).

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
