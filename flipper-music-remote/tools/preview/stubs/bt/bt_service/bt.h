#pragma once
#include "../../preview_stubs.h"
#define RECORD_BT "bt"
typedef enum { BtStatusUnavailable, BtStatusOff, BtStatusAdvertising, BtStatusConnected } BtStatus;
typedef void (*BtStatusChangedCallback)(BtStatus, void*);
FuriHalBleProfileBase* bt_profile_start(Bt*, const FuriHalBleProfileTemplate*, void*);
bool bt_profile_restore_default(Bt*);
void bt_disconnect(Bt*);
void bt_set_status_changed_callback(Bt*, BtStatusChangedCallback, void*);
void bt_forget_bonded_devices(Bt*);
void bt_keys_storage_set_storage_path(Bt*, const char*);
void bt_keys_storage_set_default_path(Bt*);
