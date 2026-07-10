# Cyclops firmware OTA update path (XIAO ESP32-S3)

Over-the-air firmware updates ride the **existing BLE frame protocol** — no new
GATT characteristic, no separate transport. The phone streams a new image over
the same NOTE characteristic the device already uses; the device writes it to the
inactive OTA partition and reboots into it.

## Wire protocol

Four new `MsgType`s (see `lib/cyclops_shared/include/cyclops_shared.h`):

| type | dir | payload |
|------|-----|---------|
| `MSG_OTA_BEGIN` (21) | phone→device | `[size:u32-le][crc32:u32-le][chunk:u32-le]` |
| `MSG_OTA_CHUNK` (22) | phone→device | `[seq:u32-le][data...]` (seq strictly sequential from 0) |
| `MSG_OTA_END`   (23) | phone→device | empty (request finalize + verify) |
| `MSG_OTA_ACK`   (24) | device→phone | `{"seq":n,"st":code}` flow-control + result |

`crc32` is IEEE 802.3 (zlib/`java.util.zip.CRC32`), finalized. ACK `st` codes
match `cyclops::OtaStatus` (0=OK, 6=CRC_MISMATCH, …).

## Components

- **`lib/cyclops_shared/include/ota.h`** — `OtaReceiver` state machine +
  `crc32_ieee`. Host-testable: flash writes go through an injected `OtaSink`
  (esp_ota on device, buffer in tests). Validates sequencing, size, and CRC32
  before committing; aborts on any failure.
- **`xiao/src/main.cpp`** — wires `OtaSink` to `esp_ota_begin/write/end` +
  `esp_ota_set_boot_partition`, routes `MSG_OTA_*` through the frame decoder,
  ACKs every frame, and `esp_restart()`s on a verified `MSG_OTA_END`.
- **`android/.../core/OtaSender.kt`** — phone side: `frames(image, chunkSize)`
  produces the ordered BEGIN/CHUNK/END frame list; `parseAck()` reads results.

## Tests

- `make ota` — 10 host tests (happy path, busy/bad-state/bad-seq/overflow/
  size/crc/flash-err rejects, ACK json, CRC32 check value). No toolchain needed.
- `android :core:test` — `OtaSenderTest` reassembles the image from the frame
  list and re-verifies size+CRC32, plus CRC32 canonical check value.

## Update flow (phone)

1. `OtaSender.frames(imageBytes, chunkSize=240)` → list of encoded frames.
2. Write frame 0 (BEGIN); wait for `MSG_OTA_ACK` with `st==OTA_OK`.
3. For each CHUNK: write, wait for ACK `st==OTA_OK` (ACK `seq` echoes the chunk).
4. Write END; ACK `st==OTA_OK` means image verified + committed — device reboots.
   Any non-OK status aborts the session (device discards the partial image).

## Partition note

Requires a dual-app OTA partition table (`ota_0`/`ota_1` + `otadata`). Set in
`platformio.ini` per-env with `board_build.partitions = default_ota.csv` (or a
custom CSV sized for the app) before shipping OTA to hardware.
