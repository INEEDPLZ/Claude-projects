/* Desktop preview harness: compiles the real FlipTune drawing + protocol code
 * against a fake 128x64 canvas and replays a scripted session.
 *   stdin : script lines  "C <ms> <0|1>" | "I <ms> <key> <type>" | "E <ms>"
 *   stdout: one 8192-byte frame (0/1 per pixel) every 33 ms                        */
#include <stdio.h>
#include "fonts.h"
#include "stubs/gui/gui.h"
#include "stubs/notification/notification_messages.h"
#include "stubs/bt/bt_service/bt.h"
#include "stubs/extra_profiles/hid_profile.h"

struct Canvas {
    uint8_t px[64][128];
    int color;
    int font;
};

static uint32_t g_now;
uint32_t furi_get_tick(void) { return g_now; }

static void pset(Canvas* c, int x, int y) {
    if(x < 0 || y < 0 || x >= 128 || y >= 64) return;
    if(c->color == 0) c->px[y][x] = 0;
    else if(c->color == 1) c->px[y][x] = 1;
    else c->px[y][x] ^= 1;
}
void canvas_clear(Canvas* c) { memset(c->px, 0, sizeof(c->px)); }
void canvas_set_color(Canvas* c, Color col) { c->color = col; }
void canvas_set_font(Canvas* c, Font f) { c->font = f; }
static const PGlyph* fnt(Canvas* c) { return c->font == FontPrimary ? font_primary : font_secondary; }
static int fnt_ascent(Canvas* c) { return c->font == FontPrimary ? font_primary_ascent : font_secondary_ascent; }
uint16_t canvas_string_width(Canvas* c, const char* s) {
    int w = 0;
    for(; *s; s++) w += fnt(c)[(uint8_t)*s & 127].dx;
    return w;
}
void canvas_draw_str(Canvas* c, int32_t x, int32_t y, const char* s) {
    for(; *s; s++) {
        const PGlyph* g = &fnt(c)[(uint8_t)*s & 127];
        for(int r = 0; r < g->h && r < 16; r++)
            for(int col = 0; col < g->w; col++)
                if(g->rows[r] & (0x8000 >> col)) pset(c, x + g->x + col, y - (g->h + g->y) + r);
        x += g->dx;
    }
}
void canvas_draw_str_aligned(Canvas* c, int32_t x, int32_t y, Align h, Align v, const char* s) {
    int w = canvas_string_width(c, s);
    if(h == AlignRight) x -= w;
    if(h == AlignCenter) x -= w / 2;
    if(v == AlignTop) y += fnt_ascent(c);
    if(v == AlignCenter) y += fnt_ascent(c) / 2;
    canvas_draw_str(c, x, y, s);
}
void canvas_draw_dot(Canvas* c, int32_t x, int32_t y) { pset(c, x, y); }
void canvas_draw_box(Canvas* c, int32_t x, int32_t y, size_t w, size_t h) {
    for(size_t j = 0; j < h; j++) for(size_t i = 0; i < w; i++) pset(c, x + i, y + j);
}
void canvas_draw_line(Canvas* c, int32_t x0, int32_t y0, int32_t x1, int32_t y1) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1, dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1, e = dx + dy;
    for(;;) {
        pset(c, x0, y0);
        if(x0 == x1 && y0 == y1) break;
        int e2 = 2 * e;
        if(e2 >= dy) { e += dy; x0 += sx; }
        if(e2 <= dx) { e += dx; y0 += sy; }
    }
}
void canvas_draw_frame(Canvas* c, int32_t x, int32_t y, size_t w, size_t h) {
    canvas_draw_line(c, x, y, x + w - 1, y);
    canvas_draw_line(c, x, y + h - 1, x + w - 1, y + h - 1);
    for(size_t j = 1; j + 1 < h; j++) { pset(c, x, y + j); pset(c, x + w - 1, y + j); }
}
static void circ(Canvas* c, int cx, int cy, int r, bool fill) {
    static uint8_t seen[64][128];
    memset(seen, 0, sizeof(seen));
    for(int y = -r; y <= r; y++) for(int x = -r; x <= r; x++) {
        int d = x * x + y * y;
        bool in = fill ? d <= r * r + r : (d <= r * r + r && d >= r * r - r);
        int px = cx + x, py = cy + y;
        if(in && px >= 0 && py >= 0 && px < 128 && py < 64 && !seen[py][px]) { seen[py][px] = 1; pset(c, px, py); }
    }
}
void canvas_draw_circle(Canvas* c, int32_t x, int32_t y, size_t r) { circ(c, x, y, r, false); }
void canvas_draw_disc(Canvas* c, int32_t x, int32_t y, size_t r) { circ(c, x, y, r, true); }
void canvas_draw_rbox(Canvas* c, int32_t x, int32_t y, size_t w, size_t h, size_t r) {
    for(size_t j = 0; j < h; j++) for(size_t i = 0; i < w; i++) {
        bool corner = (i < r || i >= w - r) && (j < r || j >= h - r);
        if(corner) {
            int cx = i < r ? r : w - 1 - r, cy = j < r ? r : h - 1 - r;
            int dx = i - cx, dy = j - cy;
            if(dx * dx + dy * dy > (int)(r * r + r)) continue;
        }
        pset(c, x + i, y + j);
    }
}
void canvas_draw_rframe(Canvas* c, int32_t x, int32_t y, size_t w, size_t h, size_t r) {
    canvas_draw_line(c, x + r, y, x + w - 1 - r, y);
    canvas_draw_line(c, x + r, y + h - 1, x + w - 1 - r, y + h - 1);
    canvas_draw_line(c, x, y + r, x, y + h - 1 - r);
    canvas_draw_line(c, x + w - 1, y + r, x + w - 1, y + h - 1 - r);
    if(r) { pset(c, x + 1, y + 1); pset(c, x + w - 2, y + 1); pset(c, x + 1, y + h - 2); pset(c, x + w - 2, y + h - 2); }
}

/* ---- unused SDK pieces the app links against ---- */
const NotificationMessage message_vibro_on, message_vibro_off, message_delay_10, message_delay_25;
const NotificationSequence sequence_blink_blue_100 = {NULL};
const FuriHalBleProfileTemplate* ble_profile_hid = NULL;
void notification_message(NotificationApp* n, const NotificationSequence* s) { (void)n; (void)s; }
FuriHalBleProfileBase* bt_profile_start(Bt* b, const FuriHalBleProfileTemplate* t, void* p) { (void)b; (void)t; (void)p; return NULL; }
bool bt_profile_restore_default(Bt* b) { (void)b; return true; }
void bt_disconnect(Bt* b) { (void)b; }
void bt_set_status_changed_callback(Bt* b, BtStatusChangedCallback cb, void* x) { (void)b; (void)cb; (void)x; }
void bt_forget_bonded_devices(Bt* b) { (void)b; }
void bt_keys_storage_set_storage_path(Bt* b, const char* p) { (void)b; (void)p; }
void bt_keys_storage_set_default_path(Bt* b) { (void)b; }
bool ble_profile_hid_consumer_key_press(FuriHalBleProfileBase* p, uint16_t k) { (void)p; fprintf(stderr, "[%5u ms] HID press 0x%02X\n", g_now, k); return true; }
bool ble_profile_hid_consumer_key_release(FuriHalBleProfileBase* p, uint16_t k) { (void)p; (void)k; return true; }
bool ble_profile_hid_consumer_key_release_all(FuriHalBleProfileBase* p) { (void)p; return true; }
FuriMessageQueue* furi_message_queue_alloc(uint32_t a, uint32_t b) { (void)a; (void)b; return NULL; }
void furi_message_queue_free(FuriMessageQueue* q) { (void)q; }
FuriStatus furi_message_queue_put(FuriMessageQueue* q, const void* m, uint32_t t) { (void)q; (void)m; (void)t; return FuriStatusOk; }
FuriStatus furi_message_queue_get(FuriMessageQueue* q, void* m, uint32_t t) { (void)q; (void)m; (void)t; return FuriStatusError; }
FuriTimer* furi_timer_alloc(FuriTimerCallback cb, FuriTimerType t, void* x) { (void)cb; (void)t; (void)x; return NULL; }
void furi_timer_free(FuriTimer* t) { (void)t; }
FuriStatus furi_timer_start(FuriTimer* t, uint32_t p) { (void)t; (void)p; return FuriStatusOk; }
FuriStatus furi_timer_stop(FuriTimer* t) { (void)t; return FuriStatusOk; }
FuriStreamBuffer* furi_stream_buffer_alloc(size_t a, size_t b) { (void)a; (void)b; return NULL; }
void furi_stream_buffer_free(FuriStreamBuffer* s) { (void)s; }
size_t furi_stream_buffer_send(FuriStreamBuffer* s, const void* d, size_t n, uint32_t t) { (void)s; (void)d; (void)t; return n; }
size_t furi_stream_buffer_receive(FuriStreamBuffer* s, void* d, size_t n, uint32_t t) { (void)s; (void)d; (void)n; (void)t; return 0; }
size_t furi_stream_buffer_spaces_available(FuriStreamBuffer* s) { (void)s; return 1024; }
ViewPort* view_port_alloc(void) { return NULL; }
void view_port_free(ViewPort* v) { (void)v; }
void view_port_draw_callback_set(ViewPort* v, ViewPortDrawCallback cb, void* x) { (void)v; (void)cb; (void)x; }
void view_port_input_callback_set(ViewPort* v, ViewPortInputCallback cb, void* x) { (void)v; (void)cb; (void)x; }
void view_port_update(ViewPort* v) { (void)v; }
void gui_add_view_port(Gui* g, ViewPort* v, GuiLayer l) { (void)g; (void)v; (void)l; }
void gui_remove_view_port(Gui* g, ViewPort* v) { (void)g; (void)v; }
void* furi_record_open(const char* n) { (void)n; return NULL; }
void furi_record_close(const char* n) { (void)n; }

#include "../../flipper_app/fliptune.c"

int main(void) {
    static App app;
    static Canvas canvas;
    memset(&app, 0, sizeof(app));
    app.rng = 0x1234567;
    app.hid = (FuriHalBleProfileBase*)&app;
    app.m.tape_no = 1;
    app.bt_status = BtStatusAdvertising;

    char line[8192];
    char kind = 0;
    uint32_t at = 0;
    char rest[8000];
    bool have = false, end = false;
    for(g_now = 0; !end; g_now += TICK_MS) {
        for(;;) {
            if(!have) {
                if(!fgets(line, sizeof(line), stdin)) { end = true; break; }
                rest[0] = 0;
                if(sscanf(line, " %c %u %7999[^\n]", &kind, &at, rest) < 2) continue;
                have = true;
            }
            if(at > g_now) break;
            have = false;
            if(kind == 'E') { end = true; break; }
            if(kind == 'C') app.bt_status = atoi(rest) ? BtStatusConnected : BtStatusAdvertising;
            if(kind == 'I') {
                int k, t;
                sscanf(rest, "%d %d", &k, &t);
                InputEvent e = {.key = k, .type = t};
                handle_input(&app, &e);
            }
        }
        connection_step(&app);
        step(&app);
        draw_cb(&canvas, &app);
        fwrite(canvas.px, 1, sizeof(canvas.px), stdout);
    }
    return 0;
}
