# Cyclops — Plan Update: xiao_s3 Ingestion

Imported from `dev/xiao_s3` (19 XIAO ESP32-S3 projects). Skipped speaker output (phone speaker instead). See each source for proven patterns.

## Priority order

| # | Feature | Source | Effort | Status |
|---|---------|--------|--------|--------|
| 1 | Config portal | `XIAO_OpenAI/.../config_portal.h` | ~4h | **IN PROGRESS** |
| 2 | On-device VAD (energy gate) | `agtos-firmware` pattern | ~4h | pending |
| 3 | Power-saving (brownout, PSRAM, camera fallback) | `xiao-esp32s3-edge-ai` + `Complete-voice-and-vision-AI` | ~2h | pending |
| 4 | WiFi camera stream (MJPEG) | `xiao-esp32s3-edge-ai/main.cpp` | ~1d | pending |
| 5 | On-device vision (TFLite Micro gate) | `H-S-Codesign` | ~1-2d | last |

## 1. Config Portal — implementation plan

**Goal:** Replace SD-card `/wifi.txt` provisioning with a captive WiFi portal on first boot. User connects phone to `Cyclops-Setup-XXXX`, fills SSID/password/API keys in browser, device saves to NVS and restarts.

**Source:** `XIAO_OpenAI_complete_voice_and_vision_assistant/config_portal.h` (600 lines, production captive portal with WiFi scan, timezone select, personality config, factory reset)

**Integration into cyclops:**
- New file: `firmware/xiao/src/config_portal.h` — adapted from the OpenAI sketch
- Modified: `firmware/xiao/src/main.cpp` — portal init in `setup()` on first boot, config button in `loop()`
- Modified: `firmware/platformio.ini` — add WebServer + DNSServer deps

**Data to save** (to NVS / Preferences):
- `wifi_ssid`, `wifi_password`
- `openai_api_key` (or generic LLM key)
- `assistant_name`, `assistant_role`
- `timezone` (IANA name)
- `language` (TTS/STT language code)
- `consent` (default consent mode state)

**Portal enter triggers:**
1. First boot (no WiFi config found in NVS)
2. Factory reset: hold both BTN_A + BTN_B at boot (same as OpenAI sketch D2+D3)
3. Config mode: hold BTN_A + BTN_B for 3s in normal operation

## 2. On-device VAD

**Goal:** Avoid streaming silence over BLE. Energy-based RMS gate before ADPCM encode.

**Pattern:** `audio_trigger` in cyclops already detects loud sounds — extend it with a low-energy gate that skips `adpcm_encode_chunk` when RMS < threshold.

## 3. Power-saving

- `WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0)` in setup (from `xiao-esp32s3-edge-ai`)
- `psramFound()` → `ps_malloc` for camera buffers (from `Complete-voice-and-vision-AI`)
- Camera init fallback: VGA 20MHz → VGA 16MHz → QVGA (from same)

## 4. WiFi camera stream

- Add `/stream` (MJPEG) + `/snap` endpoints to `camera_capture.cpp`
- Reuse existing WiFi bring-up / teardown (60s idle timeout)

## 5. On-device vision

- TFLite Micro person/face gate before streaming to brain
- Reference: `H-S-Codesign` face recognition wrapper