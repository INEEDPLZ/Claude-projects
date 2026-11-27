#pragma once
#include "../preview_stubs.h"
typedef enum { SerialServiceEventTypeDataReceived, SerialServiceEventTypeDataSent } SerialServiceEventType;
typedef struct { uint8_t* buffer; uint16_t size; } SerialServiceData;
typedef struct { SerialServiceEventType event; SerialServiceData data; } SerialServiceEvent;
typedef uint16_t (*FuriHalBtSerialCallback)(SerialServiceEvent, void*);
extern const FuriHalBleProfileTemplate* const ble_profile_serial;
bool ble_profile_serial_tx(FuriHalBleProfileBase*, uint8_t*, uint16_t);
void ble_profile_serial_set_rpc_active(FuriHalBleProfileBase*, bool);
void ble_profile_serial_set_event_callback(FuriHalBleProfileBase*, uint16_t, FuriHalBtSerialCallback, void*);
