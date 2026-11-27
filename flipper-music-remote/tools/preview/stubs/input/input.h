#pragma once
typedef enum { InputKeyUp, InputKeyDown, InputKeyRight, InputKeyLeft, InputKeyOk, InputKeyBack } InputKey;
typedef enum { InputTypePress, InputTypeRelease, InputTypeShort, InputTypeLong, InputTypeRepeat } InputType;
typedef struct { unsigned sequence; InputKey key; InputType type; } InputEvent;
