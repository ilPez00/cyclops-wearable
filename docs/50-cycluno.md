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
| OLED SSD1306 (I2C, 0x3C) | SDA=A4, SCL=A5, VCC=5V, GND | 4-pin I2C board; 7-pin board → strap CS/DC/RES (below) |
| Joystick 1 (primary) | VRx=A0, VRy=A1, SW=D2, +=5V, GND | scroll Y + push=select/REC |
| Joystick 2 (secondary) | VRx=A2, VRy=A3, SW=D3, +=5V, GND | push=menu/back |
| Button B1 | D4 | select / REC (mirrors J1 push) — no VCC, internal pullup |
| Button B2 | D5 | menu / back (mirrors J2 push) — no VCC, internal pullup |
| Button B3 | D6 | ask agent — no VCC, internal pullup |
| Button B4 | D7 | home — no VCC, internal pullup |
| USB | Serial @115200 | brain link |

**Buttons need NO power wire.** They are passive switches: SIG→MCU pin (D4–D7),
GND→GND. The logic HIGH comes from the MCU's *internal* pullup
(`pinMode(pin, INPUT_PULLUP)`), tied to the board's logic rail — 5V on the Uno,
3.3V on the XIAO. Pressing shorts SIG→GND → reads LOW. Joysticks are different:
they need real +5V so the pot wiper can output a voltage to the ADC.

### 7-pin OLED module strapping (if your board isn't the 4-pin I2C type)
A common SSD1306 breakout carries 7 pins. I2C firmware only drives
VCC/GND/SDA/SCL — the other three must be strapped or the controller won't init:
- **RES** → pull up to VCC with 10k (or wire to a free MCU pin if you want a
  hard reset; firmware resets over Wire so leaving it pulled-up-and-NC is fine).
- **DC** → tie to **GND** (selects I2C/"command" line state).
- **CS** → tie to **VCC** (permanently selected; no SPI CS needed).
Do NOT leave CS/DC floating — that's the "unmapped cables" trap.

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

---

## Full assembly — every wire

This is the complete, end-to-end build. Nothing left implicit. The schematic
`cyclops_v1_CyclUno.png` and the assembly poster `cyclops_v1_CyclUno_ASSEMBLY.png`
(both regenerated from `docs/_gen_wiring_guide.py`) show the same thing drawn.

### Parts list
| Qty | Part | Notes |
|-----|------|-------|
| 1 | Arduino Uno (ATmega328P) | or Nano (same pinout) |
| 1 | SSD1306 128x32 OLED | I2C, blue board, addr 0x3C (4-pin or 7-pin) |
| 2 | Analog joystick module | 5-pin (VRx/VRy/SW/+/GND) |
| 4 | Tactile pushbutton | momentary, 2 legs |
| — | Jumper wires | dupont M-F / F-F |
| 1 | 10k resistor | only if you use a 7-pin OLED (RES strap) |
| 1 | USB cable | Uno → host (brain) |

### Every connection (signal + power + ground)
OLED (connect ALL of these):
- VCC → Uno **5V**
- GND → Uno **GND**
- SDA → Uno **A4**
- SCL → Uno **A5**
- *(7-pin board only)* RES → 10k → **5V** (strap)
- *(7-pin board only)* DC → **GND** (strap)
- *(7-pin board only)* CS → **5V** (strap)

Joystick 1 (primary nav):
- VRx → **A0**
- VRy → **A1**
- SW → **D2**
- + → **5V**
- GND → **GND**

Joystick 2 (secondary):
- VRx → **A2**
- VRy → **A3**
- SW → **D3**
- + → **5V**
- GND → **GND**

Button B1 (select / REC):  SIG → **D4**, other leg → **GND**
Button B2 (menu / back): SIG → **D5**, other leg → **GND**
Button B3 (ask agent):    SIG → **D6**, other leg → **GND**
Button B4 (home):         SIG → **D7**, other leg → **GND**

USB: Uno USB port → host running `demo_cycluno.py` @115200.

> **Power rule:** buttons are passive switches — they get NO VCC wire. The logic
> HIGH comes from the Uno's *internal* pullup (`INPUT_PULLUP`), tied to the 5V
> rail. Only the OLED and the joystick `+` pins draw real 5V. Do NOT connect
> buttons to chassis/metal-case ground; use the Uno GND rail only.

### Step-by-step build
1. **Flash first** so you can test as you go:
   `cd firmware && pio run -e cycluno -t upload`
2. Place the Uno. Identify on its header: **5V, GND, A0–A5, D2–D7**, USB.
3. **OLED:** VCC→5V, GND→GND, SDA→A4, SCL→A5. If 7-pin, strap RES→10k→5V,
   DC→GND, CS→5V (do not leave them floating).
4. **Joystick 1:** VRx→A0, VRy→A1, SW→D2, +→5V, GND→GND.
5. **Joystick 2:** VRx→A2, VRy→A3, SW→D3, +→5V, GND→GND.
6. **Buttons B1–B4:** each = SIG→D4/D5/D6/D7, other leg→GND.
7. **USB** to host; run `python3 demo_cycluno.py`.
8. **Verify:** OLED shows HOME; press **B1** → "REC" toast + ring marker;
   push **J1** → select; **J2** push → back/menu.

### Verification checklist
- [ ] OLED lights (addr 0x3C; if blank, try 0x3D in `screens.h`)
- [ ] J1 Y scroll moves the cursor (center-locked single step)
- [ ] B1 / J1-push toggle REC; B2 / J2-push go back
- [ ] B3 fires "agent…" toast; B4 returns HOME
- [ ] `demo_cycluno.py` streams NOTE frames back to the ring
