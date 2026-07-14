# CyclUno — Cyclops dev unit on an Arduino Uno

The wearable product at breadboard scale: a screen + joysticks + buttons on an
Uno, wired to the brain over USB serial. No WiFi/BT — the serial cable
substitutes the radio while exercising the exact same v2 frame protocol and
the exact same brain pipeline (transcriber → extractor → notes → HUD frames).
Prerecorded fixtures stand in for live audio until the mic path exists.

> Bench build reality (this unit): **2 joysticks + 4 buttons, NO rotary
> encoder, NO LEDs.** Scroll is the joystick Y axis; REC/link state shows on
> the OLED only.

## Why an Uno when the XIAO exists
- Buttons/joystick bring-up without risking the wearable board.
- The ATmega328P's 2 KB SRAM forces the lean-HUD discipline (`cycluno.h`,
  `sizeof(UnoHud)` gated < 400 B — the full `cyclops::Hud` is ~1.9 KB, which
  is why the first Arduino target died).
- Anything proven here (input handling, frame flow, pipeline) transfers
  upstream unchanged, because the wire protocol is shared.

## Wiring (revised bench build)

Screen — I2C SSD1306 128x32 (blue board, 0x3C): SDA=A4, SCL=A5, VCC=5V, GND.

| Part | Pin | Notes |
|------|-----|-------|
| OLED SSD1306 (I2C, 0x3C) | SDA=A4, SCL=A5, VCC=5V, GND | |
| Joystick 1 (primary) | VRx=A0, VRy=A1, SW=D2 | scroll Y + push=select/REC |
| Joystick 2 (secondary) | VRx=A2, VRy=A3, SW=D3 | push=menu/back |
| Button B1 | D4 | select / REC (mirrors J1 push) |
| Button B2 | D5 | menu / back (mirrors J2 push) |
| Button B3 | D6 | ask agent |
| Button B4 | D7 | home |
| USB | Serial @115200 | brain link |

Joysticks are analog (10-bit ADC); scroll uses a center-locked single step
(hold = one move, returns to center to unlock). All switch pins are active-low
with the internal pullup. No physical LEDs — REC/link state is shown on the
OLED (toast + REC marker in the HOME row).

## Controls
- **J1 Y / wheel** scrolls notes & menu.
- **J1 push or B1** = select on MENU / REC toggle on HOME.
- **J2 push or B2** = menu/back.
- **B3** = ask agent. **B4** = home.

## Build + flash
```
cd firmware
pio run -e cycluno                # compile gate (flash ~34%)
pio run -e cycluno -t upload      # flash (auto-detects the Uno's port)
```
Host logic gate (no hardware): `make proto` runs `test_cycluno.cpp`.

## Run the wired brain
```
python3 demo_cycluno.py                       # auto-picks /dev/ttyACM*|ttyUSB*
python3 demo_cycluno.py --fixtures tests/fixtures/cycluno_transcripts.txt
```
Press **B1** (or push J1) on the unit: the driver "transcribes" the next
prerecorded take through the real pipeline and streams the extracted notes
back as NOTE frames — they appear on the OLED ring. `Menu → Ask agent` returns
a canned reply offline (the real agent drops in behind the same frame).

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
