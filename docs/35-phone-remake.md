# docs/35 — The app remakes the phone

Companion to `docs/34-cyclops-as-computer.md`. Same principle, different
target: 34 remakes the brain (substrate, not pile). This one remakes the
**phone** — from a remote control with 14 screens into the computer the
wearable belongs to.

## The diagnosis

Today the phone is a thin client over LAN HTTP to a Python server on a PC:

- 14 activities, each a remote for one `/api/*` endpoint (`MainActivity`
  already documents this: "the phone-side equivalent of serve.sh + the web
  dashboard"). Feed, Transcript, Memory, Dreams, Entities, Experiences,
  Cost — seven views over one pile, the survey's chat-as-interface failure
  with extra steps.
- `CyclopsApi.kt` is 579 lines of GET/POST plumbing to reach a brain that
  could live on the phone itself. The whole class is accidental complexity
  from the client/server split, not from the product.
- The wearable talks to the phone over BLE (`CyclopsService` already pumps
  frames into a Kotlin `HudBridge`) — then the phone **forwards** the work
  to a PC over Wi-Fi, and shows the answer. Two hops where one suffices,
  and the product dies with the LAN.
- Seven browse-screens exist because retrieval is unmeasured (34 Phase 0).
  When nothing can answer "what was happening while X", you build a screen
  per pile and let the user browse. That is the tell.

The remake in one sentence: **the brain moves onto the phone; the ledger
becomes local; the PC becomes a peer, not the computer.**

## What moves, concretely

### 1. Brain on the phone (kills CyclopsApi-as-remote)

`CyclopsService` already exists as a foreground BLE hub with a Kotlin
`HudBridge` that fulfills MSG_CMD actions locally — transcribe, translate,
health, nav, camera, confirm. Today its transcriber/vision/store callbacks
are stubs and the real work round-trips to `app/server.py`. The move:

- Embed the pipeline in-process: audio chunks → on-device or on-phone-LLM
  transcribe → `events.py` ledger append → extractor → claims. The Python
  brain stays as the **heavy peer** (big models, Obsidian sync, dreams
  consolidation) reached over LAN when present, never required.
- `CyclopsApi` shrinks from remote client to local façade: same call sites,
  Room/SQLite answers instead of HTTP. The 25+ `/api/*` endpoints become
  internal queries; the LAN API keeps a small sync subset (see §4).
- Bootstrap dies with it: no baseUrl to type, no UDP discovery to run, no
  LAN token to paste. First launch pairs BLE and works. `BrainDiscovery`,
  the Settings URL field, and the token field become legacy paths, deleted
  in the phase gate (the Phase-0 dead-code audit runs here too).

### 2. Ledger on the phone (34 Phases 1–2, local-first)

The OBSERVE/BELIEVE layers from 34 land in Room, not on the PC:

- Events: wearable frames (already decoded in-process by `CyclopsProto`),
  phone-side captures (§3), agent tool calls. Same
  `{ts, duration, source, kind, body, locator}` primitive.
- Claims with evidence, contradiction/supersede rules, structure hash —
  ported logic, same gates. The model-swap probe (34 Phase 0c) runs
  on-device-LLM vs heavy-peer-LLM; if structure survives the swap, the
  phone is proven as a first-class believer, not a viewer.
- Sync is ledger sync (event rows + claim revisions, both append-only and
  therefore merge-trivial), never screen-scraping REST. The PC peer
  replays what it missed; either side can be offline for a week.

### 3. Phone as a sensor node (not a relay)

Today the phone has a mic, cameras, GPS, IMU, and a screen — and contributes
none of them to the ledger. It relays the XIAO's sensors and displays text.
The remake:

- Phone mic → same VAD-gated capture path as the wearable, `source: phone`.
  The "which mic heard it" question answers itself by provenance.
- Phone camera → zero-photo sightings locally (tag, discard bytes — the
  privacy design already proven in `brain/sightings.py`, no new policy
  needed).
- Phone GPS/IMU → presence and movement context the wearable's single IMU
  cannot give (walk vs ride vs still; which room by Wi-Fi).
- This is what makes the wearable dumber in a good way: the XIAO stays a
  2-button + tilt sensor node because the phone carries the sensors that
  need power and silicon.

### 4. Launcher surface (the phone behaves like the computer)

- **Timeline** (34 Phase 4a) becomes the home surface: events + claims in
  time order, contradictions as forks, grades inline. Replaces Feed,
  Transcript, Memory, Dreams, Entities, Experiences, Cost browsing.
- **Ask** stays as the convenience layer with cited answers (34 Phase 4b),
  and registers as the device assistant (Assist API): long-press power /
  "hey" goes to Ask-with-citations, not to a chat box over the pile.
- Wearable gestures route to phone actions, not server endpoints: A-double
  (photo) fires the *phone* camera pipeline; B-long (voice-cmd) fires
  on-device voice → ledger → act-check. The existing `bind()` remap grid
  already speaks action ids — the targets change from `/api/hud_cmd` to
  local intents.
- Widget shows next action / contradiction count (34 Phase 4d), already
  halfway there via `HudWidgetProvider`.
- Volume-key gate approval (`dispatchKeyEvent` in MainActivity) graduates
  into a system-level pattern: any HITL gate is answerable from the
  wearable buttons, the widget, or voice — never by opening screen #12.

### 5. Consent and secrets, phone-grade

- Premortem P2 (plaintext `~/.cyclops/`) has a phone-native answer:
  EncryptedSharedPreferences / Keystore for tokens and keys, biometric gate
  on export and on HITL approve. The server-side token file does not move
  to the phone as a string extra — it is replaced by pairing-bound auth.
- Presence off-body (firmware already force-stops capture) extends to the
  phone: no unlocked-phone mic capture without an explicit session, same
  fail-closed principle, logged as a claim boundary (34 Phase 5c).

## The bridge: from the computer to the real world

The phone remake makes the phone the computer. This section makes the
computer *matter*: Cyclops is the bridge from the phone to the physical
world in front of the wearer. The loop is the product:

**gesture → question → taught-or-seen answer → OLED + voice → ledger.**

- **One gesture, one question.** Four new actions (`ACT_WORLD_LOOK=24`,
  `READ=25`, `PRICE=26`, `HOWTO=27`, firmware `hud.h` + `protocol_v2.py` +
  Kotlin `HudBridge`) ask what is in front of the wearer: *what is this,
  read it, what does it cost, how do I use it.* arg carries a short tag
  ("menu", "sign", "price tag"). The OLED shows a thinking toast, pushes
  the AGENT view, and streams the answer back — same UX shape as voice-cmd.
- **Registry beats vision beats honest miss** (`brain/world.py`).
  A taught answer ("menu at Luigi's → today's risotto") always wins over
  a fresh vision guess; live vision runs only with a frame and a backend;
  otherwise the answer is "don't know yet — teach me", logged so a later
  entry answers it retroactively. No stub dressed as knowledge, ever.
- **Zero-photo, same as sightings.** Bytes are discarded; only tags and
  taught answers persist in `~/.cyclops/world.json`. The privacy design is
  inherited, not re-argued.
- **The World screen** (Android drawer, next to Chat) is the teaching
  surface: list, teach, and — by reading the miss log — see what the
  wearer asked that nobody taught yet. Every miss is a prompt to teach;
  every taught tag makes a gesture instant next time.
- **The cool loop, stated plainly:** point at a menu → double-tap → OLED
  reads the specials aloud. Point at a price tag → answer plus fair-deal
  judgement. Point at a machine → three steps to operate it. The phone
  never leaves the pocket; the world becomes the interface, and the
  computer is the bridge, not the destination.

## What explicitly does NOT happen

- **No rewrite of `app/server.py` in Kotlin.** The Python brain becomes the
  heavy peer with a shrinking sync API. Two implementations of belief logic
  is how you get two memories that disagree; the port is the ledger +
  rules (deterministic, testable), never the whole server.
- **No cloud account, no cloud sync.** Peer sync over LAN/USB only. An
  account would reintroduce the interpreter-as-memory failure through the
  back door (whoever hosts the sync owns the past).
- **No screenshot/screen-record capture.** The a11y-tree-first decision
  (34 Phase 1c) applies on Android too: UsageStats + Accessibility events,
  structured, event-driven — never pixels.
- **No new ontology.** Claims carry free-form statements + evidence links;
  structure is earned by the contradiction machinery, not authored up
  front (survey §3, third reject).

## Phases and gates

| phase | work | gate |
|---|---|---|
| A. Ledger local | Room schema for events + claims; BLE frames append directly; `CyclopsApi` reads local first, LAN fallback | airplane-mode week: capture + Timeline + Ask work with Wi-Fi off; every row has duration + locator |
| B. Brain on phone | on-device transcribe + extractor in-process; heavy peer used only when present | unplug the PC for a week; zero feature loss except big-model quality, measured not asserted |
| C. Phone as sensor | phone mic/camera/GPS/IMU as ledger sources with provenance | "which device heard/saw it" answered for every row; battery cost stated in mAh/day, not adjectives |
| D. Surface collapse | Timeline + Ask-with-citations + Devices + Settings; 14 → 4; Assist API registration | dogfood: any question answered twice without touching the ledger is a filed bug (34 Phase 4 gate) |
| E. Peer sync | append-only row/revision sync with the Python brain; conflict = both revisions kept, contradiction machinery resolves | either side offline a week, resync with zero loss and a Revision trail |

## Standing rules (same as 34, plus one)

1–6 from `docs/34-cyclops-as-computer.md` apply unchanged. Plus:

7. **The phone must work with no network, no PC, no account.** Any screen,
   capture, or answer that requires the LAN is a bug, not a limitation.
   (This is the phone-shaped form of "cost depends on the question, not
   the history" — dependence on infrastructure is the cost that kills
   wearables in the field.)

## Ten directions (in `docs/36-ten-directions.md`)

Senses (W1 voices, W2 sound events, W3 phone camera as second eye),
world depth (W4 procedural overlays, W5 price memory, W6 read-translate),
phone (W7 notification triage, W8 calendar loop), belief payoffs (W9
contradiction on the wrist, W10 morning briefing). Cross-group build
order: W4+W6, then W7+W8, then W1+W9, then W3+W5+W2+W10. No direction
starts until the 34/35 phase it extends is gated.
