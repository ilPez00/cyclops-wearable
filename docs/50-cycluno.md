# CyclUno — Cyclops dev unit on an Arduino Uno

The wearable product at breadboard scale: buttons + scrollwheel + OLED + LEDs
on an Uno, wired to the brain over USB serial. No WiFi/BT — the serial cable
substitutes the radio while exercising the exact same v2 frame protocol and
the exact same brain pipeline (transcriber → extractor → notes → HUD frames).
Prerecorded fixtures stand in for live audio until the mic path exists.

## Why an Uno when the XIAO exists
- Buttons/wheel bring-up without risking the wearable board.
- The ATmega328P's 2 KB SRAM forces the lean-HUD discipline (`cycluno.h`,
  `sizeof(UnoHud)` gated < 400 B — the full `cyclops::Hud` is ~1.9 KB, which
  is why the first Arduino target died).
- Anything proven here (input handling, frame flow, pipeline) transfers
  upstream unchanged, because the wire protocol is shared.

## Wiring
| Part | Pin |
|------|-----|
| OLED SSD1306 (I2C, 0x3C) | SDA=A4, SCL=A5, VCC=5V, GND |
| Rotary encoder A / B | D2 / D3 (both interrupt-capable) |
| Encoder push / button A | D4 (to GND, internal pullup) |
| Button B (menu/back) | D5 (to GND, internal pullup) |
| REC LED (+resistor) | D6 |
| Link LED (+resistor) | D7 |

Controls: **wheel** scrolls notes/menu · **A** = REC toggle on HOME, select in
MENU · **B** = menu/back. Link LED is lit while frames arrive; REC LED mirrors
recording state.

## Build + flash
```
cd firmware
pio run -e cycluno                # compile gate (flash ~35%)
pio run -e cycluno -t upload      # flash (auto-detects the Uno's port)
```
Host logic gate (no hardware): `make proto` runs `test_cycluno.cpp`.

## Run the wired brain
```
python3 demo_cycluno.py                       # auto-picks /dev/ttyACM*|ttyUSB*
python3 demo_cycluno.py --fixtures tests/fixtures/cycluno_transcripts.txt
```
Press **A** on the unit: the driver "transcribes" the next prerecorded take
through the real pipeline and streams the extracted notes back as NOTE frames
— they appear on the OLED ring. `Menu → Ask agent` returns a canned reply
offline (the real agent drops in behind the same frame).

The transport layer is `device/serial_link.py` (`SerialLink`): same shape as
`BleLink`, pyserial imported lazily, fully offline-tested via an injected
duplex (`tests/test_serial_link.py`).

## Bash TUI
```
./shells/cyclops.sh                # interactive: notes, ask, ingest
./shells/cyclops.sh --once         # status + notes, scriptable (CI-tested)
CYCLOPS_URL=http://host:8080 ./shells/cyclops.sh
```
curl + python3 only (json parsing) — no pip, no external TUI toolkit.

## Fixture pipeline (prerecorded data)
`tests/fixtures/cycluno_transcripts.txt` = one "take" per line. The demo
driver synthesizes deterministic speech-band PCM per take (a real WAV drops
into the same flow), runs it through the transcriber interface, extracts
notes, and ships them over the wire. Image/video fixtures follow the same
pattern once the vision path is wired to the serial demo.
