# cyclops — agent notes

Wearable + companion app.

## Rules

- **The companion app is the single UI surface.** No separate device- or
  firmware-served browser pages. Firmware may expose JSON only; the app renders
  it. The reason is that the app must work when the wearable is asleep or
  offline.
- New features are **app endpoints plus a dashboard tab**, not device pages.
- `app/templates/dashboard.html` is deliberately a single self-contained file:
  vanilla JS, zero dependencies, offline, no CDN. Keep it that way.
- Captured media lives host-side under `~/.cyclops/captures/{images,audio,video}/`.
  The device SD card holds `/cyclops.log` only, never media.
- The capture endpoint is SSRF-guarded (private-LAN only, IP-pinned, no
  redirects). Do not relax those checks.

## Hardware reality

The KY-040 rotary encoder was **removed**. The deck is joysticks (JOY1/JOY2) plus
buttons (A/B/J2/X/Y) and a MODE toggle. Do not re-add rotary-zoom; any spec
describing it is obsolete.

The **MVP harness (docs/43) has ONE button** on GPIO3 — BTN_B is not populated
and GPIO5 is free. The single button is bound tap=OK, double-tap=BACK,
long=AGENT (`Hud::use_one_button()`, hint row `tap:ok 2x:back hold:ask`);
factory reset is a ≥2 s hold at boot. Two-button boards (Feather) keep the old
2×3 grid. The accelerometer is an external MPU-class part at `0x68` on the
shared I2C bus — `imu.cpp` speaks MPU registers, so `imu_whoami.h` refuses
anything else (an LSM6DS3 at 0x6A/0x6B would ACK and read garbage).

`firmware/mini4` builds `src/main.cpp` (PlatformIO's default `src_dir`); the
project-root `main.cpp` is **not** compiled — do not recreate it (`src_dir = src`
is explicit in `mini4/platformio.ini`). Firmware serves **JSON only**
(`/status`, `/audio.wav`, `/stream`, `/snap`) — never a device page.

The Colmi R02 ring has **no physical button** — taps are synthesised from
accelerometer spikes in `ring.TapDetector`. Its checksum is `sum(first15) % 255`
(mod 255, not 256), and the ring streams nothing until the host writes an enable
frame.

## Case / CAD

The committed `cad/*.scad`, `cad/*.blend`, `cad/*.stl` and `cad/freecad/*`
models are built on wrong part dimensions and contradict each other (evidence
table: `docs/44-case-redesign.md` §0). Do not extend them, do not print them,
and do not "fix" one of them in isolation — they are presets awaiting
retirement, not sources.

Dimensions are only usable when **probed** from the vendor's own geometry
(`python3 scripts/cad_probe.py dxf|step <file>`, originals in `cad/vendor/seeed/`)
or **measured** with calipers. `docs/44` §2 holds the probed table, §4 the
tolerance defaults and §6 the caliper sheet — fill §6 before modelling
anything. Firmware is unaffected by case work: `/status` JSON and the protocol
are the only interfaces the enclosure may assume.
