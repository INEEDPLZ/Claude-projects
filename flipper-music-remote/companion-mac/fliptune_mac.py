#!/usr/bin/env python3
"""
FlipTune Mac companion: bridges the Music app (Apple Music) to the FlipTune
Flipper Zero app over Bluetooth LE.

    pip3 install bleak pillow
    python3 fliptune_mac.py            # connects to the first Flipper found
    python3 fliptune_mac.py --name Abcd  # or a specific Flipper by name

macOS will ask for Bluetooth permission (for your terminal) and, the first
time a command runs, for permission to control "Music". The Flipper shows a
pairing PIN on first connect; enter it in the macOS prompt.
"""

import argparse
import asyncio
import os
import subprocess
import tempfile
import unicodedata

from bleak import BleakClient, BleakScanner
from PIL import Image, ImageOps

SERIAL_SERVICE = "8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000"
SERIAL_RX = "19ed82ae-ed21-4c9d-4145-228e62fe0000"  # we write  -> Flipper
SERIAL_TX = "19ed82ae-ed21-4c9d-4145-228e61fe0000"  # indicate <- Flipper

SYNC = 0xA5
MSG_TRACK, MSG_STATE, MSG_ART_CHUNK, MSG_ART_DONE, MSG_ART_NONE = 1, 2, 3, 4, 5
MSG_COMMAND = 0x10
(CMD_PLAYPAUSE, CMD_NEXT, CMD_PREV, CMD_VOLUP, CMD_VOLDOWN,
 CMD_SEEKFWD, CMD_SEEKBACK, CMD_SYNC, CMD_POLL) = range(1, 10)

ART = 48
ART_CHUNK = 128


# --------------------------------------------------------------------------
# Protocol
# --------------------------------------------------------------------------

def frame(msg_type: int, payload: bytes = b"") -> bytes:
    n = len(payload)
    head = bytes([msg_type, n & 0xFF, n >> 8])
    chk = 0
    for b in head + payload:
        chk ^= b
    return bytes([SYNC]) + head + payload + bytes([chk])


def ascii_only(s: str, limit: int = 63) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return s.encode("ascii", "ignore").decode()[:limit]


class Parser:
    """Stream parser for Flipper -> companion frames."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data: bytes):
        self.buf += data
        out = []
        while True:
            i = self.buf.find(bytes([SYNC]))
            if i < 0:
                self.buf.clear()
                break
            del self.buf[:i]
            if len(self.buf) < 4:
                break
            t, n = self.buf[1], self.buf[2] | (self.buf[3] << 8)
            if n > 512:
                del self.buf[:1]
                continue
            if len(self.buf) < 5 + n:
                break
            body = bytes(self.buf[1:4 + n])
            chk = 0
            for b in body:
                chk ^= b
            if chk == self.buf[4 + n]:
                out.append((t, bytes(self.buf[4:4 + n])))
                del self.buf[:5 + n]
            else:
                del self.buf[:1]
        return out


# --------------------------------------------------------------------------
# Artwork -> 48x48 1-bit (Atkinson dither, MSB first, 1 = ink)
# --------------------------------------------------------------------------

def dither_art(path: str) -> bytes:
    img = Image.open(path).convert("L")
    img = ImageOps.fit(img, (ART, ART), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=2)
    px = [float(v) for v in img.getdata()]
    for y in range(ART):
        for x in range(ART):
            i = y * ART + x
            old = px[i]
            new = 255.0 if old >= 128 else 0.0
            px[i] = new
            err = (old - new) / 8.0
            for dx, dy in ((1, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (0, 2)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < ART and yy < ART:
                    px[yy * ART + xx] += err
    out = bytearray(ART * ART // 8)
    for i, v in enumerate(px):
        if v < 128:
            out[i >> 3] |= 0x80 >> (i & 7)
    return bytes(out)


# --------------------------------------------------------------------------
# Music.app via AppleScript
# --------------------------------------------------------------------------

def osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip()


SEP = "␞"

STATE_SCRIPT = f'''
if application "Music" is not running then return "stopped"
tell application "Music"
    set st to player state as string
    if st is "stopped" then return "stopped"
    set t to current track
    return st & "{SEP}" & (name of t) & "{SEP}" & (artist of t) & "{SEP}" & (album of t) ¬
        & "{SEP}" & (duration of t) & "{SEP}" & (player position) & "{SEP}" & (sound volume) ¬
        & "{SEP}" & (persistent ID of t)
end tell
'''


def read_state():
    out = osa(STATE_SCRIPT)
    if not out or out == "stopped":
        return None
    parts = out.split(SEP)
    if len(parts) < 8:
        return None
    st, name, artist, album, dur, pos, vol, pid = parts[:8]

    def num(v):
        try:
            return float(v.replace(",", "."))
        except ValueError:
            return 0.0

    return {
        "playing": st == "playing",
        "title": name, "artist": artist, "album": album,
        "duration": num(dur), "position": num(pos),
        "volume": int(num(vol)), "id": pid,
    }


def export_artwork() -> str | None:
    path = os.path.join(tempfile.gettempdir(), "fliptune_art.bin")
    script = f'''
    tell application "Music"
        try
            set d to raw data of artwork 1 of current track
        on error
            try
                set d to data of artwork 1 of current track
            on error
                return "none"
            end try
        end try
    end tell
    set f to open for access POSIX file "{path}" with write permission
    set eof f to 0
    write d to f
    close access f
    return "ok"
    '''
    return path if osa(script) == "ok" else None


COMMANDS = {
    CMD_PLAYPAUSE: 'tell application "Music" to playpause',
    CMD_NEXT: 'tell application "Music" to next track',
    CMD_PREV: 'tell application "Music" to back track',
    CMD_VOLUP: 'tell application "Music" to set sound volume to (sound volume + 6)',
    CMD_VOLDOWN: 'tell application "Music" to set sound volume to (sound volume - 6)',
    CMD_SEEKFWD: 'tell application "Music" to set player position to (player position + 10)',
    CMD_SEEKBACK: 'tell application "Music" to set player position to (player position - 10)',
}


# --------------------------------------------------------------------------
# Bridge
# --------------------------------------------------------------------------

class Bridge:
    def __init__(self, client: BleakClient, rx_char, tx_char):
        self.client = client
        self.rx_char = rx_char  # we write here
        self.tx_char = tx_char  # Flipper notifies/indicates here
        self.parser = Parser()
        self.last = None
        self.sent_id = None
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self.lock = asyncio.Lock()

    async def write(self, data: bytes):
        mtu = max(20, min(self.client.mtu_size - 3, 180))
        async with self.lock:
            for i in range(0, len(data), mtu):
                await self.client.write_gatt_char(self.rx_char, data[i:i + mtu], response=True)

    def on_notify(self, _char, data: bytearray):
        for t, payload in self.parser.feed(bytes(data)):
            if t == MSG_COMMAND and payload:
                self.queue.put_nowait(payload[0])

    async def push_state(self, s):
        if s is None:
            payload = bytes([0]) + (0).to_bytes(4, "little") * 2 + bytes([255])
        else:
            payload = (bytes([1 if s["playing"] else 0])
                       + int(s["position"] * 1000).to_bytes(4, "little")
                       + int(s["duration"] * 1000).to_bytes(4, "little")
                       + bytes([max(0, min(100, s["volume"]))]))
        await self.write(frame(MSG_STATE, payload))

    async def push_track(self, s):
        text = "\0".join(ascii_only(s[k]) for k in ("title", "artist", "album")) + "\0"
        await self.write(frame(MSG_TRACK, text.encode()))
        path = await asyncio.to_thread(export_artwork)
        art = None
        if path:
            try:
                art = await asyncio.to_thread(dither_art, path)
            except Exception as e:  # unreadable image
                print("artwork error:", e)
        if art:
            for off in range(0, len(art), ART_CHUNK):
                await self.write(frame(MSG_ART_CHUNK, off.to_bytes(2, "little") + art[off:off + ART_CHUNK]))
            await self.write(frame(MSG_ART_DONE))
        else:
            await self.write(frame(MSG_ART_NONE))
        self.sent_id = s["id"]

    async def sync(self, force: bool):
        s = await asyncio.to_thread(read_state)
        if s and (force or s["id"] != self.sent_id):
            print(f"♪ {s['title']} — {s['artist']} ({s['album']})")
            await self.push_track(s)
        await self.push_state(s)
        self.last = s

    async def run(self):
        await self.client.start_notify(self.tx_char, self.on_notify)
        await self.sync(force=True)
        while self.client.is_connected:
            try:
                cmd = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # watch Music.app for changes on our own, too
                s = await asyncio.to_thread(read_state)
                changed = (s is None) != (self.last is None) or (
                    s and self.last and (s["id"] != self.last["id"]
                                         or s["playing"] != self.last["playing"]
                                         or abs(s["position"] - self.last["position"]) > 3
                                         or s["volume"] != self.last["volume"]))
                if changed:
                    await self.sync(force=False)
                elif s:
                    self.last = s
                continue
            if cmd in COMMANDS:
                await asyncio.to_thread(osa, COMMANDS[cmd])
                await asyncio.sleep(0.15)
                await self.sync(force=False)
            elif cmd == CMD_SYNC:
                await self.sync(force=True)
            elif cmd == CMD_POLL:
                await self.sync(force=False)


async def find_flipper(name: str | None):
    print("Scanning for Flipper…")
    while True:
        devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
        for dev, adv in devices.values():
            label = dev.name or adv.local_name or ""
            uuids = [u.lower() for u in adv.service_uuids]
            is_flipper = SERIAL_SERVICE in uuids or label.lower().startswith("flipper")
            if is_flipper and (not name or name.lower() in label.lower()):
                print(f"Found {label} ({dev.address})")
                return dev
        print("…not found yet (is FlipTune open on the Flipper?)")


def pick_chars(client: BleakClient):
    rx = client.services.get_characteristic(SERIAL_RX)
    tx = client.services.get_characteristic(SERIAL_TX)
    if not (rx and tx):
        raise RuntimeError("Flipper serial characteristics not found")
    return rx, tx


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", help="Flipper name (as shown in Settings > System)")
    args = ap.parse_args()
    while True:
        dev = await find_flipper(args.name)
        try:
            async with BleakClient(dev) as client:
                print("Connected.")
                rx, tx = pick_chars(client)
                await Bridge(client, rx, tx).run()
        except Exception as e:
            print("connection lost:", e)
        await asyncio.sleep(2)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
