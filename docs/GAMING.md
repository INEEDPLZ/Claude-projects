# Gaming on ZorpOS

ZorpOS aims for SteamOS-style compatibility on ordinary PCs. Everything below is installed
by the `zorpos-gaming` metapackage.

## What's included

| Area | Packages / config |
|---|---|
| Steam | `steam` (multilib) + `zorp-steam` wrapper ("Docking with Steam…" splash, first-run tuning) |
| Windows games | Proton (Steam downloads it), **Proton-GE** via `protonup-qt`, `wine-staging`, `winetricks`, `protontricks` |
| Performance | `gamescope`, `gamemode` (+lib32), `kernel.split_lock_mitigate=0`, `vm.max_map_count=1048576` (Arch default) |
| Overlay | `mangohud` (+lib32), themed as the **Vitals** dot-matrix teal readout (`/etc/MangoHud.conf`) |
| Post-processing | `vkbasalt` (optional; CAS sharpening when `ENABLE_VKBASALT=1`, Home key toggles) |
| Graphics | `mesa`, `lib32-mesa`, `vulkan-radeon`, `vulkan-intel` + lib32 variants on the ISO; NVIDIA added per machine by `zorp-gpu-setup` |
| Controllers | Steam's udev rules, `game-devices-udev` (third-party pads), `xpadneo-dkms` (Xbox over Bluetooth), `uinput` auto-loaded, Bluetooth enabled |

## The Gamer Hive session

A gamescope session that boots straight into Steam Big Picture.

- **At the greeter:** pick **Gamer Hive**. (The greeter arrives in Phase 5; the session file is already registered.)
- **From a TTY:** log in as your normal user (on the live ISO, tty1 auto-logs in as `specimen`) and run `zorp-gamer-hive`.
- **Leaving:** Steam → Power → **Switch to Desktop** ends the session cleanly. Ctrl+Alt+F3 always gives a text console.
- **Tuning:** create `~/.config/zorpos/gamer-hive.env` with, e.g., `ZORP_GS_EXTRA="-W 2560 -H 1440 -r 144 --adaptive-sync"`.
- **Safety:** if gamescope or Steam dies 3 times within 2 minutes, the session stops and tells you to run
  `zorp-gaming-doctor`, instead of looping forever.

Steam runs with `-gamepadui -steamos3`. The SteamOS helper commands Steam expects
(`steamos-session-select`, `steamos-update`, `steamos-select-branch`) are small ZorpOS stubs:
OS updates come from pacman, and "Switch to Desktop" leaves the Hive.

## Using the tools

| Want | Do |
|---|---|
| Overlay in a game | Steam launch options: `mangohud %command%` (Right Shift+F12 toggles) |
| gamemode in a game | `gamemoderun %command%` |
| Both | `gamemoderun mangohud %command%` |
| Proton-GE | open **ProtonUp-Qt** → Add version → GE-Proton → then pick it in the game's Compatibility tab |
| Sharpening | `ENABLE_VKBASALT=1 %command%` |
| NVIDIA on the live ISO | `sudo zorp-gpu-setup` (needs internet); `--dry-run` shows what it would install |
| Check everything | `zorp-gaming-doctor` |

## GPU auto-detection (`zorp-gpu-setup`)

- **AMD / Intel:** Mesa RADV / ANV + 32-bit variants.
- **NVIDIA Turing or newer (RTX 20 / GTX 16+):** `nvidia-open-dkms`, `nvidia-utils`, `lib32-nvidia-utils`. DKMS builds
  for both linux-zen and linux-lts.
- **Older NVIDIA:** nvidia-open can't drive these, so it keeps nouveau and says so.
- **Hybrid laptops:** adds `nvidia-prime` + `switcheroo-control`; use `prime-run %command%`.

The installer (Phase 6) runs `zorp-gpu-setup --root /mnt`. NVIDIA isn't preinstalled on the ISO
because the open module only supports Turing+ and would get in the way on other cards.

## Shader pre-caching, esync, fsync

- **Shader pre-caching** is on by default in Steam. On first launch, `zorp-steam` writes `steam_dev.cfg` so
  background shader compiles use half your cores, and disables HTTP/2 for downloads (often faster on Linux).
- **esync** needs a high open-file limit. Arch/systemd already set the hard limit to 524288.
- **fsync** needs `futex_waitv`, which is built into linux-zen and linux-lts.

`zorp-gaming-doctor` checks all of these.

## Known limits

- **The Steam login screen can't be themed.** Valve's client UI has no supported skinning, and
  patching it breaks on every Steam update. ZorpOS themes what it owns instead: the full-screen
  "Docking with Steam…" splash shown while Steam starts.
- **In a VM without 3D acceleration**, gamescope and Steam's gamepad UI can't start (no Vulkan device).
  The automated QEMU test therefore checks the installed stack with `zorp-gaming-doctor`, not a live
  Steam session. Test the Gamer Hive on real hardware, or in a VM with GPU passthrough or virgl/venus.
