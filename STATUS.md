# Cyclops — STATUS (2026-09-28, MVP one-button + physis-next bridge)

Single source of truth for build state lives in [`docs/00-superplan.md`](docs/00-superplan.md).
This file is the at-a-glance snapshot.

## Branch / repo
- Remote: `github.com/ilPez00/cyclops-wearable.git` (origin). **Default branch: `main`**
  (`master` force-aligned to `main` 2026-07-12; no longer stale).
- The outer `/home/gio` (ayu) repo carries a tracked snapshot of this tree by owner
  choice — canonical development happens HERE. Content-only-on-ayu commits (ayu #17–#20)
  were ported in #36.
- **Pushing to the `origin` mirror lies twice.** It lives on a mount
  (`/mnt/faststore/git-mirrors/cyclops.git`) whose ref reads go stale: an
  up-to-date push can print `Everything up-to-date` while the object is genuinely
  absent, and the *next* attempt can answer
  `! [remote rejected] (incorrect old value provided)` even though the update had
  actually landed. Observed 2026-09-28 on `freerouting-omniroute` (three false
  verdicts in one session, both directions). Trust neither the push output nor an
  immediate `ls-remote`; verify against the mirror's own filesystem:
  `git -C /mnt/faststore/git-mirrors/cyclops.git rev-parse <branch>`. If it is
  genuinely behind, `git -C <mirror> fetch --no-tags /home/gio/dev/cyclops
  refs/heads/<branch>:refs/heads/<branch>` works where push-side checks stall.

## Verification snapshots
| Gate | Result |
|------|--------|
| Python full suite (`tests/run_tests.py tests/test_*.py`) | **513 passed, 0 failed** (2026-09-28, incl. the docs/44 case-evidence pass) |
| Firmware host gate (`make test`) | **PASS** (incl. status_json clamp regression) |
| Firmware proto gate (`make proto`) | **PASS** (framing + OTA + **ADPCM contract**) |
| Firmware device builds (`xiao_128x32_i2c`, `xiao_selftest`) | **SUCCESS** (local PlatformIO) |
| G2 layout parity (Python↔JS) | PASS |
| Kotlin `:core:test` / APK | CI-only (no local SDK) |

## Verified ON METAL (2026-07-12, bare XIAO ESP32-S3 Sense)
First real-hardware session — D1 ("never flashed") is dead. Flash 18.9%, RAM 10.1%.
- **Boot**: missing screen/IMU/SD all degrade gracefully; heartbeat + HOME mode.
- **BLE**: advertises `CyclopsXIAO`; laptop central (bleak) connects, decodes live
  MSG_STATUS with the brain's own `Decoder`, writes MSG_CMD back.
- **Camera** (OV2640): VGA JPEG captured + pulled over serial (PSRAM detected).
- **Mic**: works ONLY as PDM (clk GPIO42, data GPIO41) — fixed in #38.
- **SD**: SDHC 32 GB formatted FAT (owner-approved), write+readback OK, mounts at boot.
- **Audio over BLE**: remote ACT_TRANSCRIBE_START → PDM capture → chunks decoded on the
  laptop → WAV. Measured notify throughput ~2 KB/s → drove the ADPCM work (#41).
- Repeatable bring-up: `pio run -e xiao_selftest` (SD/camera/mic report over serial).

## Recently shipped (2026-09-28 — MVP one-button + physis-next)

Plan of record: **`docs/43-mvp-one-button.md`**. MVP = full XIAO S3 Sense build
(camera + PDM mic + microSD + WiFi/BLE + I2C OLED + accel) with **ONE button**.

- **Single-button input (firmware).** `BOARD_HAS_BTN_B` in `board_config.h`
  (XIAO 0 / Feather 1); `main.cpp` guards the pin, the detector and the reset
  combo; factory reset is now "hold BTN_A ≥ 2 s at boot" (A+B kept on
  two-button boards). `Hud::use_one_button()` rebinds the single button grid to
  tap=OK / double-tap=BACK / long=AGENT and switches the HINT row to
  `tap:ok 2x:back hold:ask`. Remap stays protocol-compatible (`{"kind":"bind"}`).
  mini4 calls it too (its doc claimed that grid; the code had the 2-button one).
- **physis bridge rebuilt on physis-next.** physis-pro is retired and the app's
  `/api/physis/*` routes had vanished, so 4 tests were red. New
  `brain/physis_next.py` speaks physis-next MCP over HTTP (POST /mcp, JSON-RPC
  2.0, NDJSON, loopback only); `/api/physis/{status,search,context,remember,
  history,predict,capabilities}` are back on that backend;
  `agent/tools/physis.py` prefers MCP then `physis search` CLI then an honest
  stub; `brain/physis.py` is now the legacy embedder adapter only (classify /
  lifeos / goals / coherence deleted with their routes).
- **Loop recipes un-dead.** `justfile` no longer shells out to physis-pro:
  `just physis-serve` (starts the HTTP MCP server), `just recall`,
  `just remember`, and `just start/update` drive `scripts/physis_mcp.py`
  (exit 2 + loud stderr when no server; never a silent pass or false BLOCK).
- **Other lost routes restored** (same bug class): `/api/concepts`,
  `/api/concepts/groups`, `/api/truth`, `/api/truth/log` — turning 4 more red
  tests green and wiring `brain/concepts.py`'s truth-edit/audit functions.
- **Entity enrichment is local now** (`brain/pipeline.py::_tag_entities`):
  deterministic keyword tagging replaces the dead physis-pro `classify` call;
  `CYCLOPS_ENRICH_ENTITIES=1` (legacy `CYCLOPS_PHYSIS_ENRICH` still accepted).
- **`physis` added to the capability registry** (`agent/capabilities.py`) —
  the registry and the tool set had drifted (22 tools vs 21 capabilities).
- **Docs**: `docs/43` (plan), `docs/12-wiring.md` §7-§8 (on-metal status +
  one-button harness), `docs/30-schematics-xiao.md` (controls),
  `docs/23-hud-menu-plan.md` (input model), `docs/37` §B1 (loop re-point),
  `AGENTS.md` (hardware reality), `PLAN.md` (MVP section).
- **Gates, this pass**: python suite **499 / 0** (was 494 / 5);
  `make test` PASS (16 cmds, incl. the new one-button test) + `make proto` PASS;
  `gen_acts.py --check` in sync (27 acts); `dead_calls.py` unchanged (7
  pre-existing Android items, none from this work).

## Case redesign (2026-09-28 — docs/44, evidence first)

- **Vendor geometry is now in the repo**: `cad/vendor/seeed/` holds Seeed's own
  dimensioning DXFs, the OV3660/Sense 3D assembly and their printable shell,
  with exact re-download commands in `SOURCE.md`. What each file *actually* is
  (panel sheets, multi-body exports) is documented — a naive bbox measured the
  drawing, not the part.
- **New tool `scripts/cad_probe.py`** (`dxf|step`): pure-python (`ezdxf` +
  a STEP entity walker), no FreeCAD/pythonocc needed. The DXF probe splits
  geometry into connected components and board-relativises them; the STEP probe
  reads each `MANIFOLD_SOLID_BREP` and warns that the export's **41 assembly
  placements** make part *positions* untrustworthy (sizes are fine).
- **Hard numbers now probed** (docs/44 §2): XIAO fab outline **17.790 ×
  21.140 mm** with **14 pads, 7 per side, exactly 2.54 mm pitch**, pads
  2.04 × 1.52 mm flush with the long edges and **no mounting holes**; Sense
  assembly **17.790 × 21.150** with the camera footprint **5.050 × 4.720** at
  board-relative (7.89, 6.59) → camera axis ≈ (10.4, 8.9); expansion board
  **17.780 × 15.370** (so the XIAO overhangs it by ~5.8 mm); USB-C shell
  **8.942 × 7.300 × 4.200**; OLED glass active **22.384 × 5.584**, panel
  30.00 × 11.50 × 1.45. The old `screen_w/h = 35/36`, `screen_glass = 28` and
  the two disagreeing accel sizes are confirmed wrong.
- **Decisions locked** (docs/44 §5): 128×32 **4-pin** I2C carrier; accel stacked
  **below** the XIAO stack; **OV3660** (camera faces away from the display, i.e.
  window in the base); microSD card usable while cased; USB-C reachable with the
  lid on and the Li-Po kept off the antenna half; PLA first for the coupon.
- **Envelope:** ≈ **42.40 × 25.55 mm** footprint; Z ≈ **25.60 mm** (2.54 header
  mate) or **20.30 mm** (soldered low-profile mate) — a 5.30 mm swing on that one
  decision. Computed by `scripts/cad_params.py envelope`, not by hand: the first
  prose estimate was 5 mm adrift.
- **Next, in order:** fill the caliper sheet (docs/44 §6, M1–M14) → **print the
  coupon** and record the winners → retire the 52 legacy artefacts to
  `cad/legacy/` once the parametrized pendant exists → model the pendant.
- Docs corrected in the same pass: `docs/10` (no onboard IMU; MVP supersedes the
  ST7735/128×64 rows), `docs/11` (one button, I2C pins, MVP env, no wheel),
  `docs/30` (I2C SDA/SCL rows, MVP build, "do not use the committed models"),
  `AGENTS.md` ("Case / CAD" rules).
- **Gates this pass:** docs + one new script, no firmware/app code touched.
  Python suite **513 / 0**; `scripts/cad_probe.py` reproduces every §2 number.

## Case: single parameter source + fit coupon (2026-09-28, docs/44 §7 steps 2–3)

- **`cad/params.yaml` is now the only place a case dimension is written.** Every
  value carries its provenance: PROBED / SPEC / DEFAULT / UNVERIFIED + the
  caliper measurement (M-number) that will replace it. `scripts/cad_params.py
  generate` emits `cad/params.scad` for OpenSCAD, so a model and a check cannot
  disagree; `envelope` derives the case numbers and prints all 16 UNVERIFIED
  inputs they depend on.
- **The fit coupon exists and is verified numerically.** `cad/fit_coupon.scad`
  → `cad/stl/fit_coupon.stl` (3 bodies, all watertight, 13.3 g PLA, ~1 h, no
  supports). `scripts/cad_params.py section` reads the built mesh back:
  pockets **8.10 / 8.15 / 8.20 / 8.25 / 8.30 × 13.00**, PCB slots
  **1.60 / 1.75 / 1.90**, pilots **Ø1.60 / 1.70 / 1.80**, latch detent
  **3.00 × 2.00**, USB-C opening **9.20**, card opening **11.40** — every value
  the coupon claims, measured from the geometry rather than assumed.
- **Toolchain without root:** `scripts/get_openscad.sh` extracts OpenSCAD
  2021.01 from the official AppImage into `~/.local/share/openscad-appimage/`.
  Two traps recorded in docs/44 §7.1: this build rejects `include "..."`
  (use `include <...>`), and CGAL needs solids to *interpenetrate* by ≥0.2 mm —
  face-to-face contact emits non-manifold edges (the first coupon build proved
  it, one edge with four faces).
- **Gates this pass:** OpenSCAD compile clean (no errors/warnings), `check`
  green, `section` receipts above, python suite **513 / 0**, envelope numbers
  reproducible. The coupon has **not been printed** — that is the next physical
  step, and it is what promotes a DEFAULT into a measured value.

## Shipped (2026-09-28 — MVP one-button pass, docs/43)

- **C2 firmware serves JSON only.** The `/` HTML page is gone; `GET /status`
  returns `{cam,wifi,sd,ip,stream,audio,snap}` for the app's Device tab.
- **C4 IMU identification.** `imu_whoami.h` (two byte-identical copies,
  parity-tested) + `Imu::begin()` now refuses a part whose register map this
  driver cannot speak — an LSM6DS3 ACKs, then yields garbage. `reason()` names
  the raw WHO_AM_I byte; both mains log it and toast the short form. New host
  gate `shared/test_imu_whoami.cpp`, wired into `make proto`.
- **C5 presence/posture become ledger rows.** `status_json` grew `pres`/`pos`;
  `HudBridge.handle_status` keeps the last frame and appends a `presence` Event
  with its duration on every edge (docs/34 §5c). Wiring it surfaced a real
  protocol trap: `ACT_IMAGE_ANALYSIS == 8 == MSG_STATUS` — one integer, two
  namespaces; the frame header decides, and `dispatch()` needs
  `looks_like_status()` before it may treat act 8 as a status frame.
- **C6 `firmware/mini4` was building the wrong file.** PlatformIO's default
  `src_dir` is `src/`, so the docs/43 one-button port that landed in the
  project-root `main.cpp` was dead (`.map`: `src/main.cpp` 428×, root 0×). One
  source of truth now: `firmware/mini4/src/main.cpp`, explicit `src_dir = src`.
- **M2 app half.** `brain/events.py` (`Event{ts,duration_s,source,kind,body,
  locator}`), `POST /api/events`, `GET /api/timeline` (ledger + legacy stores on
  one axis, every row carrying source + locator), `GET|POST /api/ask` (cited
  answers; `cited:false` plus a warning when the model ignored its evidence),
  `GET /api/device`; dashboard 7 → 11 tabs (Timeline/Ask/Device/Physis),
  `node --check` clean.
- **Gates this pass:** `make test` + `make proto` PASS (incl. the new IMU tests
  and a worst-case status-frame assertion that caught the buffer at exactly
  160 B), python suite 0 failures, `gen_acts.py --check` in sync. The firmware
  IMAGE build and every on-metal claim still wait for a board — `pio` is not
  installed on this box. `dead_calls.py` still reports 7 acked-dead Android
  symbols (LifeOS/Coherence decided dropped, docs/43 §6).

## Recently shipped (2026-07-27 pass)
- **LAN auth on `app/server.py` — premortem P0 closed.** The server binds
  0.0.0.0 by design, and `POST /api/agent` reaches an agent holding the
  terminal tool; it was unauthenticated. Now the PEER decides: loopback is
  exempt, anything off-host presents the shared secret in `~/.cyclops/token`
  (`?token=` / `cyclops_token` cookie / `X-Cyclops-Token`). `/health` stays
  open for discovery. `CYCLOPS_ALLOW_INSECURE_LAN=1` opts out, loudly.
  Verified from a second address on the wire, not just in tests
  (`tests/test_app_auth.py`).
- **Auto-learning was dead in production.** `agent/learning.py` called
  `router.complete()`; `ModelRouter` only has `chat()`. Every review raised
  AttributeError into a stderr line, so no fact was ever persisted. `_ask()`
  now accepts either client shape. It is a real second model call per turn, so
  it is gated by the new `AgentConfig.learning` (default on).
- **`AiKeys` registered every `~/.env` variable as an endpoint** — so
  `get_endpoint("ai_groq_key")` returned the *secret*, and `LLMClient` built
  `gsk_.../chat/completions` ("unknown url type"). Endpoints must now look like
  URLs; trailing `# comments` are stripped out of values.
- **`LLMExtractor` degraded silently.** With `_DEFAULT_PROVIDER=omniroute`, a
  user holding only Groq keys got rule-based notes forever with no log line.
  It now falls back to a provider configured with *both* a key and an http
  endpoint, says so once, and traces failures with credentials redacted.
- **Test suite green + honest**: 389/4-failed → 406/0. `test_screen_offline`
  asserted "no screenshot backend" on a box that has scrot — it was silently
  screenshotting the developer's desktop every run; the backend lookup is now
  injectable and screen capture obeys `consent_mode`.
- **Wire-drift gates**: `brain.protocol.MSG` is now checked against the C++
  `MsgType` enum (it had stopped at TTS=20 while the header grew OTA 21–24),
  and the two in-repo copies of `cyclops_shared.h` are asserted identical.

## Recently shipped (earlier cycle, PRs #33–#42)
- **Four on-metal firmware fixes** (#38): PDM mic config; BLE audio chunks never fit
  `send_frame` (silently dropped — now sliced); `status_json` garbage-tail clamp;
  incoming MSG_CMD dispatch (phone can drive capture/HUD, consent-gated).
- **IMA ADPCM codec** (#41): 4:1 audio compression, C++/Python byte-identical wire
  contract, self-contained chunks, warm step-index across chunks; firmware streams
  ADPCM and announces the codec in MSG_AUDIO_META byte[5].
- **ADPCM ingest** (#42, in CI): `HudBridge.handle_audio` decodes per the META codec
  byte; legacy 5-byte META keeps raw PCM.
- **BleakBackend** (#40): real BLE radio behind `BleLink` — the "transport glue
  pending" gap. Import-safe (bleak loads on connect).
- **Obsidian vault sink** (#37): notes mirror into a vault as frontmatter pages +
  daily-note wikilinks (`CYCLOPS_OBSIDIAN_VAULT`); `memory_root` can live in-vault.
- **Test hardening** (#39): learning-suite gaps + env-independent omi BLE test.
- DeviceSim coverage (#33), Android BLE service glue (#35), docs sync (#34).

## Open / next
- **Boards: XIAO + Feather both build (2026-09-19).** One application, three
  targets, all green on this box: `xiao_128x32_i2c` (18.5%/33.5%),
  `feather_128x32_i2c` (20.8%/73.0% of 4MB), `xiao_mini4` (10.1%/17.0%).
  Board differences are in `firmware/xiao/src/board_config.h`
  (`-DCYCLOPS_BOARD_XIAO` / `-DCYCLOPS_BOARD_FEATHER`). Neither board was ever
  reached for INSTALL: the XIAO has not enumerated on USB since 12:03 today
  (kernel: `303a:1001 … ttyACM0` at 12:02:11, disconnect 12:03:01; `lsusb` and a
  70 s BLE scan show nothing since), and no Feather has appeared either.
  Commands: `make compile BOARD=feather`, `make flash BOARD=feather`,
  `pio run -d mini4`. See docs/flash-xiao.md §3/§4.
- **Work mirrored to `/home/gio/dev/cyclops`.** rsync of the canonical tree +
  the target's uncommitted work restored (backup tarball kept). One casualty:
  `firmware/mini4/main.cpp` was untracked and got deleted by the sync before its
  backup; RECONSTRUCTED from docs/15-mini4.md into `firmware/mini4/src/main.cpp`
  with its own platformio.ini — the `xiao_mini4` env the doc referenced for
  months but which never existed.
- **Live re-verify with ADPCM firmware** — board was unplugged mid-session; rerun
  audio E2E + BleLink-over-BleakBackend when reattached.
- **MSG_STATUS heartbeats starve during audio streaming** (observed live).
- **On-device VAD gate** — landed in firmware (71d2f72); not yet measured on metal.
- **Android companion must now send the token** — the APK talks to this server
  over the LAN and every route except `/health` is gated. Until it carries
  `X-Cyclops-Token`, pair by opening the dashboard URL with `?token=` once, or
  run with `CYCLOPS_ALLOW_INSECURE_LAN=1` on a network you trust.
- Ring on metal: R02 was advertising in scans; `ENABLE_RING` central path unverified.
- Live Ollama llava vision test (T2.6); Android `:app` build still SDK-gated.
- **`plan.md` and `PLAN.md` both exist here** — on a case-insensitive checkout
  (a Mac clone, a zip round-trip) one silently overwrites the other.
- **Encryption at rest** (premortem P2): `~/.cyclops/notes.jsonl`,
  `sightings.jsonl` and `profile.json` (which holds `api_key`) are plaintext,
  and `~/.cyclops/token` now joins them.

## Principles (unchanged)
One brain, thin clients. Offline-first (every tool stubs without network/keys).
Secrets never committed. KISS/DRY. Verify before claiming done — on metal when it's metal.
