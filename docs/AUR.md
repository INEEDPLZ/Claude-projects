# AUR & non-official packages

Official Arch repos come first. Anything not in core/extra/multilib gets **our own PKGBUILD**
in `packages/`, built straight from upstream at a pinned version, tag or commit. It goes into
the local `[zorpos]` repo that ships inside the ISO.
**ZorpOS uses no AUR packages.** The build never touches aur.archlinux.org.

| Package | Phase | Why it isn't official | Source |
|---|---|---|---|
| `protonup-qt-bin` | 2 | ProtonUp-Qt (Proton-GE manager) is AUR-only | upstream AppImage v2.16.0, unpacked so it runs without FUSE |
| `game-devices-udev` | 2 | third-party controller udev rules are AUR-only | codeberg.org/fabiscafe/game-devices-udev, tag 1.1 |
| `xpadneo-dkms` | 2 | Xbox Bluetooth controller driver is AUR-only | github.com/atar-axis/xpadneo, tag v0.10.5 |
| `vkbasalt` | 2 | Vulkan post-processing layer is AUR-only (optional; dormant unless `ENABLE_VKBASALT=1`) | github.com/DadSchoorse/vkBasalt, tag v0.3.2.10 |
| `zorpos-fonts` | 2 | Doto + Comfortaa (SIL OFL) | google/fonts at a pinned commit |
| `zorpos-gamer-hive` | 2 | ours: replaces AUR `gamescope-session-steam` | this repo |
| `zorpos-gaming` | 2 | ours: metapackage + config | this repo |
| `calamares` | 6 | installer framework; not in official repos | github.com/calamares/calamares, tag v3.3.14 (Qt6) |
| `mbpfan` | MacBook | Intel MacBook fan control is AUR-only | github.com/linux-on-mac/mbpfan, tag v2.5.0 (our unit: starts only where an Apple SMC exists) |
| `zorpos-installer` | 6 | ours: Abduction Sequence config + branding + `zorp-install-target` / `zorp-install-cli` | this repo |
| `zorpos-hive`, `xenoscribe`, `zorpos-themes` | 3–5 | ours | this repo |

These were on the original AUR list but are **official now**, so we use the repo versions:
`protontricks` (extra), `wine-staging` (extra), `gamescope` (extra), `mangohud` / `lib32-mangohud`,
`nvidia-open-dkms`.

## Building them

```sh
sudo scripts/build-packages.sh          # all, skipping versions already in build/repo
sudo scripts/build-packages.sh -f       # force rebuild
sudo scripts/build-packages.sh vkbasalt # just one
```

`make iso` runs this automatically. The repo is unsigned for now
(`SigLevel = Optional TrustAll`, only for the build-time `[zorpos]` entry). A signing key and a
hosted mirror for installed systems come with the installer in Phase 6.
