# docs/43 — MVP: XIAO S3 Sense, all onboard hardware, ONE button

Status: implementation started (2026-09-28). Supersedes the input half of
docs/23-hud-menu-plan and the board half of docs/zero-plan (that doc's
"onboard LSM6DS3" is wrong for this board — see §2).

One sentence: **the MVP is the full XIAO ESP32-S3 Sense build — camera, PDM
mic, microSD, WiFi/BLE, I2C OLED, accel — plus a single physical button**, and
`physis-next` (not the retired `physis-pro`) is the memory substrate behind it.

## 1. Locked BOM (verified against `firmware/xiao/src/board_config.h`)

| Part | Pin | Notes |
|---|---|---|
| XIAO ESP32-S3 **Sense** | — | onboard: OV2640 (SCCB + DVP), PDM mic (clk 42 / data 41), microSD (CS 21 + 7/8/9), WiFi/BLE |
| SSD1306 128×32 I2C OLED | SDA 43 / SCL 44, addr `0x3C` | 21×4 chars, 4 rows |
| HW-123 accel (MPU-class) | same bus, addr `0x68` | tilt-scroll, gestures, presence, posture |
| **BTN — one only** | GPIO3 | active-low, `INPUT_PULLUP`; **GPIO5 is free** in the MVP |
| Battery divider | GPIO2 | ÷2 (BAT+ →100k→ D2 →100k→ GND) |
| Li-Po | BAT pad | onboard charge IC |

Build: `pio run -e xiao_128x32_i2c` (18.5% RAM / 33.5% flash measured on
metal). Bringup: `pio run -e xiao_selftest`. SD holds `/cyclops.log` only —
media is host-side under `~/.cyclops/captures/` (AGENTS.md).

## 2. Hardware truth (do not re-derive from zero-plan)

- **No onboard IMU.** `docs/32-wiring.md:106` — the onboard LSM6DS3 is on the
  nRF52840 *Nano* Sense, a different board. The MVP accelerometer is an
  external MPU-class part at `0x68` on the shared I2C bus.
- `imu.cpp` speaks MPU registers (`PWR_MGMT_1 0x6B`, `ACCEL_XOUT 0x3B`) and
  accepts any WHO_AM_I ack, so an **LSM6DS3 (0x6A/0x6B) would ACK and then read
  garbage**. The MVP must use an MPU-6050-class part, or `imu.cpp` needs a
  second register map (open item C4).
- GPIO3 is a strapping pin: never hold the button during power-up.
- GPIO0/1/4/5/6/10-20/38/39/45-48 are free (GPIO5 freed by dropping BTN_B).

## 3. Single-button input model

One button × 3 gestures + accel gestures must reach all 27 `ACT_*` ids. Tilt +
MENU carries the rest. Frozen table (implemented by `hud.h::use_one_button()`):

| Input | Action | Previously |
|---|---|---|
| tilt fwd/back | `on_wheel(±1)` — scroll | unchanged |
| tap | `ACT_OK` (`on_select`; HOME → MENU) | A single |
| double-tap | `ACT_BACK` (`on_cancel`) | B single |
| long (>600 ms) | `ACT_AGENT` (+ abort on second long) | A long / nod |
| nod | quick-capture toggle (`ACT_TRANSCRIBE_START`, consent-gated) | unchanged |
| shake | `on_back_gesture()` → back/dismiss | unchanged |
| face-down / 8 s idle | screen off; off-body → consent off (fail-closed) | unchanged |
| MENU (tap from HOME, tilt to move) | Photo/Video/Translate/Health/Navigate/Teleprompter/Camera/ImageAnalyze/SSH/Settings | unchanged |
| hold button at boot ≥ 2 s | factory reset (was BTN_A + BTN_B at boot) | changed |

Rationale: `ACT_BACK` sits on the cheapest gesture because menu traversal is
the most-used input; photo / video / voice-note stay reachable through MENU and
nod, so nothing becomes unreachable. The 2-button Feather target keeps the old
grid (`BOARD_HAS_BTN_B 1`).

Remap stays protocol-compatible: `{"kind":"bind","btn":0,"g":N,"act":M}` still
writes the button-0 row; button-1 cells are inert on the MVP.

## 4. What the MVP ships

Device-local (all from in-tree shared libs): tilt-scroll, tap/double/long,
nod/shake, presence→consent-off, posture cue, HUD 16 modes with the
STATUS/ANSWER/DIGEST/HINT rows, VAD-gated voice notes + loud-sound tier,
on-demand OV2640 capture (`/stream`, 60 s idle teardown), SD log, BLE OTA,
config portal (first boot, 60 s auto-bypass), battery percent in `MSG_STATUS`.

Host-side (thin-client model, `docs/42-vision.md`): transcription, extraction,
claims/evidence, calendar loop, notification triage, world registry /
how-to / translate, agent + terminal (token-gated, HITL), media capture,
**physis-next memory** (§6).

Parity carried from `docs/07-features-omi-g2.md`: glanceable HUD, notes/memory,
conversation search, notifications. Still open for parity: NAV (phone GPS),
music control, teleprompter script source, 24/7 recording budget, live G2/Omi
BLE on metal.

## 5. Work items

| ID | Item | Status |
|---|---|---|
| A1 | Plan + wiring docs | done (2026-09-28) |
| A2 | Restored the routes that had gone missing: `/api/physis/*`, `/api/concepts`, `/api/concepts/groups`, `/api/truth`, `/api/truth/log`; `physis` in the capability registry | done (2026-09-28) |
| C1 | Single-button port: `BOARD_HAS_BTN_B`, one detector, boot-hold reset, `use_one_button()` + hint row | done (2026-09-28) |
| C2 | Drop the firmware-served HTML page; keep `/stream` (MJPEG) + `/audio.wav`, JSON only | **done** — `/` HTML handler deleted, JSON `/status` added; `camera_capture.h` documents the rule. Gate: `pio run -e xiao_128x32_i2c` (bench; pio is not on this box) |
| C3 | Measure VAD gate + `MSG_STATUS` starvation during ADPCM streaming on metal | open (metal only) |
| C4 | Accel part check: WHO_AM_I refusal screen (LSM6DS3 reads garbage today) | **done** — `imu_whoami.h` (two identical copies, parity-tested), `Imu::begin()` refuses unsupported parts, `reason()` names the raw byte; both mains log it + toast the short form. Gate: `cd firmware && make proto` → `ALL IMU WHO_AM_I TESTS PASSED`; `tests/test_wire_contract.py` (8 passed) |
| C5 | Presence/posture edges logged as claim boundaries (docs/34 §5b/§5c) | **done** — `status_json` carries `pres`/`pos`; `HudBridge.handle_status` records the last frame and appends a `presence` Event (body + duration) on every edge; `/api/device` exposes both. Gate: `make test` (status + worst-case frame) + `tests/test_events.py` + `tests/test_app_api.py`. **Trap found while wiring it:** `ACT_IMAGE_ANALYSIS == 8 == MSG_STATUS` — one integer, two namespaces. The frame HEADER is unambiguous (`device/ble.py`, `FrameReceiver` route status by type), and `dispatch()` needs `looks_like_status()` (body carries status keys) before it may treat act 8 as a status frame; a non-status payload falls through to the action handler. Pinned by `test_status_frames_reach_the_bridge_through_every_router`. |
| C6 | mini4 built the WRONG file: PlatformIO's default `src_dir` is `src/`, so the docs/43 port in `mini4/main.cpp` was dead (`.map` references `src/main.cpp` 428×, root 0×) | **done** — single source of truth `firmware/mini4/src/main.cpp`, explicit `src_dir = src`, duplicate deleted |
| M0 | physis-next bridge replaces the dead physis-pro paths | done (2026-09-28) |
| M2 | App half: event ledger + Timeline/Ask/Device/Physis tabs | **done** — `brain/events.py`, `POST /api/events`, `GET /api/timeline`, `GET|POST /api/ask` (cited), `GET /api/device`; dashboard 7 → 11 tabs (`node --check` clean). Gate: `python3 tests/run_tests.py tests/test_*.py` → 0 failed |

## 6. physis-next bridge (M0)

The old wiring was dead: `brain/physis.py` called physis-**pro**-web
`/api/v1/*` (retired server), `/api/physis/*` routes no longer existed in
`app/server.py` (4 tests red), and `justfile` shelled out to
`/home/gio/dev/physis-pro/...`.

New wiring (loopback only — `physis serve --http` never binds 0.0.0.0):

```
wearable ─BLE─► app/server.py :8080 (token-gated, single UI surface)
                    │
        brain/physis_next.py — JSON-RPC 2.0 over POST /mcp (NDJSON), stdlib
                    │
        physis serve --http 127.0.0.1:19876 --path <ROOT>
                    │
   physis.search · context_stats · remember · history · predict · capabilities
```

- `PHYSIS_URL` (default `http://127.0.0.1:19876`), `PHYSIS_ROOT` (indexed tree).
- `just recall/remember` go through `scripts/physis_mcp.py` (physis-next has no
  `system` subcommand); no server ⇒ loud note + empty history, never a false
  block in `just start`.
- Routes restored on the new backend: `/api/physis/{status,search,context,
  remember,history,predict,capabilities}`.
- Retired on purpose: the physis-pro `lifeos/goals/quality/communities`
  proxies. Android `LifeOSActivity`/`CoherenceActivity` called those dead
  routes; decision — drop the screens (docs/34 §4c, 14 → 4), reimplement goals
  on a local JSON store later if wanted.

## 7. App plan (single UI surface)

Dashboard tabs are additive: **7 → 11**, `dashboard.html` stays one file,
vanilla JS, zero CDN (`node --check` on the inline script is the cheap gate).

| Tab | Endpoint | State |
|---|---|---|
| Device | `GET /api/device` — last `MSG_STATUS` frame (battery/charging/rec/mode + C5 `pres`/`pos`), HUD-mirror rows, capture counts + paths, OTA image availability | shipped |
| Timeline | `GET /api/timeline` — event ledger merged with notes/sightings/claims, newest-first, every row carrying `source` + `locator` | shipped |
| Ask | `GET|POST /api/ask?q=` — evidence first, then the model; `cited:false` + a warning when the answer used no id | shipped |
| Physis | `GET /api/physis/{status,search}` — reachable/url/api_version + memory search | shipped |
| (unchanged) | feed, notes, entities, progress, proposals, files, cost | — |

Supporting surface added with them: `brain/events.py` (`Event{ts,duration_s,
source,kind,body,locator}`), `POST /api/events` for writers that live outside
the brain, and a ledger row appended by `/api/ingest` (docs/34 §1b: writers
append, readers keep working). Android still mirrors: the APK must finally send
`X-Cyclops-Token` (open item in STATUS.md), and the two dead screens
(`LifeOSActivity`, `CoherenceActivity`) stay dropped per §6.

## 8. Gates

- Firmware host: `cd firmware && make test && make proto`; protocol parity
  `python3 protocol/gen_acts.py --check`.
- Firmware image: `pio run -e xiao_128x32_i2c` (PlatformIO is not installed on
  this box — image builds happen on the bench/CI), bringup
  `pio run -e xiao_selftest`.
- App/brain: `python3 tests/run_tests.py tests/test_*.py` (0 failures) and
  `just apk-gate` (6 gates incl. `dead_calls.py`).
- physis-next side untouched: `just ci` in that repo stays the authority.

## 9. Open decisions (defaults taken, veto any)

1. LifeOS/Coherence Android screens: **dropped** (dead upstream), not ported.
2. physis root: `CYCLOPS_OBSIDIAN_VAULT` if set, else `~/.cyclops`.
3. App shape: additive tabs now; docs/34 Phase-4 restructure later.
4. Entity enrichment on ingest: local keyword tagging (no network), replacing
   the dead physis-pro `classify` call; env `CYCLOPS_ENRICH_ENTITIES`
   (`CYCLOPS_PHYSIS_ENRICH` accepted as legacy alias).

