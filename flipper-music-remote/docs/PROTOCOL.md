# FlipTune protocol

## Transport

FlipTune runs over the Flipper's standard BLE **serial service**:

| | UUID | Direction |
|---|---|---|
| Service | `8fe5b3d5-2e7f-4a98-2a48-7acc60fe0000` | |
| RX characteristic | `19ed82ae-ed21-4c9d-4145-228e62fe0000` | companion **writes**, Flipper receives |
| TX characteristic | `19ed82ae-ed21-4c9d-4145-228e61fe0000` | Flipper **indicates**, companion receives |

Both characteristics need an authenticated (PIN-paired) link. Subscribing to TX
starts the pairing. Use writes *with response* and keep each write to 180 bytes or
less; this gives natural flow control.

The Flipper's advertisement does not include the 128-bit service UUID. Scan for
devices whose name starts with `Flipper`.

## Framing

Messages are framed the same way in both directions:

```
0xA5 | type | len_lo | len_hi | payload[len] | chk
chk = type ^ len_lo ^ len_hi ^ payload[0] ^ … ^ payload[len-1]
```

The maximum payload is 512 bytes. Frames can be split across BLE writes or packed
several to a write, so treat the link as a byte stream. Multi-byte integers are
little-endian.

## Companion → Flipper

| Type | Name | Payload |
|---|---|---|
| `0x01` | Track | `title\0artist\0album\0` in printable ASCII; longer than 63 bytes is truncated |
| `0x02` | State | `u8 playing`, `u32 elapsed_ms`, `u32 duration_ms`, `u8 volume` (0–100, or 255 if unknown) |
| `0x03` | ArtChunk | `u16 offset`, then cover bytes |
| `0x04` | ArtDone | empty: the cover buffer is complete, so show it |
| `0x05` | ArtNone | empty: this track has no cover, so show the generated pattern |

**Cover format**

- 48×48 pixels, 1 bit per pixel: 288 bytes in total.
- Row-major order, most significant bit first. A `1` bit is a black pixel.
- Send it as ArtChunks of up to 128 bytes, then send ArtDone.
- When a Track message changes the album or artist, the Flipper clears the cover and
  shows a loading shimmer. If no cover arrives within 1.5 s, it falls back to the
  generated pattern.

**Elapsed time**: the Flipper advances elapsed time on its own while `playing` is set,
so the companion only needs to send State when something changes.

## Flipper → companion

| Type | Name | Payload |
|---|---|---|
| `0x10` | Command | `u8 cmd` |

| cmd | Meaning |
|---|---|
| 1 | Play / pause |
| 2 | Next track |
| 3 | Previous track (restart the song if past 3 s) |
| 4 | Volume up |
| 5 | Volume down |
| 6 | Seek +10 s |
| 7 | Seek −10 s |
| 8 | Sync: resend Track, State and cover |
| 9 | Poll: send State, and Track + cover only if the song changed |

The Flipper sends Sync 0.6 s after connecting, then Poll every 3 s.
