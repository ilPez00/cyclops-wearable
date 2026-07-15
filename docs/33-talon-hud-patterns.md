# Talon/HUD-inspired Plan: 4 Patterns for Cyclops

**Source**: talon_hud, talon-ai-tools, MIRAGE, talonvoice.com  
**Target**: Cyclops firmware (`firmware/lib/cyclops_shared/include/hud.h` + `brain/context.py`)

## Current state
- `toast(msg, ttl=2)` — single slot, overwritten by next call, auto-clears after N seconds
- `add_note(t)` — appends to 12-slot ring buffer (FIFO after 12), NO TTL, NO auto-clear
- `notes[MAX_NOTES][NCOLS+1]` — 12 lines of 23 chars, no metadata (type, age, priority)
- `Hud::tick_sec()` — decrements `toast_ttl`, does NOT touch notes
- `agent` context in `brain/context.py` — appends freeform prose, not structured blocks

## P1 — Notification ring buffer with auto-clear (highest ROI)

### What
Replace the flat `notes[]` array with a proper ring buffer of `NoteSlot` structs:
```cpp
struct NoteSlot {
    char text[NCOLS+1];
    uint8_t ttl;      // seconds remaining; 0 = permanent
    uint8_t kind;     // NOTE_INFO=0, NOTE_WARN=1, NOTE_ERR=2, NOTE_SUCCESS=3
};
NoteSlot ring[RING_SIZE];   // RING_SIZE = 8 or 12
uint8_t ring_wp = 0;        // write pointer (circular)
uint8_t ring_count = 0;
```

### Changes
1. **`hud.h`** — Replace `notes[MAX_NOTES][NCOLS+1]` with `NoteSlot ring[RING_SIZE]`. Rewrite `add_note()` → `notify(text, kind, ttl)`. Add `tick_sec()` ring decrement: each tick, `if (ring[i].ttl > 0) if (--ring[i].ttl == 0) remove it`.
2. **`draw_notes()`** — iterate ring oldest-first, skip expired, color icon by kind.
3. **`apply_display_cmd()`** — accept `{\"kind\":\"notify\",\"text\":\"...\",\"ttl\":N,\"kind\":N}`.
4. **`test_hud.cpp`** — add cases: push with TTL → auto-removed after N ticks; push 9 items → oldest evicted; push with kind → icon rendered.
5. **`hud.h` (shared copy)** — mirror the change.

### Effort: ~2h | UX impact: High

Messages don't get lost. Transient notifications (sent, error, recording started) auto-clear. Important messages (notes from agent) stay forever. Kind icons give visual priority.

---

## P2 — Choice menu via wheel-scroll (medium)

### What
Replace the current modal `CONFIRM_YES`/`CONFIRM_NO` with a dynamic choice list driven by the brain:
```json
{"kind":"choices","items":["Save note","Discard","Edit"],"callback":"note_save"}
```

### Changes
1. **`hud.h`** — Add `ChoiceItem choices[8]` + `choice_cb[32]` + `show_choices(items, n, cb)`. Wheel scrolls, select fires `MSG_CMD` with the callback text + index.
2. **`apply_display_cmd()`** — Parse `"choices"` block.
3. **`brain/hud_bridge.py`** — Handle `choice` callback, route to the right brain handler.
4. **`test_hud.cpp`** — Push 3 choices → wheel down → select fires correct cb.

### Effort: ~4h | UX impact: Medium

Replaces the binary confirm with multi-option interaction. Useful for: "Save as note / discard / retry", "What to do with this transcription?", "Which note to open?"

---

## P3 — Context prompt format standardization (low effort)

### What
Change `brain/context.py` from appending prose to emitting a labeled block:
```
=== LIVE CONTEXT ===
Flow Score: 73/100 (Flowing)
Active goals: 3
Last checkin: mood 7/10, energy 6/10
Ring: HR 72, SpO2 98%
Recent notes: 4 today
=== END CONTEXT ===
```

### Changes
1. **`brain/context.py`** — `ContextAssembler.render()` → delimited block with `=== LIVE CONTEXT ===` / `=== END CONTEXT ===` markers.
2. **`agent/loop.py`** — `_system_block()` strips any old context, appends the new one.
3. **Test** (`test_context.py`) — assert the block is present and parsable.

### Effort: ~1h | UX impact: Medium

When context is delimited with consistent markers, the LLM learns precisely where the live data starts and ends. Reduces hallucinated context boundaries.

---

## P4 — Status icon zone re-layout (low effort, visual polish)

### What
Organize the 21-char OLED banner into fixed semantic zones:
```
[BT][REC][##---] [notes:3] [72bpm]
 0    1    2        3         4
```

### Changes
1. **`hud.h`** — `draw_home()` renders zones: BLE icon (0‑2), recording flag (4‑7), progress bar (9‑14), note count (16‑20), heart rate (22‑26).
2. **`test_hud.cpp`** — Assert zone positions on the rendered row.

### Effort: ~1h | UX impact: Low

Nice-to-have polish. Already partially done — REC flag and battery exist. This formalizes the positions so everything doesn't get packed into a single `snprintf`.

---

## Implementation order

| # | Pattern | Effort | Depends on |
|---|---------|--------|-----------|
| 1 | Notification ring buffer | 2h | Nothing |
| 2 | Choice menu | 4h | P1 (uses same notify for feedback) |
| 3 | Context format | 1h | Nothing |
| 4 | Status icon zones | 1h | Nothing |

**P1 first**: highest ROI, smallest risk, foundational for P2.

---

## Verification

Each pattern follows the existing dual-gate pattern:
1. `cd firmware && make test` — C++ host gate asserts new behavior
2. `python3 tests/run_tests.py tests/test_*.py` — Python suite confirms bridge/brain integration
3. Ad-hoc verifier script per change

---

## Talon patterns explicitly NOT taken (and why)

| Talon pattern | Rejected because |
|---|---|
| Desktop screen overlay (HTML/overlay) | Cyclops is wearable, not desktop |
| `.talon` voice script language | Cyclops uses faster-whisper STT → agent |
| MIRAGE stereoscopic camera pipeline | Needs Jetson GPU, Cyclops is ESP32 |
| Eye tracking | No Tobii on Cyclops hardware |
| MQTT component bus | Handled by BLE MSG_CMD frames, lighter weight |
