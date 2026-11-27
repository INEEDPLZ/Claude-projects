#pragma once

/*
 * FlipTune wire protocol (see ../docs/PROTOCOL.md).
 *
 * Every message, in both directions, is one frame:
 *
 *   0xA5 | type | len_lo | len_hi | payload[len] | chk
 *
 * chk = XOR of type, len_lo, len_hi and every payload byte.
 * Frames can be split across BLE writes or packed together; the receiver
 * parses a byte stream.
 */

#include <stdint.h>

#define FT_SYNC        0xA5
#define FT_MAX_PAYLOAD 512

#define FT_ART_W     48
#define FT_ART_H     48
#define FT_ART_BYTES (FT_ART_W * FT_ART_H / 8) /* 288, row-major, MSB first, 1 = ink */

typedef enum {
    /* companion -> Flipper */
    FtMsgTrack = 0x01, /* "title\0artist\0album\0" (ASCII) */
    FtMsgState = 0x02, /* u8 playing, u32 elapsed_ms, u32 duration_ms, u8 volume(0-100, 255=unknown) */
    FtMsgArtChunk = 0x03, /* u16 offset, bytes... */
    FtMsgArtDone = 0x04, /* (empty) art buffer complete */
    FtMsgArtNone = 0x05, /* (empty) no artwork for this track */

    /* Flipper -> companion */
    FtMsgCommand = 0x10, /* u8 FtCmd */
} FtMsgType;

typedef enum {
    FtCmdPlayPause = 1,
    FtCmdNext = 2,
    FtCmdPrev = 3,
    FtCmdVolUp = 4,
    FtCmdVolDown = 5,
    FtCmdSeekFwd = 6, /* +10 s */
    FtCmdSeekBack = 7, /* -10 s */
    FtCmdSync = 8, /* resend track + state + art */
    FtCmdPoll = 9, /* send state; resend track/art only if it changed */
} FtCmd;
