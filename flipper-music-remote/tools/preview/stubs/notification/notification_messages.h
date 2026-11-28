#pragma once
#include "../preview_stubs.h"
#define RECORD_NOTIFICATION "notification"
extern const NotificationMessage message_vibro_on, message_vibro_off, message_delay_10, message_delay_25;
extern const NotificationSequence sequence_blink_blue_100;
void notification_message(NotificationApp*, const NotificationSequence*);
