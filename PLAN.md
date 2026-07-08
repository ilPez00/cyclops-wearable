# Cyclops Plan

## MVP (DONE - local-first, testable now)
1. Wire protocol (framing + CRC) .................... DONE
2. Device C++ codec + UI state machine ............. DONE (host-build verified)
3. Brain: stub/whisper transcriber .................. DONE
4. Smart-note extractor (rule-based) ................ DONE
5. Display sinks (local / g2 / console) ............. DONE
6. Input: wheel + buttons + gyro gestures ........... DONE
7. Battery monitor ................................. DONE
8. Persistence (JSONL + MD) ........................ DONE
9. Web dashboard (stdlib) .......................... DONE
10. Glasses (G2) + pebble variants ................. DONE

## Next (hardware / quality)
- Wire real I2S mic + I2C OLED on XIAO; flash and field-test.
- Real faster-whisper on-device or edge box; cloud adapter (OpenAI/Deepgram).
- LLM-based note extraction (replace rule engine behind same interface).
- BLE transport for G2 glasses + Omi phone app parity.
- Vibration motor feedback; low-battery auto-sleep.

## G2 / Omi feature gap (target)
| Feature             | Status |
|---------------------|--------|
| Glanceable text HUD | DONE (local + G2 sink) |
| Audio capture       | DONE (transport + stub) |
| Transcription       | DONE (stub; whisper/cloud pluggable) |
| Notifications       | DONE (NOTE frames -> display) |
| Smart notes/memory  | DONE (extractor) |
| Navigation/map      | TODO (needs GPS + maps) |
| Translation         | TODO (needs translate adapter) |
| Teleprompt          | TODO (script scroll mode) |
| Music control       | TODO |
| 24/7 recording      | TODO (battery + stream store) |
| Phone app parity    | PARTIAL (web dashboard) |
| Conversation search | TODO (index store) |
