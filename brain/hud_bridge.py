"""HUD command bridge: fulfills the wearable's MSG_CMD actions locally.

The firmware Hud emits MSG_CMD {"a":<ACT_*>,"arg":"..."} over BLE/USB. This
module parses it and returns display frames (DISPLAY_CMD JSON / G2 HUD_FRAME)
to the sink (screen/glasses). Everything is local-first: transcribe via
StubTranscriber, translate via a tiny dict, camera/image via stubs. Swap in
faster-whisper / a real translator / a camera backend by replacing the handler.

Used both by:
  - app/server.py  (phone-side: receives BLE frames, fulfills, sends back)
  - tests         (headless: a fake transport)
"""

from __future__ import annotations

import json

from .hitl import get_gatebook
from .events import EventLog, seconds_since, utc_now
from .protocol import MSG, crc16_ccitt_false, encode
from .protocol_v2 import (
    ACT_AGENT,
    ACT_AGENT_ABORT,
    ACT_CAMERA,
    ACT_CONFIRM_NO,
    ACT_CONFIRM_YES,
    ACT_HEALTH,
    ACT_IMAGE_ANALYSIS,
    ACT_NAV,
    ACT_NOTES,
    ACT_PHOTO,
    ACT_SSH,
    ACT_TELEPROMPTER,
    ACT_TRANSCRIBE_START,
    ACT_TRANSLATE,
    ACT_VIDEO,
    ACT_VOICE_CMD,
    ACT_VOICE_NOTE,
    ACT_CHOICE_SELECT,
    ACT_WORLD_HOWTO,
    ACT_WORLD_LOOK,
    ACT_WORLD_PRICE,
    ACT_WORLD_READ,
    HUD_KINDS,
    MSG_RING_GESTURE,
    build_hud,
)

# numeric id of MSG_CMD in the firmware protocol
MSG_CMD = 9
from .protocol import MSG as _MSG  # noqa: E402
from .transcriber import get_transcriber  # noqa: E402

# lifeOS sink: Cyclops maintains each user's lifeOS with extracted wearable notes.
# Set CYCLOPS_VAULT env var to the vault directory (default: ~/.cyclops/vault).
# If the vault isn't available, this stays a no-op so production deploys aren't
# tied to a specific path.
try:
    import os as _os
    import sys as _sys
    _VAULT = _os.environ.get("CYCLOPS_VAULT", _os.path.expanduser("~/.cyclops/vault"))
    if _VAULT not in _sys.path:
        _sys.path.insert(0, _VAULT)
    from lifeos_sink import Cyclops as _CyclopsSink  # type: ignore
    _cyclops_sink = _CyclopsSink(_VAULT)
except Exception:  # pragma: no cover - optional integration
    _cyclops_sink = None

MSG_AUDIO_META = _MSG["AUDIO_META"]
MSG_AUDIO_CHUNK = _MSG["AUDIO_CHUNK"]
MSG_AUDIO_STOP = _MSG["AUDIO_STOP"]
# Wire type 8. COLLISION, on purpose documented: ACT_IMAGE_ANALYSIS is also 8.
# The two live in different namespaces (frame header type vs ACT id inside a v2
# CMD wrapper {"a":8}), but both can reach dispatch(). looks_like_status() is how
# a status body is told apart from an image-analysis argument — never the int.
MSG_STATUS = _MSG["STATUS"]

# Keys a MSG_STATUS body carries (firmware Hud::status_json). Used only to
# disambiguate from an ACT_IMAGE_ANALYSIS argument.
_STATUS_KEYS = ("t", "batt", "chg", "rec", "bt", "hr", "spo2", "mode", "pres",
                "pos", "recs", "bead", "toast")


def looks_like_status(arg) -> bool:
    """True when `arg` is a MSG_STATUS body rather than an ACT_* argument.

    ACT ids and wire types share one integer space (ACT_IMAGE_ANALYSIS == 8 ==
    MSG_STATUS), so a handler choice must never be made on the number alone: a
    status body is a JSON object carrying at least one status key, while an
    image-analysis argument is a note id or free text and parses as neither.
    """
    if isinstance(arg, dict):
        return any(k in arg for k in _STATUS_KEYS)
    try:
        d = json.loads(arg or "{}")
    except Exception:
        return False
    return isinstance(d, dict) and any(k in d for k in _STATUS_KEYS)

# --- tiny local stubs (replace with real backends) ---
_IT_TRANSLATE = {
    "ciao": "hello",
    "buongiorno": "good morning",
    "grazie": "thank you",
    "si": "yes",
    "no": "no",
    "note": "note",
    "riunione": "meeting",
    "g2": "g2",
}


def _translate(text):
    """Gesture translation entry point: local LLM (Ollama gemma3:4b) when the
    daemon is up, else the dict above. Never raises — a backend miss returns
    the source text and the caller (world.py) treats identity as no-op."""
    try:
        from .translator import get_translator

        return get_translator().translate(text)
    except Exception:
        out = []
        for w in text.lower().split():
            out.append(_IT_TRANSLATE.get(w, w))
        return " ".join(out)


_MASK = 0xFF


def _short(text: str, n: int = 22) -> str:
    """One OLED-sized fragment for the W9 wrist line (NCOLS = 23)."""
    t = (text or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


class HudBridge:
    def __init__(
        self, sink, store=None, transcriber=None, health=None, agent=None,
        vision=None, user_id="wearer", claims=None,
    ):
        self.sink = sink
        self.store = store
        self.user_id = user_id  # who this wearable serves (lifeOS target)
        # auto-select a real backend (whisper -> cloud -> stub) when none given
        self.trans = transcriber if transcriber is not None else get_transcriber("auto")
        self.health = health
        # agent core (cyclops.agent.loop.Agent) — wired by the server; None = stub
        self.agent = agent
        # vision_fn(image_b64, prompt) -> str — wired by the server from
        # agent/tools/vision.py; None = zero-photo memory (#1) stays a stub
        self.vision = vision
        self.tele_script = []
        self.ssh_lines = ["$ ", "cyclops@phone:~# "]
        self._last_detail = ""
        self._audio_buf = bytearray()
        self._audio_rate = 16000
        self._audio_bits = 16
        self._audio_codec = 0  # AUDIO_CODEC_PCM16; META byte[5] switches it
        self.last_banner = ""  # last glanceable line, surfaced at /api/status
        self.mode = "HOME"  # HOME | AGENT | REC — drives the HUD mirror
        self.recording = False
        self.last_gesture = None
        # docs/43 C5: newest MSG_STATUS frame (device -> brain). The firmware
        # reports battery/mode/rec/presence/posture in it; before this the app
        # had no way to see presence or posture at all -- they were emitted into
        # the void.
        self.last_status: dict = {}
        self._presence: bool | None = None   # last pres bit seen (None = unknown)
        self._presence_ts: str = ""          # when the current presence began
        # belief layer (34 Phase 2). None -> W9 claim surfacing is a no-op,
        # which keeps the bridge usable without a claims store.
        self.claims = claims

    # ---- docs/43 C5: device status frames + presence claim boundaries -----

    def handle_status(self, arg):
        """MSG_STATUS (t=8) -> last_status, plus an Event on a presence edge.

        docs/34 §5c: an off-body transition is a CLAIM BOUNDARY, not a silent
        sensor gap -- the ledger should show "on-body" ending, with how long it
        lasted. The firmware already force-stops capture and drops consent; this
        makes the gap auditable instead of invisible.
        """
        try:
            d = json.loads(arg or "{}")
        except Exception:
            return ("status", "bad json")
        if not isinstance(d, dict):
            return ("status", "bad json")
        self.last_status = d
        if "pres" in d:
            on_body = bool(d.get("pres", 1))
            if self._presence is None:
                self._presence = on_body
                self._presence_ts = utc_now()
            elif on_body != self._presence:
                now = utc_now()
                dur = seconds_since(self._presence_ts, now)
                try:
                    EventLog().append(
                        kind="presence",
                        body="on-body" if self._presence else "off-body",
                        duration_s=dur, source="wearable",
                        locator="ble:status", ts=now,
                    )
                except Exception:
                    pass  # the ledger must never break a status frame
                self._presence = on_body
                self._presence_ts = now
        return ("status", d)

    # ---- W9: contradiction on the wrist ---------------------------------

    def note_claim(self, statement: str, evidence: list[str] | None = None):
        """Assert a claim through the belief layer. When it SUPERSEDES an
        older claim, surface the disagreement on the wearable as one line and
        open a HITL gate: A-single = newer holds, B-single = older holds.
        Returns (action, claim) or (None, None) when no claims store is wired."""
        if self.claims is None:
            return (None, None)
        claim, action = self.claims.assert_claim(statement, evidence=evidence)
        if action == "superseded":
            old = self.claims.latest_supersede()
            if old:
                line = f"{_short(old['old_statement'])} vs {_short(old['new_statement'])}"
                self.last_banner = line
                self._emit_text("WHICH HOLDS?  A=new  B=old\n" + line)
                try:
                    from .hitl import get_gatebook

                    gb = get_gatebook()
                    already = any(
                        g.action == "contradiction" and g.arg == old["old_id"]
                        for g in gb.pending()
                    )
                    if not already:
                        gb.request("contradiction", old["old_id"])
                except Exception:
                    pass
        return (action, claim)

    def digest_lines(self, n: int = 3) -> list[str]:
        """Claims-driven digest (docs/41 §1, docs/42 vision): top-confidence
        active claims as glanceable lines for the OLED DIGEST row.
        Empty when no claims store is wired."""
        if self.claims is None:
            return []
        top = sorted(self.claims.active(),
                     key=lambda c: c.confidence, reverse=True)[:n]
        return [_short(c.statement, 40) for c in top]

    def push_digest(self, cite: str = "") -> str:
        """Emit the digest's top line as a wrist row (docs/42 DIGEST slot).

        Glanceable, cited when a claim id is known: `cite` rides the row so
        the wrist shows the evidence id, never bare prose. Returns the row
        (\"\" when there is nothing to say — caller keeps the old DIGEST)."""
        lines = self.digest_lines(1)
        if not lines:
            return ""
        tag = f" [{cite}]" if cite else ""
        row = _short(lines[0], 22 - len(tag)) + tag
        self._emit_text(row)
        self.last_banner = row
        return row

    def resolve_contradiction(self, keep_new: bool):
        """W9 resolution from the wrist (A=new / B=old). Reverts cleanly when
        the older claim wins; both evidence sets survive either way."""
        if self.claims is None:
            return None
        old = self.claims.latest_supersede()
        if not old:
            return None
        got = self.claims.resolve_supersede(old["old_id"], keep_new=keep_new)
        # close the W9 gate this contradiction opened, so it stops surfacing
        try:
            from .hitl import get_gatebook

            gb = get_gatebook()
            for g in gb.pending():
                if g.action == "contradiction":
                    gb.resolve(g.id, approved=keep_new)
        except Exception:
            pass
        self.last_banner = ("kept: " if keep_new else "reverted: ") + _short(
            (got.statement if got else old["new_statement"])
        )
        return got

    def _emit_text(self, text):
        if hasattr(self.sink, "render_text"):
            self.sink.render_text(text)
        else:
            self.sink.write(
                encode(
                    MSG["DISPLAY_CMD"],
                    json.dumps({"kind": "text", "data": text}).encode(),
                )
            )

    def _emit_hud(self, kind, lines, more=False):
        if hasattr(self.sink, "write"):
            self.sink.write(build_hud(kind, lines, more))
    def _emit_display_cmd(self, kind, **fields):
        """Emit a DISPLAY_CMD JSON the wearable parses into Hud state
        (progress / step ticks / choices / steps). Kind is a string."""
        obj = {"kind": kind}
        obj.update(fields)
        payload = json.dumps(obj).encode()
        if hasattr(self.sink, "write"):
            from .protocol import MSG

            self.sink.write(encode(MSG["DISPLAY_CMD"], payload))
        elif hasattr(self.sink, "render_text"):
            self.sink.render_text(json.dumps(obj))

    def _emit_tts(self, text):
        """Audio-out path: the answer is spoken by the phone (its own BT stack
        drives the user's earbuds). Emits a TTS frame the companion relays to
        its media/audio output. Falls back to a no-op if the sink can't speak."""
        if not text:
            return
        if hasattr(self.sink, "speak"):
            try:
                self.sink.speak(text)
                return
            except Exception:
                pass
        # emit a TTS frame the companion app recognizes
        if hasattr(self.sink, "write"):
            from .protocol import MSG

            try:
                self.sink.write(encode(MSG["TTS"], text.encode()))
            except Exception:
                pass

    def push_hud(self, text, cite: str = ""):
        """Push a glanceable banner line to the wearable HUD (Omi/G2 style).

        Called by the server's /api/agent endpoint so the agent answer shows up
        on the glasses without the device initiating it. `cite` is the
        claim/event id behind the answer (docs/42: no answer without a
        citation); it rides the banner so the wrist can show it.
        """
        banner = (text or "").split("\n", 1)[0][:40]
        self.last_banner = banner
        self.mode = "AGENT"
        tag = f" [{cite}]" if cite else ""
        self._emit_text("AGENT: " + banner + tag)
        self._emit_hud(
            HUD_KINDS.index("agent"),
            [ln[:18] for ln in (text or "").split("\n") if ln][:4],
            more=len(text or "") > 72,
        )

    def handle_cmd(self, payload):
        try:
            d = json.loads(payload.decode())
        except Exception:
            return None
        act = int(d.get("a", 0))
        arg = d.get("arg", "") or ""
        return self.dispatch(act, arg)

    def handle_gesture(self, payload):
        """Route a RING_GESTURE frame (G2 R1 / COLMI wheel) to HUD nav.

        The bridge doesn't run the firmware Hud, so it forwards the gesture as
        a nav intent to the device sink and returns the gesture name. `nod`
        toggles transcription via the normal dispatch path.
        """
        from .protocol_v2 import ACT_TRANSCRIBE_START, parse_ring_gesture

        g = parse_ring_gesture(payload)
        self.last_gesture = g["name"]
        if g["name"] == "nod":
            return self.dispatch(ACT_TRANSCRIBE_START, "")
        # forward nav gestures back to the device HUD
        blob = b"G" + bytes([g["code"]])
        if hasattr(self.sink, "write"):
            self.sink.write(blob)
        else:
            self.sink(blob)
        return g["name"]

    def handle_audio(self, typ, payload):
        """Accumulate audio from the device; transcribe on STOP.

        META byte[5] announces the codec (0=PCM16 raw, 1=IMA ADPCM — see
        brain/adpcm.py / firmware adpcm.h). ADPCM chunks are self-contained,
        so each is decoded to PCM16 on arrival and the buffer stays raw PCM
        for the transcriber either way. Older firmware sends a 5-byte META
        (no codec byte) and keeps the raw-PCM default.
        """
        if typ == MSG_AUDIO_META:
            if len(payload) >= 4:
                self._audio_bits = payload[0] | (payload[1] << 8)
                self._audio_rate = payload[2] | (payload[3] << 8)
            self._audio_codec = payload[5] if len(payload) >= 6 else 0
            return ("meta", (self._audio_rate, self._audio_bits))
        if typ == MSG_AUDIO_CHUNK:
            if self._audio_codec == 1:  # AUDIO_CODEC_ADPCM
                from .adpcm import decode_chunk

                self._audio_buf.extend(decode_chunk(bytes(payload)))
            else:
                self._audio_buf.extend(payload)
            return ("chunk", len(self._audio_buf))
        if typ == MSG_AUDIO_STOP:
            pcm = bytes(self._audio_buf)
            self._audio_buf = bytearray()
            txt = (
                self.trans.transcribe(pcm, self._audio_rate)
                if self.trans
                else "stub: heard something"
            )
            if self.store:
                from .extractor import get_extractor

                extr = getattr(self, "_extr", None) or get_extractor()
                for n in extr.extract(txt):
                    self.store.add(n)
            self._emit_text("TRANSCRIBE: " + txt[:120])
            return ("transcribed", txt)
        return (None, None)

    def dispatch(self, act, arg=""):
        if act == MSG_STATUS and looks_like_status(arg):
            # A status frame, not a command: record it (presence/posture ride it)
            # and never route it through the command handlers below. The guard is
            # required because ACT_IMAGE_ANALYSIS is also 8 — an image-analysis
            # argument falls through to its own handler instead.
            return self.handle_status(arg)
        if act == ACT_TRANSCRIBE_START:
            txt = (
                self.trans.transcribe(b"")
                if self.trans
                else "stub: meeting notes captured"
            )
            if self.store:
                from .extractor import extract

                for n in extract(txt):
                    self.store.add(n)
            self._emit_text("TRANSCRIBE: " + txt[:120])
            return ("transcribe", txt)
        if act == ACT_TRANSLATE:
            tr = _translate(arg or "")
            self._emit_text("TR: " + tr)
            return ("translate", tr)
        if act == ACT_HEALTH:
            if self.health:
                s = self.health.latest()
                line = (
                    ("HR %d SpO2 %d%% ring %dmV" % (s.hr, s.spo2, s.batt_mv))
                    if s
                    else "no ring data"
                )
            else:
                line = "HR -- SpO2 --% (stub)"
            self._emit_text(line)
            return ("health", line)
        if act == ACT_NAV:
            self._emit_text("NAV: dest set (stub)")
            return ("nav", "stub")
        if act == ACT_TELEPROMPTER:
            self.tele_script = [
                "Welcome to the demo.",
                "Scroll the wheel to advance.",
                "This is a local teleprompter.",
                "End of script.",
            ]
            self._emit_hud(
                HUD_KINDS.index("teleprompter"),
                [ln[:18] for ln in self.tele_script[:4]],
                more=len(self.tele_script) > 4,
            )
            return ("teleprompter", self.tele_script)
        if act == ACT_CAMERA:
            self._emit_text("CAM: capture requested (stub)")
            return ("camera", "stub")
        if act == ACT_IMAGE_ANALYSIS:
            self._emit_text("IMG: OCR/describe (stub)")
            return ("image_analysis", "stub")
        if act == ACT_SSH:
            # Remote command exec is gated, not run inline — the wearable/phone
            # must send ACT_CONFIRM_YES before this cmd actually fires. Same
            # never-auto-commit principle the app already applies to notes.
            gate = get_gatebook().request("ssh", arg or "whoami")
            self._emit_text("SSH: awaiting approval — $ " + gate.arg)
            return ("ssh_pending", gate.to_dict())
        if act == ACT_CONFIRM_YES:
            gate = get_gatebook().resolve_latest(True)
            if gate is not None:
                self._emit_text("APPROVED: " + gate.action)
                return ("gate_approved", gate.to_dict())
            self._emit_text("CONFIRMED")
            return ("confirm_yes", None)
        if act == ACT_CONFIRM_NO:
            gate = get_gatebook().resolve_latest(False)
            if gate is not None:
                self._emit_text("REJECTED: " + gate.action)
                return ("gate_rejected", gate.to_dict())
            self._emit_text("CANCELLED")
            return ("confirm_no", None)
        if act == ACT_CHOICE_SELECT:
            # arg carries the callback tag the firmware was given via
            # show_choices(); route the selection to the agent/brain.
            cb = (arg or "").strip()
            self._emit_text("CHOICE: " + (cb or "(none)"))
            # a real backend would dispatch on cb (e.g. "note_save",
            # "note_discard"); here we surface it as an event.
            return ("choice_select", cb)
        if act == ACT_NOTES:
            n = len(self.store.all()) if self.store else 0
            if arg == "digest":
                # Claims-driven digest (docs/41 §1): top-confidence active
                # claims as glanceable lines. Deterministic — no oracle call.
                lines = self.digest_lines()
                self._emit_text("DIGEST: " + (" | ".join(lines) if lines else "(no active claims)"))
                return ("digest", lines)
            self._emit_text("NOTES: %d stored" % n)
            # maintain the wearer's lifeOS with the latest extracted notes
            if _cyclops_sink is not None and self.store:
                try:
                    for _nt in self.store.all()[-5:]:
                        _txt = _nt.get("text") if isinstance(_nt, dict) else str(_nt)
                        _typ = _nt.get("type", "note") if isinstance(_nt, dict) else "note"
                        _cyclops_sink.sync_note(self.user_id or "wearer", _txt, type=_typ)
                except Exception:
                    pass  # sink failures must never break the command bridge
            return ("notes", None)
        if act == ACT_AGENT:
            prompt = arg or ""
            if not prompt:
                self._emit_text("AGENT: no prompt")
                return ("agent", None)
            if self.agent is None:
                ans = "(stub) agent would answer: " + prompt
            else:
                # stream live progress + tool-step ticks to the wearable HUD
                def _on_step(tool, pct):
                    if tool:
                        self._emit_text("  · " + tool)
                        self._emit_display_cmd("step", tool=tool)
                    self._emit_display_cmd("progress", p=pct)

                self.agent.progress_cb = _on_step
                res = self.agent.run(prompt)
                self.agent.progress_cb = None
                ans = res.text or "(no response)"
                # surface tool steps as a secondary frame if any
                if res.steps:
                    self._emit_text("  · " + "; ".join(s["tool"] for s in res.steps))
            # glanceable banner = first line of the answer (Omi/G2 HUD style)
            banner = ans.split("\n", 1)[0][:40]
            self._emit_text("AGENT: " + banner)
            from .protocol_v2 import build_hud_agent

            if hasattr(self.sink, "write"):
                self.sink.write(build_hud_agent(ans, more=len(ans) > 72))
            return ("agent", ans)
        if act == ACT_AGENT_ABORT:
            self._emit_text("AGENT: aborted")
            return ("agent_abort", None)
        if act == ACT_PHOTO:
            # arg is the wearable's announced capture URL (camera_capture.h)
            # once wired end-to-end; "" means no wifi.txt / camera failed on
            # the device side. Tag-and-discard (#1) only runs when both a
            # real URL and a vision backend are wired — otherwise stays the
            # same stub behavior tests already expect.
            if arg and self.vision:
                from .sightings import capture_and_tag

                entry = capture_and_tag(arg, self.vision)
                line = f"PHOTO: {entry['tags']}" if entry else "PHOTO: capture/tag failed"
                # Capture→belief (docs/41 §1): tags reinforce a matching
                # active claim only — photos never auto-claim.
                if entry and entry.get("tags") and self.claims is not None:
                    from .claims import REINFORCE, similarity

                    tags = entry["tags"]
                    if any(similarity(tags, c.statement) >= REINFORCE
                           for c in self.claims.active()):
                        self.note_claim(tags, evidence=["photo:" + (arg or "")])
            else:
                line = "PHOTO: captured (stub)"
            self._emit_text(line)
            self._emit_tts("Photo captured.")
            return ("photo", line)
        if act == ACT_VIDEO:
            line = "VIDEO: toggle (stub)"
            self._emit_text(line)
            self._emit_tts("Video recording toggled.")
            return ("video", line)
        if act == ACT_VOICE_NOTE:
            # B-double: record a clip, transcribe, store, TTS a short ack.
            txt = self.trans.transcribe(b"") if self.trans else "stub: voice note"
            if self.store:
                from .extractor import extract

                for n in extract(txt):
                    self.store.add(n)
            # Capture→belief (docs/41 §1): a spoken question becomes a claim,
            # the transcript its evidence. Statements stay notes-only.
            if txt.strip().endswith("?") and self.claims is not None:
                self.note_claim(txt.strip(), evidence=["vnote:" + txt.strip()[:40]])
            self._emit_text("VNOTE: " + txt[:120])
            self._emit_tts("Voice note saved.")
            return ("voice_note", txt)
        if act == ACT_VOICE_CMD:
            # B-long: spoken question -> agent -> spoken answer (interactive).
            q = self.trans.transcribe(b"") if self.trans else "stub: what time is it"
            self._emit_text("YOU: " + q[:80])
            res = self.dispatch(ACT_AGENT, q)
            ans = res[1] if isinstance(res, tuple) else None
            if ans:
                self._emit_tts(ans.split("\n", 1)[0][:200])
            return ("voice_cmd", ans)
        if act in (ACT_WORLD_LOOK, ACT_WORLD_READ, ACT_WORLD_PRICE, ACT_WORLD_HOWTO):
            # Bridge-to-world: one gesture asks about the physical scene.
            # arg is a short registry tag ("menu", "sign", ...); registry
            # hits win, else live vision on the current frame, else honest
            # miss. Bytes are never persisted (sightings privacy design).
            # W6: READ also translates (read-then-translate, one gesture).
            from .world import answer_world

            tier, text = answer_world(act, arg or "", vision_fn=self.vision,
                                      translate_fn=_translate if act == ACT_WORLD_READ else None)
            # W4: HOWTO answers from any tier become a step overlay the OLED
            # walks (tilt + A-confirm); other acts stay single-line text.
            if act == ACT_WORLD_HOWTO and tier != "miss":
                from .world import split_steps

                steps = split_steps(text.split("\nTR:", 1)[0].split(": ", 1)[-1]
                                    if ": " in text else text)
                self._emit_display_cmd("steps", items=steps)
                return ("world_howto", {"tier": tier, "steps": steps})
            self._emit_text(text[:120])
            if tier != "miss":
                self._emit_tts(text[:200])
            return ("world", {"tier": tier, "text": text})
        return (None, None)


class FrameReceiver:
    """Phone-side glue: feeds a byte stream (USB-serial / BLE) of v2 frames
    into a HudBridge. Stateless decoder mirrors the firmware FrameDecoder."""

    def __init__(self, bridge):
        self.br = bridge
        self._st = 0
        self._len = 0
        self._got = 0
        self._type = 0
        self._crc = 0
        self._buf = bytearray(1024)

    def feed(self, chunk):
        for b in chunk:
            self._push(b)

    def _push(self, b):
        if self._st == 0:
            if b == 0xAA:
                self._st = 1
        elif self._st == 1:
            self._st = 1 if b == 0xAA else (2 if b == 0x55 else 0)
        elif self._st == 2:
            self._len = b
            self._st = 3
        elif self._st == 3:
            self._len = self._len | (b << 8)
            self._got = 0
            self._st = 4
        elif self._st == 4:
            if self._len > len(self._buf) - 3:
                # frame larger than buffer: reject and resync on next preamble
                self._st = 0
                self._got = 0
                return
            self._type = b
            self._buf[0] = self._len & _MASK
            self._buf[1] = (self._len >> 8) & _MASK
            self._buf[2] = b
            self._got = 3
            self._st = 5 if self._len else 6
        elif self._st == 5:
            self._buf[self._got] = b
            self._got += 1
            if self._got - 3 >= self._len:
                self._st = 6
        elif self._st == 6:
            self._crc = b
            self._st = 7
        elif self._st == 7:
            crc = self._crc | (b << 8)
            if crc == crc16_ccitt_false(bytes(self._buf[: self._got])):
                if self._type == MSG_CMD:
                    self.br.handle_cmd(bytes(self._buf[3 : 3 + self._len]))
                elif self._type in (MSG_AUDIO_META, MSG_AUDIO_CHUNK, MSG_AUDIO_STOP):
                    self.br.handle_audio(
                        self._type, bytes(self._buf[3 : 3 + self._len])
                    )
                elif self._type == MSG_RING_GESTURE:
                    self.br.handle_gesture(bytes(self._buf[3 : 3 + self._len]))
                elif self._type == MSG_STATUS:
                    # Status frames used to be dropped here, so presence/posture
                    # never reached the brain (docs/43 C5).
                    self.br.handle_status(
                        bytes(self._buf[3 : 3 + self._len]).decode("utf-8", "replace")
                    )
            self._st = 0
            self._got = 0
