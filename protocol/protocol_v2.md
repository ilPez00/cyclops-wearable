# Cyclops Protocol v2

Superset of protocol v1 (see protocol.md). Adds: peer addressing, UTC time-sync
(from phone), ring health samples, typed HUD frames for G2, and a versioned HELLO
so mismatched peers are rejected early.

## Framing (unchanged from v1)
`[AA][55][len:u16le][type:u8][payload][crc16:u16le]` over a reliable byte stream.
Over BLE, one frame == one GATT write/notification (MTU ~23–247B; keep payloads small).

## Peers
`peer`: "bead" | "glasses" | "ring" | "phone" | "brain"

## Message types (additions to v1)
| id | name            | dir                  | payload |
|----|-----------------|----------------------|---------|
| 11 | PEER_HELLO      | any->phone           | {"v":2,"peer":"bead","caps":[...],"fw":"0.1"} |
| 12 | TIME_SYNC       | phone->any           | {"t":<utc_ms>,"acc":<ms>} |
| 13 | HEALTH_SAMPLE   | ring->phone          | {"t":<utc_ms>,"hr":<bpm>,"spo2":<pct>,"sleep":<stage>,"batt":<mv>} |
| 14 | HUD_FRAME       | phone->glasses       | {"kind":"note|notify|teleprompter|clear","lines":[...],"more":<0|1>} |
| 15 | RING_GESTURE    | ring->phone          | {"g":"tap|double|long|swipe","t":<utc_ms>} |
| 16 | AUDIO_COMPRESSED| bead->phone          | binary: [codec:u8][seq:u16le][opus/adpcm bytes] |
| 17 | CONFIRM         | phone->brain/glasses | {"id":<note_id>,"ok":<0|1>}  (user confirms LLM candidate) |
| 18 | PEER_STATUS     | any->phone           | {"peer":..,"batt":<mv>,"link":<0|1>} |

v1 types 1–10 remain valid (HELLO usable but PEER_HELLO preferred).

## HUD_FRAME rules (premortem #4)
- `lines` max 4 strings, each <= 18 chars (G2 ~640x200).
- `teleprompter`: phone streams one line at a time; glasses auto-scroll slow.
- Never send raw transcript. Always send extracted/summarized text.

## Time sync (premortem #3)
Phone owns UTC. On connect sends TIME_SYNC; peers store offset and stamp samples.
Brain joins HEALTH_SAMPLE to notes by [t-window, t+window].

## Codec negotiation
PEER_HELLO carries `caps`. Audio codec chosen by phone from bead caps ∩ phone support.
