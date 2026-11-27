/* Minimal stand-ins for the Flipper SDK so fliptune.c builds on a desktop. */
#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define UNUSED(x) (void)(x)
#define FURI_LOG_W(...) ((void)0)
#define FURI_LOG_E(...) ((void)0)
#define FuriWaitForever 0xFFFFFFFFu
typedef enum { FuriStatusOk = 0, FuriStatusError = -1 } FuriStatus;
typedef enum { FuriMutexTypeNormal } FuriMutexType;
typedef enum { FuriTimerTypePeriodic } FuriTimerType;
typedef struct FuriMessageQueue FuriMessageQueue;
typedef struct FuriMutex FuriMutex;
typedef struct FuriTimer FuriTimer;
typedef struct FuriStreamBuffer FuriStreamBuffer;
typedef struct Gui Gui;
typedef struct ViewPort ViewPort;
typedef struct NotificationApp NotificationApp;
typedef struct Bt Bt;
typedef struct FuriHalBleProfileBase FuriHalBleProfileBase;
typedef struct FuriHalBleProfileTemplate FuriHalBleProfileTemplate;
typedef void* NotificationMessage;
typedef const void* NotificationSequence[];
typedef void (*FuriTimerCallback)(void*);

uint32_t furi_get_tick(void);
static inline uint32_t furi_kernel_get_tick_frequency(void) { return 1000; }
static inline uint32_t furi_ms_to_ticks(uint32_t ms) { return ms; }
static inline void furi_delay_ms(uint32_t ms) { (void)ms; }
static inline uint32_t furi_hal_random_get(void) { return 0x12345678; }
static inline void furi_hal_bt_start_advertising(void) {}
static inline const char* furi_hal_version_get_name_ptr(void) { return "Zorp"; }
FuriMessageQueue* furi_message_queue_alloc(uint32_t, uint32_t);
void furi_message_queue_free(FuriMessageQueue*);
FuriStatus furi_message_queue_put(FuriMessageQueue*, const void*, uint32_t);
FuriStatus furi_message_queue_get(FuriMessageQueue*, void*, uint32_t);
static inline FuriMutex* furi_mutex_alloc(FuriMutexType t) { (void)t; return (FuriMutex*)1; }
static inline void furi_mutex_free(FuriMutex* m) { (void)m; }
static inline FuriStatus furi_mutex_acquire(FuriMutex* m, uint32_t t) { (void)m; (void)t; return FuriStatusOk; }
static inline FuriStatus furi_mutex_release(FuriMutex* m) { (void)m; return FuriStatusOk; }
FuriTimer* furi_timer_alloc(FuriTimerCallback, FuriTimerType, void*);
void furi_timer_free(FuriTimer*);
FuriStatus furi_timer_start(FuriTimer*, uint32_t);
FuriStatus furi_timer_stop(FuriTimer*);
FuriStreamBuffer* furi_stream_buffer_alloc(size_t, size_t);
void furi_stream_buffer_free(FuriStreamBuffer*);
size_t furi_stream_buffer_send(FuriStreamBuffer*, const void*, size_t, uint32_t);
size_t furi_stream_buffer_receive(FuriStreamBuffer*, void*, size_t, uint32_t);
size_t furi_stream_buffer_spaces_available(FuriStreamBuffer*);
