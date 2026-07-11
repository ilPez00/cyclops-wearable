# Cyclops — Build Plan & Progress

> Single consolidated progress file. Live snapshot: 2026-07-11.
> Branch: `main` (canonical). All app code lives here.
> Repo root: `/home/gio/cyclops` (remote `cyclops-wearable.git`).

## 1. Status — what's built & verified

| Tier | Feature | Verified | Commit |
|------|---------|----------|--------|
| P0-A | Desktop HUD simulator (decodes real wire frames) | ✅ 172/0 suite | `6bf7f7e` |
| P0-B | OpenGlass / XIAO camera ingest → vision | ✅ | `fb8f766` |
| P0-C | EvenRealities G2 4×18 layout + `.ehpk` plugin | ✅ node + py | `be3405e` |
| P0-D | Consent Mode (gates capture/camera/omi; firmware REC gated) | ✅ | `30b308b` |
| P1-A | Omi audio ingestion (consent-gated) | ✅ | `831bd09` |
| P1-B | Local-first pipeline (cloud only when opted in) | ✅ | `d8cabe2` |
| P1-C | G2/R1 gestures → HUD input | ✅ | `6386670` |
| P1-D | Unified health frame (`HealthAggregator`) | ✅ | `7089bf7` |
| P2-A | Local-first plugin marketplace | ✅ | `713f9eb` |
| P2-B | Multi-source context fusion (wired to agent) | ✅ | `7890abd` |
| P2-C | Phone→wearable health relay | ✅ | `af195ab` |
| P2-D | Offline-safe `make flash` + flash guide | ✅ | `76a2841` |
| T4.11 | CI host-gate job + full-suite + `cyclops` trigger | ✅ | `54ec3de` |
| T4.10 | PR `cyclops`→`master` | 🔶 OPEN #2 | — |
| 128×128 prep | Simulator profiles (legacy/128x128/g2) + tests | ✅ 172/0 | (this commit) |

**Verification status:** Python suite 185+2 / 0+4 (187 baseline, 4 pre-existing flaky gesture/hud). Ruff 0 errors, format clean. Firmware host gate (`make test`) 11/11 cmds PASS, `make proto` ALL SHARED TESTS PASSED. Android Kotlin `:core:test` runs only on CI.

**Known false-positive:** (resolved — no longer flagged.)

## 2. 128×128 ST7735 screen — preparation (incoming hardware)

**Key finding:** the incoming screen is the firmware's **DEFAULT target**. `screens.h` `St7735Screen` already declares `w=128, h=128, char_cols=21, text_rows=16`. So "preparing" = (a) exploit the extra rows the current `render()` underuses, and (b) make the laptop simulator mirror the real 21×16 grid so UX is designable headless.

### Done this turn (verifiable, no hardware)
- `shells/hud_sim.py`: added `profile=` arg + `PROFILES` dict (`legacy` 21×4, `128x128` 21×16, `g2` 18×4). Parameterized the hardcoded 21-col wrap. `demo(profile=...)` + `demo_128x128()`.
- `tests/test_hud_sim.py`: `test_profile_128x128_geometry` (asserts 21×16) + `test_profile_g2_geometry`. Suite now 172/0.
- This lets us render/verify the 128×128 UX on a laptop today, matching `St7735Screen` geometry.

### Remaining when the board lands (hardware/CI only — not host-testable)
1. **`screens.h` init correctness.** `St7735Screen::begin()` uses `initR(INITR_MINI160x80)`. A true 128×128 ST7735 module usually needs `initR(INITR_144GREENTAB)` (or `initB()` for 1.44"/1.8" variants) + correct `setRotation()`. Must be set against the actual module's datasheet. Cell metrics: at `setTextSize(1)` Adafruit GFX is 6×8 px; a 128×128 panel fits ~21 cols × 16 rows — matches `char_cols=21, text_rows=16` already. Verify wiring (CS/DC/RST/SPI pins) on the XIAO S3 Sense.
2. **Exploit the panel in `render()` (firmware, host-testable).** HOME currently draws one size-2 banner line then drops to size 1, wasting ~15 rows. With 16 text rows available, HOME should show: banner (size 2, ~1–2 rows) + health (HR/SpO2/ring batt) + a notes preview (last 2–3) + REC timer + consent state. `render()` is resolution-agnostic (`scr.text_rows()`/`scr.char_cols()`), so this is additive and stays host-gated. Recommended: branch layout on `scr.text_rows() >= 8` (TFT) vs `< 8` (OLED).
3. **Icons / bitmap (optional, TFT-only).** 128×128 RGB565 can show a small HR heart / REC dot / battery glyph via `draw_rect` blocks or an XBM. Keep a monochrome fallback for OLED profiles.
4. **Power.** TFT backlight drains vs OLED. `sleep_after` + `screen_on` already gate idle sleep — confirm backlight pin is cut on sleep for the ST7735 (likely a GPIO to the LED pin), not just `fillScreen(BLACK)`.
5. **Build flag.** `make xiao` already targets `xiao_st7735` (`platformio.ini` env `-DSCREEN_ST7735`). No build-system change needed; just confirm the module matches `INITR_*` init.

## 3. Proposal — further improvements (prioritized)

**P3 (high value, mostly host-verifiable):**
- **P3-A** Exploit 128×128 in `render()` HOME/AGENT (above). Big UX win, testable via `test_hud.cpp` + simulator 128×128 profile.
- **P3-B** Notes list scrolling polish: currently NOTES shows raw `note_count` lines; on 16-row TFT show a scrollable window with a top/bottom indicator. Host-testable.
- **P3-C** `render()` regression harness: snapshot the 21×16 grid for each Mode into `test_hud.cpp` so firmware layout drift is caught (mirrors simulator). 

**P4 (needs hardware / CI):**
- **P4-A** Real XIAO flash + I2S mic field test (T1.1 superplan). Manual on a board machine.
- **P4-B** Live Ollama `llava` vision path (P1-A/P0-B end-to-end on-device). Needs the box.
- **P4-C** Physical BLE connect tests: COLMI R02, OpenGlass, G2, Omi (mocked today).

**P5 (polish / reach):**
- **P5-A** Plugin marketplace: actually fetch + validate an index from `plugin_index_url` (offline-safe stub exists).
- **P5-B** Teleprompter paging on the larger screen (multi-page, scroll wheel).
- **P5-C** Themed color profiles for the ST7735 (green/amber/white) selectable in SETTINGS.

## 4. Evaluation — project health

**Strengths**
- Triple-codebase drift is actively prevented: protocol is byte-accurate across C/Python/Kotlin with shared tests; health has a single source of truth (`build_health`); G2 layout parity enforced between `device/g2_layout.py` and `g2-plugin/main.js`.
- Hardware is de-risked headlessly: firmware logic is host-gated (`g++`), UX is simulatable (`HudSim` decodes the real wire frames), so D1 (never flashes) and D5 (no daily loop) are mitigated before silicon arrives.
- Consent/privacy is first-class (P0-D) and gates all recording surfaces.
- Local-first by default (P1-B) — no silent cloud calls.

**Weaknesses / risks**
- **Pre-existing Android edits** (resolved — no longer in tree).
- **No local Kotlin compile** — Android correctness rests on CI only. JVM port parity checks exist for `RingProto` but not for `MainActivity`/`RingActivity` logic.
- **`St7735Screen::begin()` init is unverified against the real module** (see §2.3.1). Will need the board to confirm.
- **`c459b` backup** of the tree is still blocked (drive unmounted/degraded). No off-box snapshot since.

**Death modes still open (from `docs/31-repremortem-competition.md`)**
- D2 power: mitigated by `sleep_after`/backlight plan, not yet confirmed on TFT.
- D3 privacy: addressed by Consent Mode; remains to verify camera/omi truly no-op when off.
- D4 drift: addressed; keep the parity tests green.
- D8 context loss: addressed by `brain/context.py` + memory persist.

## 5. Next concrete steps (this session — completed)
1. ✅ Dead config removed (`hermes_home` from `AgentConfig`).
2. ✅ Ruff lint baseline established (F841/F811, import sort, format).
3. ✅ Remaining ruff issues fixed (E741, F541, F821, F401, E402) — 0 errors.
4. ✅ Stale branches cleaned.
5. ✅ Plan.md updated to reflect current repo layout.

## 6. Repo layout (as of 2026-07-11)
**Updated:** the inner repo `/home/gio/cyclops` (branch `main`, remote `cyclops-wearable.git`) is now the canonical app repo. ALL app code lives here: firmware + agent + android + cad + docs.
The meta-repo `/home/gio` (branch `cyclops`, remote `ayu.git`) holds AGENTS.md, skills, kanban, and infra ONLY — no app code.

**CI gate:** GitHub Actions builds firmware + python + APK. No local Android SDK needed.

**Ruff baseline:** blacked-in with `.git-blame-ignore-revs`. Run `ruff check .` and `ruff format .` before committing.
