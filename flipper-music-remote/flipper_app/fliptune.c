/*
 * TAPE//DECK — a cyberdeck cassette-player media remote for Flipper Zero.
 *
 * The Flipper pairs with an iPhone (or Mac / iPad / Android) as a Bluetooth
 * media remote (HID consumer control). Nothing to install on the phone:
 * pair it in Settings > Bluetooth and the buttons drive Apple Music.
 *
 * iOS does not share song info with HID remotes, so the deck shows what
 * *you* do: reels, tape counter and transport react to your presses.
 *
 *   OK          play / pause
 *   Right       next track      (fast-forward burst, eject, new tape)
 *   Left        restart / prev  (rewind; within 3 s also swaps the tape)
 *   Hold L / R  rewind / fast-forward while held
 *   Up / Down   volume
 *   Back        exit       Hold Back: forget paired devices
 */

#include <furi.h>
#include <furi_hal.h>
#include <furi_hal_usb_hid.h>
#include <gui/gui.h>
#include <input/input.h>
#include <notification/notification_messages.h>
#include <bt/bt_service/bt.h>
#include <extra_profiles/hid_profile.h>
#include <storage/storage.h>

#include <math.h>
#include <stdio.h>
#include <string.h>

#define TAG "TapeDeck"

#define KEYS_PATH APP_DATA_PATH(".tapedeck.keys")
#define TICK_MS   33

/* layout */
#define CAS_X   1
#define CAS_Y   10
#define CAS_W   76
#define CAS_H   37
#define PANEL_X 79
#define BAR_Y   48

/* sequence timings (ms) */
#define SEQ_BURST     300
#define SEQ_EJECT_END 600
#define SEQ_LAND      1000
#define SEQ_END       1100
#define INS_LAND      400
#define INS_END       500
#define RESTART_SPIN  700
#define RESTART_END   1000
#define FLASH_MS      650

typedef enum {
    SeqNone,
    SeqSkip, /* FF burst -> eject -> next tape */
    SeqPrev, /* REW burst -> eject -> previous tape */
    SeqRestart, /* rewind the current tape to 0 */
    SeqInsert, /* tape drops in (on connect) */
} Seq;

typedef struct {
    bool connected;
    uint32_t boot_tick; /* terminal typing start */
    uint32_t link_tick; /* when the link came up */

    bool playing; /* best guess; we only see our own presses */
    bool hold_ff, hold_rew;

    float elapsed_ms; /* local tape counter */
    float v; /* tape speed: 1 = play, + forward, - rewind */
    float p; /* tape wound onto the right reel, 0..1 */
    float ang_l, ang_r;
    float bar_off;
    uint16_t tape_no;

    Seq seq;
    uint32_t seq_tick;
    float seq_from_ms, seq_from_p;
    bool swapped;

    const char* flash; /* transient mode-box label */
    uint32_t flash_tick;
    int8_t vol_dir;
    uint32_t vol_tick;
    uint32_t wipe_tick;

    float vu[2], peak[2];
    uint32_t glitch_tick, next_glitch;
    int glitch_y;

    uint32_t frame;
    uint32_t last_ms;
} Model;

typedef enum {
    EvInput,
    EvTick,
} EvType;

typedef struct {
    EvType type;
    InputEvent input;
} Event;

typedef struct {
    Gui* gui;
    ViewPort* view_port;
    FuriMessageQueue* queue;
    FuriTimer* timer;
    FuriMutex* mutex;
    NotificationApp* notif;
    Bt* bt;
    FuriHalBleProfileBase* hid;
    volatile BtStatus bt_status;
    bool was_connected;
    uint32_t rng;
    Model m;
} App;

static const NotificationSequence seq_tap = {
    &message_vibro_on,
    &message_delay_10,
    &message_vibro_off,
    NULL,
};

static const NotificationSequence seq_clunk = {
    &message_vibro_on,
    &message_delay_25,
    &message_vibro_off,
    NULL,
};

/* ------------------------------------------------------------------------ */
/* helpers                                                                  */
/* ------------------------------------------------------------------------ */

static uint32_t now_ms(void) {
    return furi_get_tick() * 1000 / furi_kernel_get_tick_frequency();
}

static float clampf(float v, float lo, float hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

static float ease_in(float t) {
    t = clampf(t, 0, 1);
    return t * t * t;
}

static float ease_out(float t) {
    t = clampf(t, 0, 1);
    float u = 1 - t;
    return 1 - u * u * u;
}

static float ease_out_back(float t) {
    t = clampf(t, 0, 1);
    const float c1 = 1.9f, c3 = c1 + 1;
    float u = t - 1;
    return 1 + c3 * u * u * u + c1 * u * u;
}

static uint32_t xorshift(uint32_t* s) {
    uint32_t x = *s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return *s = x;
}

static uint32_t hash32(uint32_t x) {
    x ^= x >> 16;
    x *= 0x7feb352d;
    x ^= x >> 15;
    x *= 0x846ca68b;
    x ^= x >> 16;
    return x;
}

/* ------------------------------------------------------------------------ */
/* 3x5 micro font for HUD accents                                           */
/* ------------------------------------------------------------------------ */

typedef struct {
    char c;
    uint8_t rows[5];
} MicroGlyph;

static const MicroGlyph micro[] = {
    {'0', {7, 5, 5, 5, 7}}, {'1', {2, 6, 2, 2, 7}}, {'2', {7, 1, 7, 4, 7}},
    {'3', {7, 1, 3, 1, 7}}, {'4', {5, 5, 7, 1, 1}}, {'5', {7, 4, 7, 1, 7}},
    {'6', {7, 4, 7, 5, 7}}, {'7', {7, 1, 2, 2, 2}}, {'8', {7, 5, 7, 5, 7}},
    {'9', {7, 5, 7, 1, 7}}, {'A', {2, 5, 7, 5, 5}}, {'B', {6, 5, 6, 5, 6}},
    {'C', {3, 4, 4, 4, 3}}, {'D', {6, 5, 5, 5, 6}}, {'E', {7, 4, 6, 4, 7}},
    {'F', {7, 4, 6, 4, 4}}, {'G', {3, 4, 5, 5, 3}}, {'H', {5, 5, 7, 5, 5}},
    {'I', {7, 2, 2, 2, 7}}, {'K', {5, 5, 6, 5, 5}}, {'L', {4, 4, 4, 4, 7}},
    {'M', {5, 7, 7, 5, 5}}, {'N', {6, 5, 5, 5, 5}}, {'O', {2, 5, 5, 5, 2}},
    {'P', {6, 5, 6, 4, 4}}, {'R', {6, 5, 6, 5, 5}}, {'S', {3, 4, 2, 1, 6}},
    {'T', {7, 2, 2, 2, 2}}, {'U', {5, 5, 5, 5, 7}}, {'V', {5, 5, 5, 5, 2}},
    {'W', {5, 5, 7, 7, 5}}, {'X', {5, 5, 2, 5, 5}}, {'Y', {5, 5, 2, 2, 2}},
    {'+', {0, 2, 7, 2, 0}}, {'-', {0, 0, 7, 0, 0}}, {':', {0, 2, 0, 2, 0}},
    {'/', {1, 1, 2, 4, 4}}, {'.', {0, 0, 0, 0, 2}}, {'>', {4, 2, 1, 2, 4}},
    {'<', {1, 2, 4, 2, 1}}, {'#', {5, 7, 5, 7, 5}},
};

/* Draws micro text with its top-left at (x, y). Returns width. */
static int micro_str(Canvas* c, int x, int y, const char* s) {
    int x0 = x;
    for(; *s; s++, x += 4) {
        for(size_t g = 0; g < COUNT_OF(micro); g++) {
            if(micro[g].c != *s) continue;
            for(int r = 0; r < 5; r++)
                for(int b = 0; b < 3; b++)
                    if(micro[g].rows[r] & (4 >> b)) canvas_draw_dot(c, x + b, y + r);
            break;
        }
    }
    return x - x0 - 1;
}

/* ------------------------------------------------------------------------ */
/* primitives                                                               */
/* ------------------------------------------------------------------------ */

static void tri_r(Canvas* c, int x, int y, int h) {
    for(int i = 0; i < (h + 1) / 2; i++)
        canvas_draw_line(c, x + i, y + i, x + i, y + h - 1 - i);
}

static void tri_l(Canvas* c, int x, int y, int h) {
    int w = (h + 1) / 2;
    for(int i = 0; i < w; i++)
        canvas_draw_line(c, x + w - 1 - i, y + i, x + w - 1 - i, y + h - 1 - i);
}

static void chevron(Canvas* c, int x, int y, bool right) {
    if(right) {
        canvas_draw_line(c, x, y, x + 2, y + 2);
        canvas_draw_line(c, x + 2, y + 2, x, y + 4);
    } else {
        canvas_draw_line(c, x + 2, y, x, y + 2);
        canvas_draw_line(c, x, y + 2, x + 2, y + 4);
    }
}

/* HUD corner brackets around a rectangle */
static void brackets(Canvas* c, int x, int y, int w, int h, int len) {
    int x1 = x + w - 1, y1 = y + h - 1;
    canvas_draw_line(c, x, y, x + len, y);
    canvas_draw_line(c, x, y, x, y + len);
    canvas_draw_line(c, x1, y, x1 - len, y);
    canvas_draw_line(c, x1, y, x1, y + len);
    canvas_draw_line(c, x, y1, x + len, y1);
    canvas_draw_line(c, x, y1, x, y1 - len);
    canvas_draw_line(c, x1, y1, x1 - len, y1);
    canvas_draw_line(c, x1, y1, x1, y1 - len);
}

/* ------------------------------------------------------------------------ */
/* cassette                                                                 */
/* ------------------------------------------------------------------------ */

static void draw_reel(Canvas* c, int cx, int cy, float r, float ang) {
    int ri = (int)(r + 0.5f);
    canvas_set_color(c, ColorWhite);
    canvas_draw_disc(c, cx, cy, ri);
    canvas_set_color(c, ColorBlack);
    canvas_draw_circle(c, cx, cy, ri);
    if(ri >= 7) canvas_draw_circle(c, cx, cy, ri - 3); /* tape layers */
    /* hub + rotating teeth */
    canvas_draw_circle(c, cx, cy, 3);
    canvas_draw_dot(c, cx, cy);
    for(int k = 0; k < 3; k++) {
        float a = ang + k * 2.0944f;
        canvas_draw_line(
            c,
            cx + (int)roundf(cosf(a) * 1.5f),
            cy + (int)roundf(sinf(a) * 1.5f),
            cx + (int)roundf(cosf(a) * 3.f),
            cy + (int)roundf(sinf(a) * 3.f));
    }
    /* a marker on the tape pack makes the spin readable */
    if(ri >= 6) {
        float a = ang * 0.7f + 1.f;
        int mx = cx + (int)roundf(cosf(a) * (r - 1.5f));
        int my = cy + (int)roundf(sinf(a) * (r - 1.5f));
        canvas_set_color(c, ColorXOR);
        canvas_draw_box(c, mx - 1, my - 1, 2, 2);
        canvas_set_color(c, ColorBlack);
    }
}

static void draw_cassette(Canvas* c, const Model* m, int ox, int oy) {
    canvas_set_color(c, ColorWhite);
    canvas_draw_rbox(c, ox, oy, CAS_W, CAS_H, 3);
    canvas_set_color(c, ColorBlack);
    canvas_draw_rframe(c, ox, oy, CAS_W, CAS_H, 3);

    /* screws */
    canvas_draw_dot(c, ox + 2, oy + 2);
    canvas_draw_dot(c, ox + CAS_W - 3, oy + 2);
    canvas_draw_dot(c, ox + 2, oy + CAS_H - 3);
    canvas_draw_dot(c, ox + CAS_W - 3, oy + CAS_H - 3);

    /* label: tape id, barcode, side badge */
    canvas_draw_rframe(c, ox + 5, oy + 2, CAS_W - 10, 9, 1);
    char id[12];
    snprintf(id, sizeof(id), "TAPE#%02u", m->tape_no % 100);
    micro_str(c, ox + 7, oy + 4, id);
    uint32_t h = hash32(m->tape_no * 2654435761u + 7);
    for(int i = 0; i < 16; i++)
        if((h >> i) & 1) canvas_draw_line(c, ox + 37 + i, oy + 4, ox + 37 + i, oy + 8);
    canvas_draw_box(c, ox + 60, oy + 3, 9, 7);
    canvas_set_color(c, ColorWhite);
    micro_str(c, ox + 63, oy + 4, (m->tape_no & 1) ? "A" : "B");
    canvas_set_color(c, ColorBlack);

    /* window + reels */
    canvas_draw_rframe(c, ox + 15, oy + 15, 46, 13, 4);
    float rl = 4.f + 5.f * (1.f - m->p);
    float rr = 4.f + 5.f * m->p;
    int cyr = oy + 21;
    draw_reel(c, ox + 23, cyr, rl, m->ang_l);
    draw_reel(c, ox + 53, cyr, rr, m->ang_r);

    /* tape path to the head */
    canvas_draw_line(c, ox + 23 - (int)rl + 1, cyr + 2, ox + 15, oy + 31);
    canvas_draw_line(c, ox + 53 + (int)rr - 1, cyr + 2, ox + 61, oy + 31);

    /* bottom bridge with capstan holes and head opening */
    canvas_draw_line(c, ox + 11, oy + CAS_H - 1, ox + 15, oy + 31);
    canvas_draw_line(c, ox + 15, oy + 31, ox + 61, oy + 31);
    canvas_draw_line(c, ox + 61, oy + 31, ox + 65, oy + CAS_H - 1);
    canvas_draw_disc(c, ox + 21, oy + 34, 1);
    canvas_draw_disc(c, ox + 55, oy + 34, 1);
    canvas_draw_frame(c, ox + 34, oy + 33, 8, 3);
}

/* Horizontal speed streaks across the cassette while winding fast. */
static void draw_streaks(Canvas* c, const Model* m) {
    float sp = fabsf(m->v);
    if(sp < 3.f) return;
    bool fwd = m->v > 0;
    int n = sp > 8 ? 7 : 4;
    canvas_set_color(c, ColorXOR);
    for(int k = 0; k < n; k++) {
        uint32_t hk = hash32(k * 977 + 13);
        int y = CAS_Y + 3 + (int)(hk % (CAS_H - 6));
        int len = 5 + (int)((hk >> 8) % 9);
        int span = CAS_W + 30;
        int pos = (int)((hk >> 4) % span + m->frame * (sp * 0.9f)) % span;
        int x = fwd ? pos - 15 : CAS_W + 15 - pos;
        canvas_draw_line(c, x, y, x + len, y);
    }
    canvas_set_color(c, ColorBlack);
}

/* ------------------------------------------------------------------------ */
/* HUD, panel, transport bar                                                */
/* ------------------------------------------------------------------------ */

static const char* mode_label(const Model* m, uint32_t now, bool* blink_ok) {
    *blink_ok = true;
    int32_t st = (int32_t)(now - m->seq_tick);
    if(m->wipe_tick && now - m->wipe_tick < 1500) return "UNPAIRED";
    if(m->flash && now - m->flash_tick < FLASH_MS) return m->flash;
    uint32_t t = st > 0 ? (uint32_t)st : 0;
    switch(m->seq) {
    case SeqSkip:
        return t < SEQ_BURST ? ">> SKIP" : (t < SEQ_EJECT_END ? "EJECT" : "LOAD");
    case SeqPrev:
        return t < SEQ_BURST ? "<< BACK" : (t < SEQ_EJECT_END ? "EJECT" : "LOAD");
    case SeqRestart:
        return t < RESTART_SPIN ? "<< REW" : "RESTART";
    case SeqInsert:
        return "LOAD";
    default:
        break;
    }
    if(m->hold_ff) return ">> FF";
    if(m->hold_rew) return "<< REW";
    if(m->vol_tick && now - m->vol_tick < FLASH_MS) return m->vol_dir > 0 ? "VOL +" : "VOL -";
    if(m->playing) return "> PLAY";
    *blink_ok = (m->frame / 12) % 2 == 0;
    return "|| PAUSE";
}

static void draw_hud(Canvas* c, const Model* m) {
    canvas_set_font(c, FontSecondary);
    canvas_draw_str(c, 1, 7, "TAPE//DECK");
    /* data lights */
    for(int i = 0; i < 5; i++) {
        bool on = m->playing ? (hash32(m->frame / 4 * 31 + i) & 1) : (i == (int)(m->frame / 8) % 5);
        if(on)
            canvas_draw_box(c, 64 + i * 4, 2, 2, 4);
        else
            canvas_draw_dot(c, 64 + i * 4, 4);
    }
    /* link: label + signal bars sweeping */
    micro_str(c, 95, 2, "LNK");
    for(int i = 0; i < 4; i++) {
        int h = 2 + i * 2;
        bool lit = ((m->frame / 6) % 6) >= (uint32_t)i;
        if(lit)
            canvas_draw_box(c, 109 + i * 4, 8 - h, 2, h);
        else
            canvas_draw_dot(c, 109 + i * 4, 7);
    }
    /* dashed divider scrolling with the tape */
    int off = ((int)m->bar_off % 4 + 4) % 4;
    for(int x = -off; x < 128; x += 4)
        canvas_draw_line(c, x, 8, x + 1, 8);
}

static void draw_panel(Canvas* c, const Model* m, uint32_t now) {
    const int x0 = PANEL_X, y0 = CAS_Y, w = 128 - PANEL_X, h = CAS_H;
    canvas_set_color(c, ColorWhite);
    canvas_draw_box(c, x0 - 1, y0, w + 1, h);
    canvas_set_color(c, ColorBlack);
    brackets(c, x0, y0, w, h, 3);

    /* mode box */
    bool show = true;
    const char* lbl = mode_label(m, now, &show);
    canvas_draw_rbox(c, x0 + 2, y0 + 2, w - 4, 10, 2);
    if(show) {
        canvas_set_color(c, ColorWhite);
        canvas_set_font(c, FontSecondary);
        canvas_draw_str_aligned(c, x0 + w / 2, y0 + 11, AlignCenter, AlignBottom, lbl);
        canvas_set_color(c, ColorBlack);
    }

    /* tape counter */
    uint32_t s = (uint32_t)(m->elapsed_ms > 0 ? m->elapsed_ms : 0) / 1000;
    char buf[12];
    bool colon = !m->playing || m->seq || (m->frame / 15) % 2 == 0;
    snprintf(buf, sizeof(buf), "%02lu%c%02lu", (unsigned long)(s / 60 % 100), colon ? ':' : ' ', (unsigned long)(s % 60));
    micro_str(c, x0 + 3, y0 + 16, "T+");
    canvas_set_font(c, FontPrimary);
    canvas_draw_str(c, x0 + 14, y0 + 23, buf);

    /* VU meters or volume overlay */
    int vy = y0 + 26;
    if(m->vol_tick && now - m->vol_tick < FLASH_MS) {
        micro_str(c, x0 + 3, vy + 2, "VOL");
        uint32_t t = now - m->vol_tick;
        for(int i = 0; i < 4; i++) {
            int x = x0 + 18 + i * 7;
            int phase = (int)(t / 60) - i;
            if(phase < 0) continue;
            int dy = (phase % 3);
            int y = vy + 2 + (m->vol_dir > 0 ? -dy : dy);
            if(m->vol_dir > 0) {
                canvas_draw_line(c, x, y + 4, x + 2, y + 2);
                canvas_draw_line(c, x + 2, y + 2, x + 4, y + 4);
            } else {
                canvas_draw_line(c, x, y + 2, x + 2, y + 4);
                canvas_draw_line(c, x + 2, y + 4, x + 4, y + 2);
            }
        }
        return;
    }
    for(int ch = 0; ch < 2; ch++) {
        int y = vy + ch * 5;
        micro_str(c, x0 + 3, y, ch ? "R" : "L");
        int lit = (int)(m->vu[ch] * 12 + 0.5f);
        int pk = (int)(m->peak[ch] * 12 + 0.5f);
        for(int i = 0; i < 12; i++) {
            int x = x0 + 9 + i * 3;
            if(i < lit)
                canvas_draw_box(c, x, y, 2, 4);
            else if(i == pk && pk > 0)
                canvas_draw_line(c, x, y, x, y + 3);
            else
                canvas_draw_dot(c, x, y + 3);
        }
    }
}

static void draw_bar(Canvas* c, const Model* m) {
    const int y = BAR_Y;
    const int head = 64;
    canvas_set_color(c, ColorWhite);
    canvas_draw_box(c, 0, y - 1, 128, 16);
    canvas_set_color(c, ColorBlack);

    /* end brackets with blinking status pips */
    canvas_draw_line(c, 0, y, 0, y + 8);
    canvas_draw_line(c, 0, y, 2, y);
    canvas_draw_line(c, 0, y + 8, 2, y + 8);
    canvas_draw_line(c, 127, y, 127, y + 8);
    canvas_draw_line(c, 125, y, 127, y);
    canvas_draw_line(c, 125, y + 8, 127, y + 8);
    if(m->playing || m->seq) {
        if((m->frame / 8) % 2) canvas_draw_box(c, 2, y + 3, 2, 3);
        if((m->frame / 8) % 2 == 0) canvas_draw_box(c, 124, y + 3, 2, 3);
    }

    /* rails: dashed, scrolling with the tape */
    int off = (int)m->bar_off;
    for(int x = 5; x < 123; x++) {
        int t = ((x + off) % 8 + 8) % 8;
        if(t < 5) {
            canvas_draw_dot(c, x, y + 1);
            canvas_draw_dot(c, x, y + 7);
        }
        /* reel index marks on the rails every 16 px */
        if(((x + off) % 16 + 16) % 16 == 0) {
            canvas_draw_dot(c, x, y + 2);
            canvas_draw_dot(c, x, y + 6);
        }
    }

    /* chevrons streaming toward / away from the head */
    float sp = m->v;
    if(fabsf(sp) > 0.05f) {
        bool fwd = sp > 0;
        int spacing = 9;
        int shift = ((int)(m->bar_off * 0.8f) % spacing + spacing) % spacing;
        for(int side = 0; side < 2; side++) {
            for(int i = 0; i < 4; i++) {
                int d = 8 + i * spacing + (fwd == (side == 0) ? shift : spacing - 1 - shift);
                int x = side == 0 ? head - d - 2 : head + d;
                if(x < 6 || x > 119) continue;
                chevron(c, x, y + 2, fwd);
                if(fabsf(sp) > 3) chevron(c, x + (fwd ? -2 : 2), y + 2, fwd); /* doubled at speed */
            }
        }
    } else {
        /* idle lane: faint center dots */
        for(int x = 8; x < 120; x += 6)
            canvas_draw_dot(c, x, y + 4);
    }

    /* the head: inverted block with the transport glyph, pulsing brackets */
    canvas_draw_rbox(c, head - 6, y - 1, 13, 11, 2);
    canvas_set_color(c, ColorWhite);
    if(m->seq == SeqSkip || m->hold_ff) {
        tri_r(c, head - 4, y + 2, 5);
        tri_r(c, head, y + 2, 5);
    } else if(m->seq == SeqPrev || m->seq == SeqRestart || m->hold_rew) {
        tri_l(c, head - 4, y + 2, 5);
        tri_l(c, head, y + 2, 5);
    } else if(m->playing) {
        tri_r(c, head - 1, y + 1, 7);
    } else {
        canvas_draw_box(c, head - 3, y + 2, 2, 5);
        canvas_draw_box(c, head + 1, y + 2, 2, 5);
    }
    canvas_set_color(c, ColorBlack);
    int pulse = (m->playing && (m->frame % 20) < 10) ? 1 : 0;
    brackets(c, head - 8 - pulse * 2, y - 2, 17 + pulse * 4, 13, 2);
}

static void draw_ticker(Canvas* c, const Model* m) {
    char buf[96];
    snprintf(
        buf,
        sizeof(buf),
        "TAPE %02u  //  OK PLAY  <> TRACK  HOLD SCAN  +- VOL  //  BT HID LINK OK  //  ",
        m->tape_no % 100);
    int w = micro_str(c, 200, 70, buf) + 4; /* measure off-screen */
    int off = (int)(m->frame / 2) % w;
    micro_str(c, 1 - off, 58, buf);
    micro_str(c, 1 - off + w, 58, buf);
}

/* ------------------------------------------------------------------------ */
/* screens                                                                  */
/* ------------------------------------------------------------------------ */

static void draw_terminal(Canvas* c, const Model* m, uint32_t now) {
    char name[40];
    snprintf(name, sizeof(name), "> beacon: Tape %s", furi_hal_version_get_name_ptr());
    const char* lines[] = {
        "TAPE//DECK OS v2.0",
        "> bt hid core ...... OK",
        name,
        "> on iPhone open",
        "  Settings > Bluetooth",
        "> awaiting link",
    };
    canvas_set_font(c, FontSecondary);
    int budget = (int)((now - m->boot_tick) / 22); /* chars typed so far */
    int y = 8;
    for(size_t i = 0; i < COUNT_OF(lines); i++, y += 10) {
        int len = strlen(lines[i]);
        int n = budget < len ? budget : len;
        if(n <= 0) break;
        char tmp[48];
        memcpy(tmp, lines[i], n);
        tmp[n] = 0;
        canvas_draw_str(c, 1, y, tmp);
        int cw = canvas_string_width(c, tmp);
        budget -= len;
        bool last = budget <= 0 || i == COUNT_OF(lines) - 1;
        if(last && (m->frame / 8) % 2) canvas_draw_box(c, 2 + cw, y - 6, 4, 7);
        if(last) {
            if(i == COUNT_OF(lines) - 1 && n == len) {
                /* animated dots after the final line */
                for(int d = 0; d < 3; d++)
                    if((int)((m->frame / 6) % 4) > d) canvas_draw_box(c, 8 + cw + d * 4, y - 2, 2, 2);
            }
            break;
        }
    }
    /* spinner */
    const char* spin = "|/-\\";
    char sp[2] = {spin[(m->frame / 3) % 4], 0};
    canvas_draw_str(c, 121, 8, sp);
    /* CRT scanline */
    canvas_set_color(c, ColorXOR);
    canvas_draw_line(c, 0, (m->frame / 2) % 64, 127, (m->frame / 2) % 64);
    canvas_set_color(c, ColorBlack);
}

static void draw_link_up(Canvas* c, const Model* m, uint32_t now) {
    uint32_t t = now - m->link_tick;
    if((t / 60) % 2 == 0 && t < 360) canvas_draw_box(c, 0, 0, 128, 64);
    canvas_set_color(c, ColorXOR);
    canvas_set_font(c, FontPrimary);
    canvas_draw_str_aligned(c, 64, 30, AlignCenter, AlignBottom, "LINK ESTABLISHED");
    canvas_set_font(c, FontSecondary);
    canvas_draw_str_aligned(c, 64, 42, AlignCenter, AlignBottom, "> loading tape");
    int w = (int)clampf(t / 6.f, 0, 100);
    canvas_draw_frame(c, 13, 48, 102, 6);
    canvas_draw_box(c, 14, 49, w, 4);
    canvas_set_color(c, ColorBlack);
}

static void draw_deck(Canvas* c, const Model* m, uint32_t now) {
    /* cassette position from the running sequence */
    int ox = CAS_X, oy = CAS_Y;
    int32_t st = (int32_t)(now - m->seq_tick);
    uint32_t t = st > 0 ? (uint32_t)st : 0;
    if(m->seq == SeqSkip || m->seq == SeqPrev) {
        if(t >= SEQ_BURST && t < SEQ_EJECT_END)
            oy -= (int)(ease_in((float)(t - SEQ_BURST) / (SEQ_EJECT_END - SEQ_BURST)) * 50);
        else if(t >= SEQ_EJECT_END)
            oy -= (int)((1 - ease_out_back((float)(t - SEQ_EJECT_END) / (SEQ_LAND - SEQ_EJECT_END))) * 50);
        if(t >= SEQ_LAND && t < SEQ_LAND + 100) oy += (m->frame & 1) ? 1 : -1; /* clunk */
    } else if(m->seq == SeqInsert) {
        oy -= (int)((1 - ease_out_back((float)t / INS_LAND)) * 50);
        if(t >= INS_LAND && t < INS_LAND + 100) oy += (m->frame & 1) ? 1 : -1;
    }
    bool glitch = m->glitch_tick && now - m->glitch_tick < 100;
    if(glitch) ox += 2;

    draw_cassette(c, m, ox, oy);
    draw_streaks(c, m);

    /* mask what slid out of the deck bay, then draw the chrome on top */
    canvas_set_color(c, ColorWhite);
    canvas_draw_box(c, 0, 0, 128, CAS_Y);
    canvas_set_color(c, ColorBlack);
    draw_hud(c, m);
    draw_panel(c, m, now);
    draw_bar(c, m);
    draw_ticker(c, m);

    if(glitch) {
        canvas_set_color(c, ColorXOR);
        canvas_draw_box(c, 0, m->glitch_y, 128, 2);
        canvas_draw_box(c, 30, m->glitch_y + 5, 70, 1);
        canvas_set_color(c, ColorBlack);
    }
}

static void draw_cb(Canvas* c, void* ctx) {
    App* app = ctx;
    furi_mutex_acquire(app->mutex, FuriWaitForever);
    const Model* m = &app->m;
    uint32_t now = now_ms();
    canvas_clear(c);
    canvas_set_color(c, ColorBlack);
    if(!m->connected)
        draw_terminal(c, m, now);
    else if(now - m->link_tick < 700)
        draw_link_up(c, m, now);
    else
        draw_deck(c, m, now);
    furi_mutex_release(app->mutex);
}

/* ------------------------------------------------------------------------ */
/* simulation                                                               */
/* ------------------------------------------------------------------------ */

static void start_seq(Model* m, Seq s, uint32_t now) {
    m->seq = s;
    m->seq_tick = now;
    m->swapped = false;
    m->seq_from_ms = m->elapsed_ms;
    m->seq_from_p = m->p;
    m->flash = NULL;
}

static void step(App* app) {
    Model* m = &app->m;
    uint32_t now = now_ms();
    float dt = m->last_ms ? (float)(now - m->last_ms) : TICK_MS;
    if(dt > 200) dt = 200;
    m->last_ms = now;
    m->frame++;

    /* target tape speed */
    float target = m->playing ? 1.f : 0.f;
    if(m->hold_ff) target = 7.f;
    if(m->hold_rew) target = -7.f;
    int32_t st = (int32_t)(now - m->seq_tick);
    uint32_t t = st > 0 ? (uint32_t)st : 0; /* a sequence may be scheduled ahead */
    switch(m->seq) {
    case SeqSkip:
        target = t < SEQ_BURST ? 11.f : 0.f;
        break;
    case SeqPrev:
        target = t < SEQ_BURST ? -11.f : 0.f;
        break;
    case SeqRestart:
        target = t < RESTART_SPIN ? -12.f : target;
        break;
    case SeqInsert:
        target = 0.f;
        break;
    default:
        break;
    }
    m->v += (target - m->v) * (fabsf(target) > fabsf(m->v) ? 0.35f : 0.2f);
    if(fabsf(m->v) < 0.01f) m->v = 0;

    /* sequences drive the counter / tape directly */
    if(m->seq == SeqSkip || m->seq == SeqPrev) {
        if(!m->swapped && t >= SEQ_EJECT_END) {
            m->swapped = true;
            if(m->seq == SeqSkip)
                m->tape_no++;
            else if(m->tape_no > 1)
                m->tape_no--;
            m->p = 0;
            m->elapsed_ms = 0;
            m->v = 0;
            m->glitch_tick = now;
            m->glitch_y = 20 + (int)(xorshift(&app->rng) % 20);
        }
        if(t >= SEQ_LAND && t - (uint32_t)dt < SEQ_LAND) notification_message(app->notif, &seq_clunk);
        if(t >= SEQ_END) m->seq = SeqNone;
    } else if(m->seq == SeqInsert) {
        if(t >= INS_LAND && t - (uint32_t)dt < INS_LAND) notification_message(app->notif, &seq_clunk);
        if(t >= INS_END) m->seq = SeqNone;
    } else if(m->seq == SeqRestart) {
        float k = ease_out((float)t / RESTART_SPIN);
        m->elapsed_ms = m->seq_from_ms * (1 - k);
        m->p = m->seq_from_p * (1 - k);
        if(t >= RESTART_END) m->seq = SeqNone;
    }

    /* tape mechanics: constant linear speed -> angular speed ~ 1/r */
    float rl = 4.f + 5.f * (1.f - m->p);
    float rr = 4.f + 5.f * m->p;
    m->ang_l += m->v * 1.3f / rl;
    m->ang_r += m->v * 1.3f / rr;
    m->bar_off += m->v * 1.2f;
    if(m->seq != SeqRestart) {
        if(m->seq == SeqNone) m->elapsed_ms += m->v * dt;
        if(m->elapsed_ms < 0) m->elapsed_ms = 0;
        m->p = clampf(m->p + m->v * dt / 240000.f, 0.f, 1.f); /* nominal 4-min side */
    }

    /* VU meters */
    for(int ch = 0; ch < 2; ch++) {
        float tg = 0;
        if(fabsf(m->v) > 0.2f && m->seq == SeqNone) {
            float f = (float)m->frame;
            tg = 0.45f + 0.25f * sinf(f * (0.23f + ch * 0.07f)) + 0.2f * sinf(f * 0.61f + ch);
            if((xorshift(&app->rng) & 15) == 0) tg = 0.95f;
            if(fabsf(m->v) > 2) tg = 0.3f + 0.15f * (float)(xorshift(&app->rng) % 100) / 100.f;
        }
        tg = clampf(tg, 0, 1);
        m->vu[ch] += (tg - m->vu[ch]) * (tg > m->vu[ch] ? 0.6f : 0.15f);
        if(m->vu[ch] > m->peak[ch])
            m->peak[ch] = m->vu[ch];
        else
            m->peak[ch] = clampf(m->peak[ch] - 0.012f, 0, 1);
    }

    /* occasional glitch */
    if(m->connected && now > m->next_glitch) {
        m->glitch_tick = now;
        m->glitch_y = 12 + (int)(xorshift(&app->rng) % 34);
        m->next_glitch = now + 3500 + xorshift(&app->rng) % 4000;
    }
}

/* ------------------------------------------------------------------------ */
/* input -> HID                                                             */
/* ------------------------------------------------------------------------ */

static void tap_key(App* app, uint16_t key) {
    if(!app->hid) return;
    ble_profile_hid_consumer_key_press(app->hid, key);
    furi_delay_ms(15);
    ble_profile_hid_consumer_key_release(app->hid, key);
}

static void flash(Model* m, const char* s, uint32_t now) {
    m->flash = s;
    m->flash_tick = now;
}

static void forget_pairings(App* app) {
    bt_disconnect(app->bt);
    furi_delay_ms(200);
    furi_hal_bt_stop_advertising();
    bt_forget_bonded_devices(app->bt);
    furi_hal_bt_start_advertising();
}

/* Returns false to exit. */
static bool handle_input(App* app, const InputEvent* e) {
    Model* m = &app->m;
    uint32_t now = now_ms();

    if(e->key == InputKeyBack) {
        if(e->type == InputTypeShort) return false;
        if(e->type == InputTypeLong) {
            forget_pairings(app);
            m->wipe_tick = now;
            m->boot_tick = now;
            notification_message(app->notif, &seq_clunk);
        }
        return true;
    }
    if(!m->connected) return true;

    switch(e->key) {
    case InputKeyOk:
        if(e->type == InputTypeShort) {
            tap_key(app, HID_CONSUMER_PLAY_PAUSE);
            m->playing = !m->playing;
            flash(m, m->playing ? "> PLAY" : "|| PAUSE", now);
            notification_message(app->notif, &seq_tap);
        }
        break;

    case InputKeyRight:
        if(e->type == InputTypeShort) {
            tap_key(app, HID_CONSUMER_SCAN_NEXT_TRACK);
            start_seq(m, SeqSkip, now);
            notification_message(app->notif, &seq_tap);
        } else if(e->type == InputTypeLong) {
            ble_profile_hid_consumer_key_press(app->hid, HID_CONSUMER_FAST_FORWARD);
            m->hold_ff = true;
        } else if(e->type == InputTypeRelease && m->hold_ff) {
            ble_profile_hid_consumer_key_release(app->hid, HID_CONSUMER_FAST_FORWARD);
            m->hold_ff = false;
        }
        break;

    case InputKeyLeft:
        if(e->type == InputTypeShort) {
            tap_key(app, HID_CONSUMER_SCAN_PREVIOUS_TRACK);
            /* iOS restarts the song if it's >3 s in, otherwise goes back */
            start_seq(m, m->elapsed_ms > 3000 ? SeqRestart : SeqPrev, now);
            notification_message(app->notif, &seq_tap);
        } else if(e->type == InputTypeLong) {
            ble_profile_hid_consumer_key_press(app->hid, HID_CONSUMER_REWIND);
            m->hold_rew = true;
        } else if(e->type == InputTypeRelease && m->hold_rew) {
            ble_profile_hid_consumer_key_release(app->hid, HID_CONSUMER_REWIND);
            m->hold_rew = false;
        }
        break;

    case InputKeyUp:
    case InputKeyDown:
        if(e->type == InputTypePress || e->type == InputTypeRepeat) {
            bool up = e->key == InputKeyUp;
            tap_key(app, up ? HID_CONSUMER_VOLUME_INCREMENT : HID_CONSUMER_VOLUME_DECREMENT);
            m->vol_dir = up ? 1 : -1;
            m->vol_tick = now;
            if(e->type == InputTypePress) notification_message(app->notif, &seq_tap);
        }
        break;

    default:
        break;
    }
    return true;
}

static void connection_step(App* app) {
    Model* m = &app->m;
    uint32_t now = now_ms();
    bool connected = app->bt_status == BtStatusConnected;
    if(connected && !app->was_connected) {
        m->connected = true;
        m->link_tick = now;
        m->playing = true; /* most people connect with music already going */
        start_seq(m, SeqInsert, now + 700);
        m->next_glitch = now + 4000;
        notification_message(app->notif, &sequence_blink_blue_100);
    } else if(!connected && app->was_connected) {
        m->connected = false;
        m->boot_tick = now;
        m->hold_ff = m->hold_rew = false;
        m->seq = SeqNone;
    }
    app->was_connected = connected;
}

/* ------------------------------------------------------------------------ */
/* lifecycle                                                                */
/* ------------------------------------------------------------------------ */

static void bt_status_cb(BtStatus status, void* ctx) {
    App* app = ctx;
    app->bt_status = status;
}

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
    app->rng = furi_hal_random_get() | 1;
    app->m.tape_no = 1;
    app->m.boot_tick = now_ms();

    app->queue = furi_message_queue_alloc(16, sizeof(Event));
    app->mutex = furi_mutex_alloc(FuriMutexTypeNormal);
    app->view_port = view_port_alloc();
    view_port_draw_callback_set(app->view_port, draw_cb, app);
    view_port_input_callback_set(app->view_port, input_cb, app);
    app->gui = furi_record_open(RECORD_GUI);
    gui_add_view_port(app->gui, app->view_port, GuiLayerFullscreen);
    app->notif = furi_record_open(RECORD_NOTIFICATION);

    /* Bluetooth: HID profile with its own bonding store */
    app->bt = furi_record_open(RECORD_BT);
    bt_disconnect(app->bt);
    furi_delay_ms(200);
    bt_keys_storage_set_storage_path(app->bt, KEYS_PATH);
    static BleProfileHidParams params = {.device_name_prefix = "Tape", .mac_xor = 0x7A9E};
    app->hid = bt_profile_start(app->bt, ble_profile_hid, &params);
    if(!app->hid) FURI_LOG_E(TAG, "failed to start HID profile");
    furi_hal_bt_start_advertising();
    bt_set_status_changed_callback(app->bt, bt_status_cb, app);

    app->timer = furi_timer_alloc(timer_cb, FuriTimerTypePeriodic, app);
    furi_timer_start(app->timer, furi_ms_to_ticks(TICK_MS));

    Event ev;
    bool running = true;
    while(running) {
        if(furi_message_queue_get(app->queue, &ev, FuriWaitForever) != FuriStatusOk) continue;
        furi_mutex_acquire(app->mutex, FuriWaitForever);
        if(ev.type == EvInput)
            running = handle_input(app, &ev.input);
        else {
            connection_step(app);
            step(app);
        }
        furi_mutex_release(app->mutex);
        view_port_update(app->view_port);
    }

    furi_timer_stop(app->timer);
    furi_timer_free(app->timer);

    bt_set_status_changed_callback(app->bt, NULL, NULL);
    if(app->hid) ble_profile_hid_consumer_key_release_all(app->hid);
    bt_disconnect(app->bt);
    furi_delay_ms(200);
    bt_keys_storage_set_default_path(app->bt);
    bt_profile_restore_default(app->bt);
    furi_record_close(RECORD_BT);

    gui_remove_view_port(app->gui, app->view_port);
    view_port_free(app->view_port);
    furi_record_close(RECORD_GUI);
    furi_record_close(RECORD_NOTIFICATION);
    furi_mutex_free(app->mutex);
    furi_message_queue_free(app->queue);
    free(app);
    return 0;
}
