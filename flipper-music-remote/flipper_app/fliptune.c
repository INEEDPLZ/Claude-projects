/*
 * FlipTune Remote — Apple Music now-playing display and media remote.
 *
 * The Flipper runs its standard BLE serial profile. A companion (iPhone app
 * or Mac script) connects, streams track metadata, playback state and a
 * 48x48 1-bit dithered album cover, and executes the commands we send back.
 *
 * Controls:
 *   OK            play / pause
 *   Left / Right  previous / next track
 *   Hold L / R    seek -10 s / +10 s (repeats while held)
 *   Up / Down     volume
 *   Back          exit
 */

#include <furi.h>
#include <furi_hal.h>
#include <gui/gui.h>
#include <input/input.h>
#include <notification/notification_messages.h>
#include <bt/bt_service/bt.h>
#include <profiles/serial_profile.h>

#include <math.h>
#include <string.h>
#include <stdio.h>

#include "fliptune_protocol.h"

#define TAG "FlipTune"

#define STR_MAX         64
#define RX_STREAM_SIZE  2048
#define TICK_MS         33 /* ~30 fps */
#define POLL_MS         3000
#define EQ_BARS         9
#define ART_X           1
#define ART_Y           1
#define TEXT_X          54
#define TEXT_W          (128 - TEXT_X)
#define ART_PENDING_MS  1500 /* show the loading shimmer this long before falling back */
#define REVEAL_MS       650
#define SLIDE_MS        380
#define CMD_FX_MS       420
#define VOL_FX_MS       1200

/* ------------------------------------------------------------------------ */
/* Model                                                                    */
/* ------------------------------------------------------------------------ */

typedef struct {
    bool connected;
    bool has_track;
    char title[STR_MAX];
    char artist[STR_MAX];
    char album[STR_MAX];

    bool playing;
    uint32_t elapsed_ms; /* as reported at state_tick */
    uint32_t duration_ms;
    uint32_t state_tick;
    uint8_t volume; /* 0-100, 255 unknown */

    uint8_t art[FT_ART_BYTES];
    uint8_t art_rx[FT_ART_BYTES];
    bool has_art; /* real cover in `art`; otherwise generative fallback */
    bool art_pending; /* waiting for cover after a track change */
    uint32_t art_pending_tick;
    uint32_t reveal_tick;
    uint32_t ident_hash[2]; /* seeds for the fallback cover */

    uint32_t track_tick; /* for slide-in and marquee */
    uint32_t last_rx_tick;
    uint32_t connect_tick;

    FtCmd fx_cmd;
    uint32_t fx_tick;
    uint32_t vol_fx_tick;

    float eq[EQ_BARS];
    uint32_t frame;
} Model;

typedef enum {
    EvInput,
    EvTick,
} EvType;

typedef struct {
    EvType type;
    InputEvent input;
} Event;

typedef enum {
    PsSync,
    PsType,
    PsLen0,
    PsLen1,
    PsPayload,
    PsChk,
} ParseState;

typedef struct {
    ParseState st;
    uint8_t type;
    uint16_t len;
    uint16_t pos;
    uint8_t chk;
    uint8_t buf[FT_MAX_PAYLOAD];
} Parser;

typedef struct {
    Gui* gui;
    ViewPort* view_port;
    FuriMessageQueue* queue;
    FuriTimer* timer;
    FuriMutex* mutex;
    NotificationApp* notif;

    Bt* bt;
    FuriHalBleProfileBase* profile;
    FuriStreamBuffer* rx;
    volatile BtStatus bt_status;

    Parser parser;
    Model m;

    bool was_connected;
    bool sync_sent;
    uint32_t last_poll_tick;
    uint32_t rng;
} App;

static const NotificationSequence seq_tap = {
    &message_vibro_on,
    &message_delay_10,
    &message_vibro_off,
    NULL,
};

/* ------------------------------------------------------------------------ */
/* Small helpers                                                            */
/* ------------------------------------------------------------------------ */

static uint32_t now_ms(void) {
    return furi_get_tick() * 1000 / furi_kernel_get_tick_frequency();
}

static float clampf(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

static float ease_out_cubic(float t) {
    t = clampf(t, 0.f, 1.f);
    float u = 1.f - t;
    return 1.f - u * u * u;
}

static uint32_t fnv1a(const char* s, uint32_t h) {
    while(*s) {
        h ^= (uint8_t)*s++;
        h *= 16777619u;
    }
    return h;
}

static uint32_t xorshift(uint32_t* s) {
    uint32_t x = *s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *s = x;
    return x;
}

static uint32_t model_elapsed(const Model* m, uint32_t now) {
    uint32_t e = m->elapsed_ms;
    if(m->playing) e += now - m->state_tick;
    if(m->duration_ms && e > m->duration_ms) e = m->duration_ms;
    return e;
}

static void format_time(char* out, size_t n, uint32_t ms, bool negative) {
    uint32_t s = ms / 1000;
    uint32_t h = s / 3600;
    uint32_t mi = (s / 60) % 60;
    uint32_t se = s % 60;
    if(h)
        snprintf(
            out,
            n,
            "%s%lu:%02lu:%02lu",
            negative ? "-" : "",
            (unsigned long)h,
            (unsigned long)mi,
            (unsigned long)se);
    else
        snprintf(
            out, n, "%s%lu:%02lu", negative ? "-" : "", (unsigned long)mi, (unsigned long)se);
}

/* 8x8 Bayer matrix, used for the dissolve-in reveal of a new cover. */
static const uint8_t bayer8[8][8] = {
    {0, 32, 8, 40, 2, 34, 10, 42},
    {48, 16, 56, 24, 50, 18, 58, 26},
    {12, 44, 4, 36, 14, 46, 6, 38},
    {60, 28, 52, 20, 62, 30, 54, 22},
    {3, 35, 11, 43, 1, 33, 9, 41},
    {51, 19, 59, 27, 49, 17, 57, 25},
    {15, 47, 7, 39, 13, 45, 5, 37},
    {63, 31, 55, 23, 61, 29, 53, 21},
};

/* ------------------------------------------------------------------------ */
/* Glyphs (drawn with primitives so we need no icon assets)                 */
/* ------------------------------------------------------------------------ */

/* Solid right-pointing triangle, h rows tall, (h+1)/2 wide. */
static void glyph_tri_r(Canvas* c, int x, int y, int h) {
    for(int i = 0; i < (h + 1) / 2; i++)
        canvas_draw_line(c, x + i, y + i, x + i, y + h - 1 - i);
}

static void glyph_tri_l(Canvas* c, int x, int y, int h) {
    int w = (h + 1) / 2;
    for(int i = 0; i < w; i++)
        canvas_draw_line(c, x + w - 1 - i, y + i, x + w - 1 - i, y + h - 1 - i);
}

static void glyph_play(Canvas* c, int x, int y, int h) {
    glyph_tri_r(c, x, y, h);
}

static void glyph_pause(Canvas* c, int x, int y, int h) {
    int bw = h / 3 > 1 ? h / 3 : 2;
    canvas_draw_box(c, x, y, bw, h);
    canvas_draw_box(c, x + bw + bw / 2 + 1, y, bw, h);
}

static void glyph_next(Canvas* c, int x, int y, int h) {
    int w = (h + 1) / 2;
    glyph_tri_r(c, x, y, h);
    glyph_tri_r(c, x + w - 1, y, h);
    canvas_draw_box(c, x + 2 * w - 1, y, h > 8 ? 2 : 1, h);
}

static void glyph_prev(Canvas* c, int x, int y, int h) {
    int w = (h + 1) / 2;
    int bw = h > 8 ? 2 : 1;
    canvas_draw_box(c, x, y, bw, h);
    glyph_tri_l(c, x + bw, y, h);
    glyph_tri_l(c, x + bw + w - 1, y, h);
}

static void glyph_ff(Canvas* c, int x, int y, int h) {
    int w = (h + 1) / 2;
    glyph_tri_r(c, x, y, h);
    glyph_tri_r(c, x + w, y, h);
}

static void glyph_rew(Canvas* c, int x, int y, int h) {
    int w = (h + 1) / 2;
    glyph_tri_l(c, x, y, h);
    glyph_tri_l(c, x + w, y, h);
}

static void glyph_speaker(Canvas* c, int x, int y) {
    canvas_draw_box(c, x, y + 2, 2, 3);
    canvas_draw_line(c, x + 2, y + 2, x + 4, y);
    canvas_draw_line(c, x + 2, y + 4, x + 4, y + 6);
    canvas_draw_line(c, x + 4, y, x + 4, y + 6);
    canvas_draw_line(c, x + 3, y + 1, x + 3, y + 5);
}

/* Bluetooth rune, 5x9. */
static void glyph_bt(Canvas* c, int x, int y) {
    canvas_draw_line(c, x + 2, y, x + 2, y + 8);
    canvas_draw_line(c, x + 2, y, x + 4, y + 2);
    canvas_draw_line(c, x + 4, y + 2, x, y + 6);
    canvas_draw_line(c, x + 2, y + 8, x + 4, y + 6);
    canvas_draw_line(c, x + 4, y + 6, x, y + 2);
}

/* Bigger bluetooth rune for the waiting screen, scale 2. */
static void glyph_bt_big(Canvas* c, int cx, int cy) {
    int x = cx - 5, y = cy - 9;
    for(int o = 0; o < 2; o++) {
        canvas_draw_line(c, x + 4 + o, y, x + 4 + o, y + 18);
        canvas_draw_line(c, x + 4 + o, y, x + 9 + o, y + 5);
        canvas_draw_line(c, x + 9 + o, y + 5, x + o, y + 13);
        canvas_draw_line(c, x + 4 + o, y + 18, x + 9 + o, y + 13);
        canvas_draw_line(c, x + 9 + o, y + 13, x + o, y + 5);
    }
}

static void glyph_note(Canvas* c, int x, int y) {
    /* beamed eighth notes */
    canvas_draw_disc(c, x + 2, y + 10, 2);
    canvas_draw_disc(c, x + 10, y + 8, 2);
    canvas_draw_line(c, x + 4, y + 10, x + 4, y + 1);
    canvas_draw_line(c, x + 12, y + 8, x + 12, y - 1);
    canvas_draw_line(c, x + 4, y + 1, x + 12, y - 1);
    canvas_draw_line(c, x + 4, y + 2, x + 12, y);
}

/* ------------------------------------------------------------------------ */
/* Album art                                                                */
/* ------------------------------------------------------------------------ */

static inline bool art_bit(const uint8_t* art, int x, int y) {
    int i = y * FT_ART_W + x;
    return art[i >> 3] & (0x80 >> (i & 7));
}

/* Generative fallback: a mirrored 8x8 "pixel cover" seeded from album+artist,
 * with three tones (white / 50% checker / black), 6x6 px per cell. */
static bool ident_pixel(const Model* m, int x, int y) {
    int cx = x / 6, cy = y / 6;
    if(cx >= 4) cx = 7 - cx;
    int bit = (cy * 4 + cx) * 2; /* 0..62 */
    uint32_t word = m->ident_hash[bit >> 5];
    int tone = (word >> (bit & 31)) & 3;
    switch(tone) {
    case 0:
        return false;
    case 1:
        return ((x ^ y) & 1) == 0;
    default:
        return true;
    }
}

static void draw_art(Canvas* c, const Model* m, uint32_t now) {
    canvas_set_color(c, ColorWhite);
    canvas_draw_box(c, 0, 0, TEXT_X - 1, 51);
    canvas_set_color(c, ColorBlack);
    canvas_draw_frame(c, ART_X - 1, ART_Y - 1, FT_ART_W + 2, FT_ART_H + 2);

    bool pending = m->art_pending && (now - m->art_pending_tick) < ART_PENDING_MS;

    if(!pending) {
        /* Dissolve in through an ordered-dither threshold. */
        uint32_t t = now - m->reveal_tick;
        int level = t >= REVEAL_MS ? 64 : (int)(t * 64 / REVEAL_MS);
        for(int y = 0; y < FT_ART_H; y++) {
            for(int x = 0; x < FT_ART_W; x++) {
                if(bayer8[y & 7][x & 7] >= level) continue;
                bool on = m->has_art ? art_bit(m->art, x, y) : ident_pixel(m, x, y);
                if(on) canvas_draw_dot(c, ART_X + x, ART_Y + y);
            }
        }
        /* A bright scanline sweeps down once while it dissolves. */
        if(t < REVEAL_MS) {
            int sy = (int)(t * FT_ART_H / REVEAL_MS);
            canvas_set_color(c, ColorXOR);
            canvas_draw_line(c, ART_X, ART_Y + sy, ART_X + FT_ART_W - 1, ART_Y + sy);
            canvas_set_color(c, ColorBlack);
        }
    } else {
        /* Loading shimmer: diagonal stripes drifting across the frame. */
        int off = (m->frame * 2) % 12;
        for(int y = 0; y < FT_ART_H; y += 2) {
            for(int x = 0; x < FT_ART_W; x++) {
                if(((x + y + off) % 12) < 2) canvas_draw_dot(c, ART_X + x, ART_Y + y);
            }
        }
        canvas_set_color(c, ColorWhite);
        canvas_draw_rbox(c, ART_X + 8, ART_Y + 18, 32, 12, 2);
        canvas_set_color(c, ColorBlack);
        canvas_draw_rframe(c, ART_X + 8, ART_Y + 18, 32, 12, 2);
        canvas_set_font(c, FontSecondary);
        const char* dots[] = {"   ", ".  ", ".. ", "..."};
        char buf[8];
        snprintf(buf, sizeof(buf), "art%s", dots[(m->frame / 6) % 4]);
        canvas_draw_str(c, ART_X + 11, ART_Y + 27, buf);
    }

    /* Button feedback: ripple + glyph badge in the middle of the cover. */
    uint32_t ft = now - m->fx_tick;
    if(m->fx_tick && ft < CMD_FX_MS) {
        int cx = ART_X + FT_ART_W / 2, cy = ART_Y + FT_ART_H / 2;
        float p = ease_out_cubic((float)ft / CMD_FX_MS);
        int r = 8 + (int)(p * 16);
        canvas_set_color(c, ColorXOR);
        canvas_draw_circle(c, cx, cy, r);
        if(r > 12) canvas_draw_circle(c, cx, cy, r - 4);
        canvas_set_color(c, ColorWhite);
        canvas_draw_rbox(c, cx - 11, cy - 8, 22, 17, 3);
        canvas_set_color(c, ColorBlack);
        canvas_draw_rframe(c, cx - 11, cy - 8, 22, 17, 3);
        /* little "punch": glyph nudges in the direction of the action */
        int nudge = ft < 120 ? (int)(3 - ft / 40) : 0;
        switch(m->fx_cmd) {
        case FtCmdPlayPause:
            if(m->playing)
                glyph_play(c, cx - 3, cy - 5, 11);
            else
                glyph_pause(c, cx - 4, cy - 5, 11);
            break;
        case FtCmdNext:
            glyph_next(c, cx - 6 + nudge, cy - 4, 9);
            break;
        case FtCmdPrev:
            glyph_prev(c, cx - 5 - nudge, cy - 4, 9);
            break;
        case FtCmdSeekFwd:
            glyph_ff(c, cx - 5 + nudge, cy - 4, 9);
            break;
        case FtCmdSeekBack:
            glyph_rew(c, cx - 5 - nudge, cy - 4, 9);
            break;
        default:
            glyph_speaker(c, cx - 5, cy - 3);
            break;
        }
    }
}

/* ------------------------------------------------------------------------ */
/* Text, equalizer, progress                                                */
/* ------------------------------------------------------------------------ */

/* Draws `s` starting at x, scrolling it as a marquee if wider than TEXT_W.
 * Anything spilling left over the art is painted over by draw_art(). */
static void draw_marquee(Canvas* c, int x, int y, const char* s, uint32_t since_ms) {
    int w = canvas_string_width(c, s);
    int avail = TEXT_W - 2;
    if(w <= avail) {
        canvas_draw_str(c, x, y, s);
        return;
    }
    const int gap = 24;
    const uint32_t hold = 1500; /* pause at the start of each loop */
    int period = w + gap;
    uint32_t cycle_ms = hold + (uint32_t)period * 40; /* 25 px/s */
    uint32_t t = since_ms % cycle_ms;
    int off = t < hold ? 0 : (int)((t - hold) / 40);
    canvas_draw_str(c, x - off, y, s);
    if(off > period - avail) canvas_draw_str(c, x - off + period, y, s);
}

static void draw_text(Canvas* c, const Model* m, uint32_t now) {
    uint32_t since = now - m->track_tick;
    const char* lines[3] = {m->title, m->artist, m->album};
    const int ys[3] = {9, 20, 30};
    for(int i = 0; i < 3; i++) {
        /* staggered slide-in from the right on track change */
        float p = ease_out_cubic(((float)since - i * 70.f) / SLIDE_MS);
        int dx = (int)((1.f - p) * TEXT_W);
        canvas_set_font(c, i == 0 ? FontPrimary : FontSecondary);
        const char* s = lines[i][0] ? lines[i] : "-";
        uint32_t mq = since > 600 ? since - 600 : 0;
        draw_marquee(c, TEXT_X + dx, ys[i], s, mq);
    }
}

static void draw_eq_row(Canvas* c, const Model* m, uint32_t now) {
    const int base_y = 46;
    canvas_set_color(c, ColorBlack);

    if(m->vol_fx_tick && now - m->vol_fx_tick < VOL_FX_MS && m->volume <= 100) {
        /* Volume overlay replaces the EQ for a moment. */
        glyph_speaker(c, TEXT_X, base_y - 8);
        int segs = 12;
        int lit = (m->volume * segs + 50) / 100;
        for(int i = 0; i < segs; i++) {
            int h = 3 + i / 2;
            int x = TEXT_X + 8 + i * 4;
            if(i < lit)
                canvas_draw_box(c, x, base_y - h, 3, h);
            else
                canvas_draw_dot(c, x + 1, base_y - 1);
        }
        char buf[6];
        snprintf(buf, sizeof(buf), "%u", m->volume);
        canvas_set_font(c, FontSecondary);
        canvas_draw_str_aligned(c, 127, base_y, AlignRight, AlignBottom, buf);
        return;
    }

    /* play/pause state glyph */
    if(m->playing)
        glyph_play(c, TEXT_X, base_y - 8, 9);
    else
        glyph_pause(c, TEXT_X, base_y - 8, 9);

    /* equalizer bars */
    for(int i = 0; i < EQ_BARS; i++) {
        int h = (int)m->eq[i];
        if(h < 1) h = 1;
        int x = TEXT_X + 10 + i * 4;
        canvas_draw_box(c, x, base_y - h, 3, h);
        /* falling peak caps when playing */
        if(m->playing && h > 3) canvas_draw_line(c, x, base_y - h - 2, x + 2, base_y - h - 2);
    }

    /* bluetooth rune, flickers when data arrives */
    bool flash = (now - m->last_rx_tick) < 120;
    if(flash) {
        canvas_draw_rbox(c, 118, base_y - 11, 9, 12, 1);
        canvas_set_color(c, ColorWhite);
    }
    glyph_bt(c, 120, base_y - 10);
    canvas_set_color(c, ColorBlack);
}

static void draw_progress(Canvas* c, const Model* m, uint32_t now) {
    const int x0 = 3, y0 = 52, w = 122, h = 3;
    uint32_t el = model_elapsed(m, now);
    int fill = m->duration_ms ? (int)((uint64_t)el * w / m->duration_ms) : 0;
    if(fill > w) fill = w;

    canvas_set_color(c, ColorBlack);
    canvas_draw_rframe(c, x0 - 1, y0 - 1, w + 2, h + 2, 1);
    canvas_draw_box(c, x0, y0, fill, h);

    /* flowing shimmer through the filled part while playing */
    if(m->playing) {
        canvas_set_color(c, ColorWhite);
        int phase = (m->frame / 2) % 6;
        for(int x = phase; x < fill - 3; x += 6)
            canvas_draw_dot(c, x0 + x, y0 + 1);
        canvas_set_color(c, ColorBlack);
    }

    /* playhead with a heartbeat pulse */
    int px = x0 + fill;
    int pr = (m->playing && (m->frame % 20) < 3) ? 3 : 2;
    canvas_set_color(c, ColorWhite);
    canvas_draw_disc(c, px, y0 + 1, pr + 1);
    canvas_set_color(c, ColorBlack);
    canvas_draw_circle(c, px, y0 + 1, pr + 1);
    canvas_draw_disc(c, px, y0 + 1, pr - 1);

    /* sparks trailing the playhead */
    if(m->playing) {
        for(int k = 0; k < 3; k++) {
            int age = (m->frame + k * 7) % 21; /* 0..20 frames */
            int sx = px - 3 - age / 2;
            int sy = y0 - 1 - age / 8;
            if(sx < TEXT_X - 3 && sy < 50) continue; /* keep off the cover frame */
            if(sx > x0 && (age < 14 || (age & 1))) canvas_draw_dot(c, sx, sy);
        }
    }

    char left[12], right[12];
    format_time(left, sizeof(left), el, false);
    uint32_t rem = m->duration_ms > el ? m->duration_ms - el : 0;
    format_time(right, sizeof(right), rem, true);
    canvas_set_font(c, FontSecondary);
    canvas_draw_str(c, 1, 64, left);
    canvas_draw_str_aligned(c, 127, 64, AlignRight, AlignBottom, right);

    if(!m->playing && (m->frame / 15) % 2 == 0)
        canvas_draw_str_aligned(c, 64, 64, AlignCenter, AlignBottom, "PAUSED");
}

/* ------------------------------------------------------------------------ */
/* Screens                                                                  */
/* ------------------------------------------------------------------------ */

static void draw_waiting(Canvas* c, const Model* m) {
    int cx = 64, cy = 21;
    /* radiating rings */
    canvas_set_color(c, ColorBlack);
    for(int k = 0; k < 3; k++) {
        int r = (int)((m->frame + k * 12) % 36);
        if(r > 12) canvas_draw_circle(c, cx, cy, r);
    }
    canvas_set_color(c, ColorWhite);
    canvas_draw_disc(c, cx, cy, 12);
    canvas_set_color(c, ColorBlack);
    canvas_draw_circle(c, cx, cy, 12);
    glyph_bt_big(c, cx, cy);

    canvas_set_color(c, ColorWhite);
    canvas_draw_box(c, 0, 40, 128, 24);
    canvas_set_color(c, ColorBlack);
    canvas_set_font(c, FontPrimary);
    const char* dots[] = {"", ".", "..", "..."};
    char buf[40];
    snprintf(buf, sizeof(buf), "Waiting for phone%s", dots[(m->frame / 10) % 4]);
    canvas_draw_str(c, 13, 51, buf);
    canvas_set_font(c, FontSecondary);
    snprintf(buf, sizeof(buf), "Open FlipTune > %s", furi_hal_version_get_name_ptr());
    canvas_draw_str_aligned(c, 64, 62, AlignCenter, AlignBottom, buf);
}

static void draw_idle(Canvas* c, const Model* m) {
    float b = fabsf(sinf(m->frame * 0.15f));
    int y = 8 + (int)((1.f - b) * 8);
    glyph_note(c, 57, y);
    /* shadow squashes as the note rises */
    int sw = 4 + (int)(b * 6);
    canvas_draw_line(c, 64 - sw, 28, 64 + sw, 28);

    canvas_set_font(c, FontPrimary);
    canvas_draw_str_aligned(c, 64, 42, AlignCenter, AlignBottom, "Connected!");
    canvas_set_font(c, FontSecondary);
    canvas_draw_str_aligned(c, 64, 54, AlignCenter, AlignBottom, "Play something in");
    canvas_draw_str_aligned(c, 64, 63, AlignCenter, AlignBottom, "Apple Music");
}

static void draw_player(Canvas* c, const Model* m, uint32_t now) {
    draw_text(c, m, now); /* first: art paints over any marquee overflow */
    draw_art(c, m, now);
    draw_eq_row(c, m, now);
    draw_progress(c, m, now);
}

static void draw_cb(Canvas* c, void* ctx) {
    App* app = ctx;
    furi_mutex_acquire(app->mutex, FuriWaitForever);
    const Model* m = &app->m;
    uint32_t now = now_ms();
    canvas_clear(c);
    canvas_set_color(c, ColorBlack);
    if(!m->connected)
        draw_waiting(c, m);
    else if(!m->has_track)
        draw_idle(c, m);
    else
        draw_player(c, m, now);
    furi_mutex_release(app->mutex);
}

/* ------------------------------------------------------------------------ */
/* Bluetooth                                                                */
/* ------------------------------------------------------------------------ */

static uint16_t serial_cb(SerialServiceEvent event, void* ctx) {
    App* app = ctx;
    if(event.event == SerialServiceEventTypeDataReceived) {
        furi_stream_buffer_send(app->rx, event.data.buffer, event.data.size, 0);
    }
    return (uint16_t)furi_stream_buffer_spaces_available(app->rx);
}

static void install_serial_cb(App* app) {
    /* The BT service attaches its RPC session to the serial profile on
     * connect; we take the data stream over for the companion protocol. */
    if(app->profile)
        ble_profile_serial_set_event_callback(app->profile, RX_STREAM_SIZE, serial_cb, app);
}

static void bt_status_cb(BtStatus status, void* ctx) {
    App* app = ctx;
    app->bt_status = status;
    if(status == BtStatusConnected) install_serial_cb(app);
}

static void send_cmd(App* app, FtCmd cmd) {
    if(app->bt_status != BtStatusConnected || !app->profile) return;
    uint8_t f[6] = {FT_SYNC, FtMsgCommand, 1, 0, (uint8_t)cmd, 0};
    f[5] = f[1] ^ f[2] ^ f[3] ^ f[4];
    ble_profile_serial_tx(app->profile, f, sizeof(f));
}

/* ------------------------------------------------------------------------ */
/* Protocol handling (main thread)                                          */
/* ------------------------------------------------------------------------ */

static uint16_t rd16(const uint8_t* p) {
    return p[0] | (p[1] << 8);
}

static uint32_t rd32(const uint8_t* p) {
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static const uint8_t* take_str(const uint8_t* p, const uint8_t* end, char* out) {
    size_t n = 0;
    while(p < end && *p) {
        if(n < STR_MAX - 1) out[n++] = (*p >= 0x20 && *p < 0x7f) ? (char)*p : '?';
        p++;
    }
    out[n] = 0;
    return p < end ? p + 1 : end;
}

static void handle_msg(App* app, uint8_t type, const uint8_t* p, uint16_t len) {
    Model* m = &app->m;
    uint32_t now = now_ms();

    switch(type) {
    case FtMsgTrack: {
        char t[STR_MAX], ar[STR_MAX], al[STR_MAX];
        const uint8_t* end = p + len;
        p = take_str(p, end, t);
        p = take_str(p, end, ar);
        take_str(p, end, al);
        bool changed = !m->has_track || strcmp(t, m->title) || strcmp(ar, m->artist) ||
                       strcmp(al, m->album);
        bool album_changed = !m->has_track || strcmp(al, m->album) || strcmp(ar, m->artist);
        if(changed) {
            strlcpy(m->title, t, STR_MAX);
            strlcpy(m->artist, ar, STR_MAX);
            strlcpy(m->album, al, STR_MAX);
            m->track_tick = now;
            m->has_track = true;
        }
        if(album_changed) {
            m->ident_hash[0] = fnv1a(al, fnv1a(ar, 2166136261u));
            m->ident_hash[1] = fnv1a(ar, fnv1a(al, 0x9E3779B9u));
            m->has_art = false;
            m->art_pending = true;
            m->art_pending_tick = now;
            memset(m->art_rx, 0, sizeof(m->art_rx));
        }
        break;
    }
    case FtMsgState: {
        if(len < 10) break;
        bool was_playing = m->playing;
        m->playing = p[0] != 0;
        m->elapsed_ms = rd32(p + 1);
        m->duration_ms = rd32(p + 5);
        m->state_tick = now;
        uint8_t vol = p[9];
        if(vol <= 100 && m->volume <= 100 && vol != m->volume) m->vol_fx_tick = now;
        m->volume = vol;
        (void)was_playing;
        break;
    }
    case FtMsgArtChunk: {
        if(len < 2) break;
        uint16_t off = rd16(p);
        uint16_t n = len - 2;
        if(off >= FT_ART_BYTES) break;
        if(off + n > FT_ART_BYTES) n = FT_ART_BYTES - off;
        memcpy(m->art_rx + off, p + 2, n);
        break;
    }
    case FtMsgArtDone:
        if(!(m->has_art && memcmp(m->art, m->art_rx, FT_ART_BYTES) == 0)) {
            memcpy(m->art, m->art_rx, FT_ART_BYTES);
            m->has_art = true;
            m->reveal_tick = now;
        }
        m->art_pending = false;
        break;
    case FtMsgArtNone:
        if(m->has_art || m->art_pending) m->reveal_tick = now;
        m->has_art = false;
        m->art_pending = false;
        break;
    default:
        break;
    }
}

static void parse_byte(App* app, uint8_t b) {
    Parser* ps = &app->parser;
    switch(ps->st) {
    case PsSync:
        if(b == FT_SYNC) ps->st = PsType;
        break;
    case PsType:
        ps->type = b;
        ps->chk = b;
        ps->st = PsLen0;
        break;
    case PsLen0:
        ps->len = b;
        ps->chk ^= b;
        ps->st = PsLen1;
        break;
    case PsLen1:
        ps->len |= (uint16_t)b << 8;
        ps->chk ^= b;
        ps->pos = 0;
        if(ps->len > FT_MAX_PAYLOAD)
            ps->st = (b == FT_SYNC) ? PsType : PsSync;
        else
            ps->st = ps->len ? PsPayload : PsChk;
        break;
    case PsPayload:
        ps->buf[ps->pos++] = b;
        ps->chk ^= b;
        if(ps->pos >= ps->len) ps->st = PsChk;
        break;
    case PsChk:
        if(b == ps->chk) {
            handle_msg(app, ps->type, ps->buf, ps->len);
        } else {
            FURI_LOG_W(TAG, "bad checksum type=%02x len=%u", ps->type, ps->len);
        }
        ps->st = PsSync;
        break;
    }
}

static void drain_rx(App* app) {
    uint8_t buf[128];
    size_t n;
    bool got = false;
    while((n = furi_stream_buffer_receive(app->rx, buf, sizeof(buf), 0)) > 0) {
        for(size_t i = 0; i < n; i++)
            parse_byte(app, buf[i]);
        got = true;
    }
    if(got) app->m.last_rx_tick = now_ms();
}

/* ------------------------------------------------------------------------ */
/* Animation step + input                                                   */
/* ------------------------------------------------------------------------ */

static void step_anim(App* app) {
    Model* m = &app->m;
    m->frame++;
    for(int i = 0; i < EQ_BARS; i++) {
        float target;
        if(m->playing) {
            float f = (float)m->frame;
            float a = 0.5f + 0.5f * sinf(f * (0.17f + 0.031f * i) + i * 1.7f);
            float b = 0.5f + 0.5f * sinf(f * 0.43f + i * 0.9f);
            target = 2.f + a * 7.f + b * 3.f;
            /* random kick, like a drum hit */
            if((xorshift(&app->rng) & 31) == 0) target = 12.f;
        } else {
            target = 1.f;
        }
        float k = target > m->eq[i] ? 0.55f : 0.18f; /* fast attack, slow release */
        m->eq[i] += (target - m->eq[i]) * k;
    }
}

static void fx(App* app, FtCmd cmd) {
    app->m.fx_cmd = cmd;
    app->m.fx_tick = now_ms();
    notification_message(app->notif, &seq_tap);
}

/* Returns false to exit. */
static bool handle_input(App* app, const InputEvent* e) {
    Model* m = &app->m;
    uint32_t now = now_ms();

    if(e->key == InputKeyBack && e->type == InputTypeShort) return false;
    if(e->key == InputKeyBack && e->type == InputTypeLong) return false;
    if(!m->connected) return true;

    FtCmd cmd = 0;
    switch(e->key) {
    case InputKeyOk:
        if(e->type == InputTypeShort) {
            cmd = FtCmdPlayPause;
            /* optimistic toggle; the companion confirms with a State msg */
            m->elapsed_ms = model_elapsed(m, now);
            m->state_tick = now;
            m->playing = !m->playing;
        }
        break;
    case InputKeyRight:
        if(e->type == InputTypeShort) cmd = FtCmdNext;
        if(e->type == InputTypeLong || e->type == InputTypeRepeat) {
            cmd = FtCmdSeekFwd;
            m->elapsed_ms = model_elapsed(m, now) + 10000;
            if(m->duration_ms && m->elapsed_ms > m->duration_ms) m->elapsed_ms = m->duration_ms;
            m->state_tick = now;
        }
        break;
    case InputKeyLeft:
        if(e->type == InputTypeShort) cmd = FtCmdPrev;
        if(e->type == InputTypeLong || e->type == InputTypeRepeat) {
            cmd = FtCmdSeekBack;
            uint32_t el = model_elapsed(m, now);
            m->elapsed_ms = el > 10000 ? el - 10000 : 0;
            m->state_tick = now;
        }
        break;
    case InputKeyUp:
        if(e->type == InputTypeShort || e->type == InputTypeRepeat) {
            cmd = FtCmdVolUp;
            if(m->volume <= 100) m->volume = m->volume > 94 ? 100 : m->volume + 6;
            m->vol_fx_tick = now;
        }
        break;
    case InputKeyDown:
        if(e->type == InputTypeShort || e->type == InputTypeRepeat) {
            cmd = FtCmdVolDown;
            if(m->volume <= 100) m->volume = m->volume < 6 ? 0 : m->volume - 6;
            m->vol_fx_tick = now;
        }
        break;
    default:
        break;
    }

    if(cmd) {
        send_cmd(app, cmd);
        if(cmd != FtCmdVolUp && cmd != FtCmdVolDown) fx(app, cmd);
        else notification_message(app->notif, &seq_tap);
    }
    return true;
}

static void connection_step(App* app) {
    Model* m = &app->m;
    uint32_t now = now_ms();
    bool connected = app->bt_status == BtStatusConnected;

    if(connected && !app->was_connected) {
        m->connected = true;
        m->connect_tick = now;
        app->sync_sent = false;
        notification_message(app->notif, &sequence_blink_blue_100);
    } else if(!connected && app->was_connected) {
        m->connected = false;
        m->has_track = false;
        m->playing = false;
        m->has_art = false;
        app->parser.st = PsSync;
    }
    app->was_connected = connected;

    if(!connected) return;

    /* Ask for a full sync shortly after connecting, then poll periodically.
     * Polls also wake a backgrounded iOS companion. */
    if(!app->sync_sent && now - m->connect_tick > 600) {
        install_serial_cb(app);
        send_cmd(app, FtCmdSync);
        app->sync_sent = true;
        app->last_poll_tick = now;
    } else if(app->sync_sent && now - app->last_poll_tick > POLL_MS) {
        install_serial_cb(app);
        send_cmd(app, FtCmdPoll);
        app->last_poll_tick = now;
    }
}

/* ------------------------------------------------------------------------ */
/* Lifecycle                                                                */
/* ------------------------------------------------------------------------ */

static void input_cb(InputEvent* e, void* ctx) {
    App* app = ctx;
    Event ev = {.type = EvInput, .input = *e};
    furi_message_queue_put(app->queue, &ev, 0);
}

static void timer_cb(void* ctx) {
    App* app = ctx;
    Event ev = {.type = EvTick};
    furi_message_queue_put(app->queue, &ev, 0);
}

int32_t fliptune_app(void* p) {
    UNUSED(p);
    App* app = malloc(sizeof(App));
    memset(app, 0, sizeof(App));

    app->m.volume = 255;
    app->rng = furi_hal_random_get() | 1;
    app->queue = furi_message_queue_alloc(16, sizeof(Event));
    app->mutex = furi_mutex_alloc(FuriMutexTypeNormal);
    app->rx = furi_stream_buffer_alloc(RX_STREAM_SIZE, 1);

    app->view_port = view_port_alloc();
    view_port_draw_callback_set(app->view_port, draw_cb, app);
    view_port_input_callback_set(app->view_port, input_cb, app);
    app->gui = furi_record_open(RECORD_GUI);
    gui_add_view_port(app->gui, app->view_port, GuiLayerFullscreen);
    app->notif = furi_record_open(RECORD_NOTIFICATION);

    app->bt = furi_record_open(RECORD_BT);
    bt_disconnect(app->bt);
    furi_delay_ms(200);
    app->profile = bt_profile_start(app->bt, ble_profile_serial, NULL);
    if(!app->profile) {
        FURI_LOG_E(TAG, "failed to start serial profile");
    } else {
        install_serial_cb(app);
        ble_profile_serial_set_rpc_active(app->profile, false);
        furi_hal_bt_start_advertising();
    }
    bt_set_status_changed_callback(app->bt, bt_status_cb, app);

    app->timer = furi_timer_alloc(timer_cb, FuriTimerTypePeriodic, app);
    furi_timer_start(app->timer, furi_ms_to_ticks(TICK_MS));

    Event ev;
    bool running = true;
    while(running) {
        if(furi_message_queue_get(app->queue, &ev, FuriWaitForever) != FuriStatusOk) continue;
        furi_mutex_acquire(app->mutex, FuriWaitForever);
        if(ev.type == EvInput) {
            running = handle_input(app, &ev.input);
        } else {
            connection_step(app);
            drain_rx(app);
            step_anim(app);
        }
        furi_mutex_release(app->mutex);
        view_port_update(app->view_port);
    }

    furi_timer_stop(app->timer);
    furi_timer_free(app->timer);

    bt_set_status_changed_callback(app->bt, NULL, NULL);
    if(app->profile) ble_profile_serial_set_event_callback(app->profile, 0, NULL, NULL);
    bt_disconnect(app->bt);
    furi_delay_ms(200);
    bt_profile_restore_default(app->bt);
    furi_record_close(RECORD_BT);

    gui_remove_view_port(app->gui, app->view_port);
    view_port_free(app->view_port);
    furi_record_close(RECORD_GUI);
    furi_record_close(RECORD_NOTIFICATION);

    furi_stream_buffer_free(app->rx);
    furi_mutex_free(app->mutex);
    furi_message_queue_free(app->queue);
    free(app);
    return 0;
}
