# docs/42 — Grand vision: the wearable is the computer

Status: target state (2026-09-19). One sentence: **your past becomes
queryable and your present becomes decidable, with the wearable as the
only surface you need** — cyclops + app, through physis, is the single
access point to computer, internet, and AI.

## Why this shape

A phone is 14 remotes over other people's computers. Cyclops inverts it:
the XIAO on your glasses observes (mic/cam/accel), the phone/app believes
(ledger + claims + physis memory), and acts (terminal/web/agent tools).
The model sits outside as a replaceable interpreter — swap it mid-phase
and the belief state must survive (docs/34 rule 5). Raw bytes never leave
the body without consent; only notes/claims cross the link, and only with
a confirm row for anything irreversible.

## The loop (capture → belief → digest)

1. **Capture with a question attached.** One gesture: A-double = photo +
   "what is this", B-double = voice note + spoken question, B-long =
   voice command. The question travels WITH the capture as the claim
   statement; the transcript/photo locator becomes evidence (docs/41 §1).
2. **Belief answers from the ledger with citations.** Claims (deterministic
   reinforce/supersede, bi-temporal) + physis memory + calendar/triage.
   No answer without a cited claim/event id — on the wrist too.
3. **Digest lands back on the OLED.** Top-confidence active claims + W7
   triage + W8 calendar-due, as glanceable lines. The wearer confirms
   from the wrist (A=new/B=old); the phone stays in the pocket.

## What the 4-row screen shows (128x32, 21x4)

```
row0  STATUS   12:04 BT+ RNBD 82%        clock + link + battery
row1  ANSWER   Meet Bob 3pm, bring      AI's last line (hud_line, big)
row2  DIGEST   * standup 14:30 office   next claim / calendar / triage
row3  HINT     A:ask B:note ~ tilt      affordance, or toast/REC/notif
```

Priorities: answer > digest > hint. Toasts, REC timer, consent-off, and
contradiction prompts ("WHICH HOLDS? A=new B=old") preempt row3, then
row2. Notifications show newest-active with a glyph (> info, * warn,
! err, + ok). Idle 8s → screen off (burn-in + battery); any input wakes.

MENU (tilt + A): Notes / Agent / Transcribe / Translate / Health /
Navigate / Teleprompter / Camera / ImageAnalyze / SSH / Settings / Back.
AGENT view streams the answer with progress ticks; CHOICE walks W4
procedure steps (tilt=move, A=done, B=back).

## Gates

- Dogfood week through capture → cited answer → confirmed act (docs/41).
- Airplane-mode week: capture + Timeline + Ask work with Wi-Fi off.
- Three on-wrist contradiction resolutions without opening the app.