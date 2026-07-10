# Cyclops — Premortem (field-failure analysis)

> **RECONSTRUCTED DOC** — original `docs/13-premortem.md` (2026-07-04) lost on
> corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `docs/20-premortem-integration.md` (the integration premortem, committed in
> the recovery tree) and `docs/00-superplan.md`. **[inferred]** = reconstructed.
>
> NOTE: the recovery tree already contains `20-premortem-integration.md` — a
> *software/integration* premortem (BLE topology, audio over BLE, protocol
> drift, etc.). The lost `13-premortem.md` was likely the **hardware/field**
> counterpart (what physically breaks when you wear it). This rebuild covers
> that hardware angle; the integration one survives in `20-`.

## 0. Premortem method

Assume it is 2026-09 and the Cyclops wearable is **flaky in the field**.
List the most likely *hardware/physical/field* causes. Software/integration
causes are covered in `20-premortem-integration.md`.

## 1. Power dies mid-day

**Likely:** Li-Po sags under ESP32 + screen + mic + ring BLE; XIAO browns
out; notes lost. **Mitigation:** keep draw < 300 mA; low-batt auto-sleep
(pending); show all three batteries (bead/ring/phone) on one screen
(premortem #8); auto-pause transcription at < 15%.

## 2. USB-C wiggle kills the tether

**Likely:** strain on the XIAO USB-C; brief disconnect → `CyclopsXIAO`
advertising restarts, phone must re-pair. **Mitigation:** untethered Li-Po
default for field use; reconnect watchdog + exponential backoff (premortem #1).

## 3. Screen burns in / OLED fade

**Likely:** static "Cyclops ready" on an SSD1306 for hours → burn-in.
**Mitigation:** idle auto-sleep (`screen_off` after `sleep_after` s of no
input); content swap; any input wakes (HUD/UX doc).

## 4. I2S mic noise / dropout

**Likely:** onboard MEMS mic picks up handling noise; loose pad; 16 kHz PCM
over classic BLE drops words (premortem #2). **Mitigation:** bead buffers +
compresses (Opus/ADPCM), streams MTU-sized chunks; brain tolerates gaps;
do NOT promise real-time on classic BLE.

## 5. Wheel/button corrosion or mis-wire

**Likely:** BTN_B put back on GPIO4 (== WHEEL_B) after a rewire → menu/back
broken. **Mitigation:** BTN_B = GPIO5 (verified free); wake on any input;
document the pin map (`12-wiring.md`) on every build.

## 6. Ring falls off / loses BLE

**Likely:** R02 is a loose epoxy ring; drops connection at ~1 m from phone.
**Mitigation:** phone is the BLE hub; reconnect watchdog; ring health stays on
phone unless exported (premortem #9). Acceptable on your own body only.

## 7. Heat in pocket enclosure

**Likely:** sealed pocket case traps heat → ESP32 throttles / Li-Po swells.
**Mitigation:** vented `enclosure/`; don't run transcribe continuously;
low-batt auto-sleep.

## 8. Water / sweat

**Likely:** XIAO + OLED are not IP-rated. **Mitigation:** enclosure with
gasket; or accept dev-grade and keep dry. Ring is sealed epoxy (fine).

## 9. Flash corruption on power loss

**Likely:** pulling USB during write bricks the XIAO sketch. **Mitigation:**
OTA/serial reflash is one command (`pio run -e xiao_* -t upload`); config is
on the phone/PC, not the device.

## Top 3 to vigilantly prevent (hardware)

1. Power budget < 300 mA + low-batt auto-sleep + 3-battery readout.
2. BTN_B on GPIO5 (never GPIO4); wake-on-any-input.
3. Untethered Li-Po default for field; reconnect watchdog for USB/BLE drops.

---
**[inferred — important]** `20-premortem-integration.md` is the *committed*
premortem (software/integration). The lost `13-premortem.md` I could not read,
so this rebuild targets the **hardware/field** angle that `20-` does not cover,
using the mitigations referenced there (premortem #1/#2/#8/#9) as anchors. The
specific failure list (§1–§9) is a **reasonable reconstruction** of what a
hardware premortem would contain, grounded in the project's known constraints
(< 300 mA, BTN_B bug, single BLE hub, OLED burn-in). Verify against the
original if recovered.
