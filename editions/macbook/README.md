# ZorpOS: MacBook Edition

A build of ZorpOS tuned for **Intel MacBook Pros from 2013–2015**, the Retina models with Intel Iris or Iris Pro
graphics: MacBookPro11,1–11,5 and 12,1. The Hive, the jelly animations, the eye greeter and all the apps are the
same as the regular ISO. What changes is driver support for Mac hardware and lower graphics cost, so it stays
smooth on a ten-year-old integrated GPU pushing a 2560×1600 panel.

```sh
sudo make iso-macbook          # -> out/zorpos-macbook-YYYY.MM.DD-x86_64.iso
```

Everything for this edition lives in this folder. The regular `make iso` is not affected by it.

## What's different

### Speed

| Change | Why |
|---|---|
| **Motion: Lite** by default | The jars, clock, Vitals heartbeat and media pod redraw at ~15 fps instead of every frame. Each redraw also made Hyprland re-blur the screen behind it. Same look, a fraction of the GPU work. Change it in *Personalize Organism → Mode → Motion* (Full / Lite / Still). |
| Glass blur in **xray** mode, 1 pass | Glass blurs the wallpaper once and reuses it, instead of re-blurring the windows underneath every frame. |
| Rotating border gradient off | It repainted every window border on every frame. Borders keep their aqua→acid→lilac gradient; it just doesn't spin. |
| Unfocused windows fully opaque, smaller shadows | Less blending per frame. |
| Color-management shaders off | The panel is sRGB anyway. |
| **Exact 2× scale** on Retina panels | Hyprland's automatic scale can choose a fractional value, which is slower and blurrier. |
| GTK's **GL renderer** on Ivy Bridge, Haswell and Broadwell graphics | These chips have no complete Vulkan driver, so GL is the fast path. |
| Hardware video decode (`libva-intel-driver`) | Firefox and Celluloid decode H.264 on the GPU instead of the dual-core CPU. |
| Boot entry **"load into RAM first"** | A live session reads everything off the USB stick, which is the main reason it feels sluggish. This entry copies the system to RAM at boot (a minute or two; needs 8 GB RAM), then everything is quick. Installing to the SSD makes the issue go away for good. |

### Mac hardware

| Hardware | What ZorpOS does |
|---|---|
| Wi-Fi (Broadcom BCM4360/43602) | `broadcom-wl-dkms`, Broadcom's driver from the official Arch repos. Without it there is no Wi-Fi at all. |
| Fans | `mbpfan` reads the Apple SMC and runs a sane fan curve. It starts only on Apple hardware. |
| Heat | `thermald` (Intel's thermal daemon), plus `power-profiles-daemon` for battery/balanced/performance. |
| Trackpad | Tap to click, two-finger click = right click, natural scrolling, palm rejection while typing, three-finger swipe between planets. |
| Keyboard | Cmd is Super, so **Cmd+Q closes a window**, Cmd+Space opens the Eye, and so on. The top-row keys do brightness, keyboard backlight, media and volume like in macOS (hold **fn** for F1–F12). Mission Control (F3) opens the star map and Launchpad (F4) opens the Eye. |
| Suspend | Turns off the USB controller's wake-up, which otherwise makes 2013–2014 MacBooks wake right after closing the lid. |

## Booting it on the Mac

1. Write the ISO to a USB stick in **DD mode** (Rufus: choose "Write in DD Image mode"; or balenaEtcher).
2. Plug it in, power on and **hold the Option (⌥) key** until the boot picker appears.
3. Pick the orange **"EFI Boot"** drive.
4. Choose **"load into RAM first"** if the Mac has 8 GB or more, otherwise the first entry.

Wi-Fi shows up in the network menu once the live system is up. Install from **Install ZorpOS** as usual; the
installed system keeps all of the above.

## Known limits

- **FaceTime HD camera:** not supported. Its Linux driver needs Apple's camera firmware pulled out of a macOS
  driver download, which ZorpOS can't ship. The community `facetimehd` driver works if you set it up yourself.
- **15″ models with an NVIDIA GT 750M** (MacBookPro11,3): they run on the open `nouveau` driver; NVIDIA's own
  driver no longer supports that chip. The Intel GPU is usually the better choice for the desktop anyway.
- **Gaming:** Steam and the Gamer Hive are all here, but a Haswell iGPU is suited to older and indie games.
  Use *Motion: Still* while playing for a few extra frames.
- These tweaks are tested by building the ISO and booting it in a VM. The Mac-specific parts (Wi-Fi, fans,
  trackpad, suspend) have not been verified on real MacBook hardware.

## Files

```
editions/macbook/
├── edition.sh        ISO name, boot menu titles, the load-into-RAM entry
├── packages.add      extra packages (Wi-Fi, fans, thermals, video decode)
└── airootfs/         files laid over the live system (and kept on install)
    ├── etc/zorpos/hive-defaults.json          Motion: Lite
    ├── etc/zorpos/session.env                 GTK GL renderer on older Intel graphics
    ├── etc/modprobe.d/zorpos-macbook.conf     Apple keyboard top row
    ├── etc/systemd/system/…                   fans, thermald, suspend wake fix
    └── usr/share/zorpos/hypr/edition.lua      Hyprland: scale, blur, trackpad, Mac keys
```

`mbpfan` isn't in the official repos, so it's built from upstream by `packages/mbpfan/PKGBUILD` (no AUR).

### Making another edition

Copy this folder to `editions/<name>/`, change what you need, and run `sudo make iso EDITION=<name>`.
All three parts are optional.
