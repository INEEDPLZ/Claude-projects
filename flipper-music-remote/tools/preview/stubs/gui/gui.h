#pragma once
#include "../preview_stubs.h"
#include "../input/input.h"
typedef struct Canvas Canvas;
typedef enum { ColorWhite, ColorBlack, ColorXOR } Color;
typedef enum { FontPrimary, FontSecondary, FontKeyboard, FontBigNumbers } Font;
typedef enum { AlignLeft, AlignRight, AlignTop, AlignBottom, AlignCenter } Align;
typedef enum { GuiLayerFullscreen = 3 } GuiLayer;
#define RECORD_GUI "gui"
typedef void (*ViewPortDrawCallback)(Canvas*, void*);
typedef void (*ViewPortInputCallback)(InputEvent*, void*);
void canvas_clear(Canvas*);
void canvas_set_color(Canvas*, Color);
void canvas_set_font(Canvas*, Font);
void canvas_draw_str(Canvas*, int32_t, int32_t, const char*);
void canvas_draw_str_aligned(Canvas*, int32_t, int32_t, Align, Align, const char*);
uint16_t canvas_string_width(Canvas*, const char*);
void canvas_draw_dot(Canvas*, int32_t, int32_t);
void canvas_draw_box(Canvas*, int32_t, int32_t, size_t, size_t);
void canvas_draw_frame(Canvas*, int32_t, int32_t, size_t, size_t);
void canvas_draw_line(Canvas*, int32_t, int32_t, int32_t, int32_t);
void canvas_draw_circle(Canvas*, int32_t, int32_t, size_t);
void canvas_draw_disc(Canvas*, int32_t, int32_t, size_t);
void canvas_draw_rframe(Canvas*, int32_t, int32_t, size_t, size_t, size_t);
void canvas_draw_rbox(Canvas*, int32_t, int32_t, size_t, size_t, size_t);
ViewPort* view_port_alloc(void);
void view_port_free(ViewPort*);
void view_port_draw_callback_set(ViewPort*, ViewPortDrawCallback, void*);
void view_port_input_callback_set(ViewPort*, ViewPortInputCallback, void*);
void view_port_update(ViewPort*);
void gui_add_view_port(Gui*, ViewPort*, GuiLayer);
void gui_remove_view_port(Gui*, ViewPort*);
void* furi_record_open(const char*);
void furi_record_close(const char*);
