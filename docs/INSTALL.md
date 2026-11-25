# Installing ZorpOS: Abduction Sequence

Boot the live ISO, then do one of these:

- **Graphical:** open **Install ZorpOS** (first favorite in the Mothership Eye; in Earthling Mode it's
  first in the dock). This is Calamares, themed "Abduction Sequence": welcome → location → keyboard →
  disks → you → summary → install → reboot.
- **Scriptable:** from a terminal (or Ctrl+Alt+F3):

  ```sh
  sudo zorp-install-cli --disk /dev/nvme0n1 --user you --password 'secret' --yes-wipe-disk \
       [--hostname mothership] [--timezone Europe/Berlin] [--locale de_DE.UTF-8] [--keymap de]
  ```

  This **wipes the whole disk**: GPT; on UEFI a 1 GiB ESP + ext4 root, on BIOS a BIOS-boot partition + ext4 root.

## What the install does

Both paths run the same back end, `zorp-install-target`, after copying the live system to disk:

| Step | Detail |
|---|---|
| Kernels | linux-zen (default) and linux-lts copied from the boot medium |
| Initramfs | mkinitcpio with the Plymouth hook (landing-UFO splash); zen: default image, LTS: default + fallback (used by the rescue entry) |
| Live cleanup | removes the `specimen` live user, live autologin, root-login SSH config, VM guest services, archiso units and hooks |
| Login | greetd with the alien-eye greeter (no autologin) |
| Packages | pacman keyring initialized; the mirror is set |
| GPU | `zorp-gpu-setup`: Mesa always; NVIDIA (Turing+) `nvidia-open-dkms` if online, otherwise run `sudo zorp-gpu-setup` later |
| Bootloader | UEFI: systemd-boot with "ZorpOS", "LTS kernel, text boot, Earthling Mode" and "rescue: text console only" entries. BIOS: GRUB with the same kernels. |

## Boot menu on an installed system (UEFI)

| Entry | Use |
|---|---|
| ZorpOS | normal boot: splash, eye greeter, the Hive |
| ZorpOS (LTS kernel, text boot, Earthling Mode) | if a zen-kernel update or the GPU misbehaves |
| ZorpOS (rescue: text console only) | LTS + fallback initramfs, no graphics, no greeter |

## Tested

`make test-install` installs the ISO onto a blank virtual disk under UEFI/OVMF with `zorp-install-cli`,
then boots the disk alone. It checks for a login prompt, greetd running, the live user and live greetd
config gone, and a clean `zorp-gaming-doctor`. The BIOS/GRUB path and the Calamares GUI are not covered
by the automated test.

## If something goes wrong

Boot the live ISO and run `zorp-rescue`: mount, `arch-chroot`, rebuild the initramfs
(`mkinitcpio -P`), reinstall the bootloader. The installed system is plain Arch underneath.
