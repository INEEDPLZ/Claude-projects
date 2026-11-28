# TAPE//DECK: cyberdeck cassette remote for Flipper Zero

A Bluetooth media remote for Apple Music with a cassette-deck look and a lot of
animation. **There is nothing to install on the phone.** You pair the Flipper in
iPhone Settings → Bluetooth like any other remote.

![screens](docs/screens.png)

Animated preview, rendered from the real drawing code: [`docs/preview.gif`](docs/preview.gif)

## What it does

| Button | Sends | Animation |
|---|---|---|
| OK | Play / pause | The reels spin up or coast to a stop, and the PLAY/PAUSE box flashes |
| ▶ | Next track | The tape fast-forwards in a burst, ejects upward, and a new tape drops in and lands with a jolt and a vibration |
| ◀ | Restart / previous | Past 3 s: the reels rewind and the counter spins back to 00:00. Within 3 s: it rewinds, ejects and loads the previous tape. This matches how iOS handles the button |
| Hold ◀ / ▶ | Rewind / fast-forward while held | The reels whip around, with speed streaks across the cassette and doubled chevrons in the bar |
| ▲ / ▼ | Volume | Chevrons rise or fall in the panel |
| Back | Exit | |
| Hold Back | Forget paired devices | |

Animations that run all the time:

- The reels turn at a constant tape speed, so the fuller reel turns slower, as on a
  real deck. The tape slowly winds from the left reel to the right one.
- The L/R VU meters bounce, with peak hold.
- The transport bar's rails scroll with the tape. Chevrons stream in the direction
  the tape is moving, and the playhead block pulses inside HUD brackets.
- The top HUD shows blinking data lights and a sweeping link-strength meter.
- A ticker scrolls along the bottom.
- The screen glitches now and then.
- Before a phone connects, a terminal screen types out pairing instructions under
  a CRT scanline.
- When the phone connects, a LINK ESTABLISHED flash plays and the first tape drops in.

**What it can't show.** iOS only shares song info with Bluetooth accessories through
functions that Flipper apps aren't allowed to call, on either official or Momentum
firmware. So the deck can't show the song title or the real song time. The tape
counter and the PLAY/PAUSE state follow your button presses on the Flipper. If you
pause from the phone, the Flipper won't know.

## Install

**Momentum firmware** (API 87.1, mntm-012 and current dev): copy `tapedeck_momentum.fap`
to `SD Card/apps/Bluetooth/` with qFlipper or the Flipper mobile app. It shows up as
**Apps → Bluetooth → TAPE//DECK**.

**To pair:**

1. Open TAPE//DECK on the Flipper.
2. On the iPhone, go to Settings → Bluetooth and tap **Tape <your Flipper's name>**.
3. Start something in Apple Music and use the Flipper's buttons.

The Flipper keeps this pairing separate from its normal Bluetooth pairing.

## Build

For Momentum, build inside a checkout of the
[Momentum firmware](https://github.com/Next-Flip/Momentum-Firmware):

```sh
git clone --recursive https://github.com/Next-Flip/Momentum-Firmware
ln -s "$PWD/flipper_app" Momentum-Firmware/applications_user/fliptune
cd Momentum-Firmware && ./fbt fap_fliptune
# → build/f7-firmware-C/.extapps/fliptune.fap
```

For official firmware, run `cd flipper_app && ufbt`. The app uses only the standard
`ble_profile` HID library, so it builds the same way.

## Preview without hardware

```sh
cd tools/preview
python3 extract_fonts.py ~/.ufbt/current/firmware.elf > fonts.h   # the Flipper's real fonts
gcc -O2 -Istubs -o deck_preview preview.c -lm
python3 render.py ./deck_preview out/    # PNG screens and an animated GIF
```

`render.py` replays a scripted session through the real `fliptune.c`: connect,
skip, volume, hold fast-forward, restart, previous and pause.
