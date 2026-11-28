#pragma once
#include "../preview_stubs.h"
typedef struct { const char* device_name_prefix; uint16_t mac_xor; } BleProfileHidParams;
extern const FuriHalBleProfileTemplate* ble_profile_hid;
bool ble_profile_hid_consumer_key_press(FuriHalBleProfileBase*, uint16_t);
bool ble_profile_hid_consumer_key_release(FuriHalBleProfileBase*, uint16_t);
bool ble_profile_hid_consumer_key_release_all(FuriHalBleProfileBase*);
