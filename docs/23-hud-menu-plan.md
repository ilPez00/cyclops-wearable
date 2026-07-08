# Cyclops — HUD & Menu System (v4)

## Principle
The device is a THIN CLIENT. Heavy work (transcribe, translate, navigation, SSH,
camera, image analysis, LLM) runs on the phone/brain. The HUD:
  - navigates a menu,
  - triggers actions (sent as MSG_CMD over BLE/USB),
  - renders results the brain streams back (DISPLAY_CMD / HUD_FRAME).

## Navigation model (resolution-agnostic)
- Screen STACK (depth <= 4). Top frame is what's drawn.
- Inputs:
    wheel        -> move selection / scroll
    btnA tap     -> open / select / confirm
    btnA long    -> back (pop one level)
    btnB tap     -> toggle screen (power save)
    nod          -> quick-capture (push last transcript as note)
    shake        -> back / dismiss
    proximity    -> wake (arduino)
- Modes: HOME, MENU, NOTES, NOTE_DETAIL, TRANSCRIBE, TRANSLATE, HEALTH,
         TELEPROMPTER, NAV, CAMERA, IMAGE_ANALYSIS, SSH, SETTINGS, CONFIRM.

## Menu (MENU mode) -> action ids (MSG_CMD subtype)
  Notes          -> push NOTES
  Transcribe     -> start; phone begins STT; push TRANSCRIBE
  Translate      -> translate selected note; push TRANSLATE
  Health         -> push HEALTH (ring + bead)
  Navigate       -> push NAV (phone GPS -> dest)
  Teleprompter   -> push TELEPROMPTER (reads a script)
  Camera         -> request snapshot; push CAMERA (thumb placeholder + "cap...")
  Image Analyze  -> OCR/describe last shot; push IMAGE_ANALYSIS
  SSH            -> open remote terminal; push SSH
  Settings       -> push SETTINGS

## Data the Hud keeps (fits Uno 2KB)
  notes[12][23]            list (reuse)
  detail[256]              shared scroll buffer (detail/translate/analysis/ssh/camera)
  scroll_off               view offset into detail
  hr, spo2, ring_batt_mv, bead_batt_mv
  nav_dist_m, nav_heading, nav_label[24]
  tele_page                teleprompter page (4 lines)
  confirm_prompt[32], confirm_action   (LLM candidate approve/reject)
  rec_secs                 transcribe timer
  clock (from TIME_SYNC)

## Rendering
Hud::render(Screen&) draws the top-of-stack mode using Screen geometry. Status
bar (row 0): clock | REC/▮ | BT | batt. Mono panels white-on-black; ST7735
green-on-black, selected row inverted.

## Verification
- Host logic test (native pio): stack push/pop, menu select, confirm yes/no,
  teleprompter paging, note detail scroll, back via long-press. No display needed.
- pio run all 6 envs (compile) after rewiring mains to Hud.

## Out of scope (later)
Real BLE action handlers on phone, GPS integration, SSH transport, camera
driver. This pass = full HUD/menu shell + render + logic, wired to both MCUs.
