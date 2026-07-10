# Cyclops — Wire Protocol (v1 + v2)

> **RECONSTRUCTED DOC** — original `docs/04-protocol.md` (2026-06-15) lost on
> corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `protocol/protocol.md`, `protocol/protocol_v2.md`, `device/src/v2/protocol_v2.cpp`,
> `brain/protocol.py`, `brain/protocol_v2.py`, `firmware/xiao/src/main.cpp`.
> This doc consolidates v1 (device↔brain serial) and v2 (multi-peer BLE).
> **[inferred]** = reconstructed where the source was ambiguous.

## 0. Two layers

- **v1** — length-delimited frames over a reliable byte stream (USB-CDC Serial /
  UART). The original MVP contract.
- **v2** — superset adding peer addressing, UTC time-sync, ring health samples,
  typed HUD frames for G2, and a versioned HELLO so mismatched peers are
  rejected early. v1 message types 1–10 remain valid.

## 1. v1 Framing

```
[0xAA][0x55][len:u16le][type:u8][payload:len bytes][crc16:u16le]
```

- Magic `0xAA 0x55`. `len` = payload bytes (0..1024), excludes header + crc.
- `crc16` = CCITT-FALSE over (`type` + `payload`).
- CRC fail → frame dropped. Retransmit on NAK (not required for MVP).
- Trivially parsable on a tiny MCU (the `FrameDecoder` in `firmware/shared`).

### v1 message types

| id | name | dir | payload |
|----|------|-----|----------|
| 1 | HELLO | device→brain | `{"v":1,"hw":"xiao-s3-sense","caps":[...]}` |
| 2 | HEARTBEAT | both | `{"t":<ms>}` |
| 3 | INPUT_EVENT | device→brain | `{"src":"wheel\|btn_a\|btn_b\|gyro","v":<int>,"ev":..}` |
| 4 | AUDIO_META | device→brain | `{"rate":16000,"ch":1,"codec":"pcm16"}` |
| 5 | AUDIO_CHUNK | device→brain | raw int16 frames (**binary**, not JSON) |
| 6 | DISPLAY_CMD | brain→device | `{"kind":"text\|icon\|clear\|scroll\|tone","data":...}` |
| 7 | NOTE | brain→device | `{"id","type":"task\|idea\|decision\|reminder\|summary","text"}` |
| 8 | STATUS | device→brain | `{"batt":<mv>,"charging":<0\|1>,"gyro":[x,y,z]}` |
| 9 | CMD | brain→device | `{"op":"start_record\|stop_record\|set_led\|sleep"}` |
| 10 | ACK | both | `{"ok":1,"type":<echoed type>}` |

`AUDIO_CHUNK` bypasses JSON (binary payload) for throughput; the type id
distinguishes it. `DISPLAY_CMD` and `NOTE` are JSON.

### v1 caps strings

`mic`, `screen`, `gyro`, `wheel`, `btn`, `ble`, `battery`, `vibration`.

## 2. v2 additions (multi-peer BLE)

Framing unchanged; over BLE one frame == one GATT write/notification
(MTU ~23–247 B; keep payloads small — premortem #1).

Peers: `bead | glasses | ring | phone | brain`.

| id | name | dir | payload |
|----|------|-----|----------|
| 11 | PEER_HELLO | any→phone | `{"v":2,"peer":"bead","caps":[...],"fw":"0.1"}` |
| 12 | TIME_SYNC | phone→any | `{"t":<utc_ms>,"acc":<ms>}` |
| 13 | HEALTH_SAMPLE | ring→phone | `{"t":<utc_ms>,"hr","spo2","sleep","batt":<mv>}` |
| 14 | HUD_FRAME | phone→glasses | `{"kind":"note\|notify\|teleprompter\|clear","lines":[...],"more":<0\|1>}` |
| 15 | RING_GESTURE | ring→phone | `{"g":"tap\|double\|long\|swipe","t":<utc_ms>}` |
| 16 | AUDIO_COMPRESSED | bead→phone | binary `[codec:u8][seq:u16le][opus/adpcm]` |
| 17 | CONFIRM | phone→brain/glasses | `{"id":<note_id>,"ok":<0\|1>}` |
| 18 | PEER_STATUS | any→phone | `{"peer":..,"batt":<mv>,"link":<0\|1>}` |

### v2 HUD_FRAME rules (premortem #4)
- `lines` max 4 strings, each ≤ 18 chars (G2 ~640×200).
- `teleprompter`: phone streams one line at a time; glasses auto-scroll slow.
- Never send raw transcript — only extracted/summarized text.
- On-device decode is a tiny state machine (`device/src/v2/protocol_v2.cpp`):
  `K<kind>\nL<line0>\nL<line1>... M<more>\n` — no JSON parser on the MCU.

### v2 time sync (premortem #3)
Phone owns UTC. On connect it sends `TIME_SYNC`; peers store the offset and
stamp samples. The brain joins `HEALTH_SAMPLE` to notes by `[t-window, t+window]`.
The ring has no RTC, so the phone pushes time sync on connect.

### v2 codec negotiation
`PEER_HELLO` carries `caps`; the audio codec is chosen by the phone from
`bead caps ∩ phone support` (premortem #2: classic BLE can't carry 16 kHz PCM
reliably — bead buffers + compresses Opus/ADPCM, streams MTU-sized chunks; the
brain tolerates gaps; do NOT promise real-time on classic BLE).

## 3. Source-of-truth / verification

- Single schema: `protocol/protocol.md` (v1) + `protocol/protocol_v2.md` (v2).
- Mirrors: `firmware/shared` (`FrameDecoder`, CRC), `device/src/v2/protocol_v2.*`
  (C++ build/parse), `brain/protocol.py` + `brain/protocol_v2.py` (Python),
  `android/core/.../RingProto.kt` (Kotlin, CI `:core:test`).
- Lenient parsers ignore unknown keys; `PEER_HELLO` carries a `v` field.
- CI test round-trips every message type (`tests/test_wire_contract.py`,
  `tests/test_v2.py`, `tests/test_colmi_r02.py`).

---
**[inferred]** v1 framing + type tables are verbatim from `protocol/protocol.md`
(accurate). v2 tables are from `protocol_v2.md` (accurate). The `K/L/M`
decode format and the "no JSON parser on MCU" note are from the committed
`protocol_v2.cpp` (accurate). Inferred only: the doc's framing as a single
"v1 + v2 consolidated" narrative — the original may have separated them.
