# Cyclops Wire Protocol (device <-> brain)

All messages are length-delimited frames over a reliable byte stream (USB-CDC
Serial / UART). Designed to be trivially parsable on a tiny MCU.

## Framing
```
[0xAA] [0x55] [len:uint16 LE] [type:uint8] [payload:len bytes] [crc16:uint16 LE]
```
- Magic: 0xAA 0x55
- len: payload length (0..1024), excludes header+crc
- crc16: CCITT-FALSE over (type + payload)
- If a frame fails CRC it is dropped; device retransmits on NAK (not required for MVP).

## Message types (type:uint8)
| id | name            | direction     | payload (json-utf8 text)                         |
|----|-----------------|----------------|--------------------------------------------------|
| 1  | HELLO           | device->brain | {"v":1,"hw":"xiao-s3-sense","caps":[...]}        |
| 2  | HEARTBEAT       | both          | {"t":<ms>}                                       |
| 3  | INPUT_EVENT     | device->brain | {"src":"wheel|btn_a|btn_b|gyro","v":<int>,"ev":..}|
| 4  | AUDIO_META      | device->brain | {"rate":16000,"ch":1,"codec":"pcm16"}            |
| 5  | AUDIO_CHUNK     | device->brain | raw int16 frames (binary, not json)              |
| 6  | DISPLAY_CMD     | brain->device | {"kind":"text|icon|clear|scroll|tone","data":...} |
| 7  | NOTE            | brain->device | {"id","type":"task|idea|decision|reminder|summary","text"} |
| 8  | STATUS          | device->brain | {"batt":<mv>,"charging":<0|1>,"gyro":[x,y,z]}    |
| 9  | CMD             | brain->device | {"op":"start_record|stop_record|set_led|sleep"}  |
| 10 | ACK             | both          | {"ok":1,"type":<echoed type>}                    |

Note: AUDIO_CHUNK bypasses JSON (binary payload) for throughput; type id is
used to distinguish. DISPLAY_CMD and NOTE are JSON.

## Caps strings
"mic","screen","gyro","wheel","btn","ble","battery","vibration"
