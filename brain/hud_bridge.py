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
    HUD_KINDS,
    MSG_RING_GESTURE,
    build_hud,
)

# numeric id of MSG_CMD in the firmware protocol
MSG_CMD = 9
from .protocol import MSG as _MSG  # noqa: E402
from .transcriber import get_transcriber  # noqa: E402

# lifeOS sink: Cyclops maintains each user's lifeOS with extracted wearable notes.
# Single source of truth lives at /home/gio/vault/lifeos_sink.py; import it if
# present (home box), else this stays a no-op so production deploys aren't tied
# to the vault path.
try:
    import sys as _sys
    _VAULT = "/home/gio/vault"
    if _VAULT not in _sys.path:
        _sys.path.insert(0, _VAULT)
    from lifeos_sink import Cyclops as _CyclopsSink  # type: ignore
    _cyclops_sink = _CyclopsSink(_VAULT)
except Exception:  # pragma: no cover - optional integration
    _cyclops_sink = None

MSG_AUDIO_META = _MSG["AUDIO_META"]
MSG_AUDIO_CHUNK = _MSG["AUDIO_CHUNK"]
MSG_AUDIO_STOP = _MSG["AUDIO_STOP"]

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
    out = []
    for w in text.lower().split():
        out.append(_IT_TRANSLATE.get(w, w))
    return " ".join(out)


_MASK = 0xFF


class HudBridge:
    def __init__(self, sink, store=None, transcriber=None, health=None, agent=None, user_id="wearer"):
        self.sink = sink
        self.store = store
        self.user_id = user_id  # who this wearable serves (lifeOS target)
        # auto-select a real backend (whisper -> cloud -> stub) when none given
        self.trans = transcriber if transcriber is not None else get_transcriber("auto")
        self.health = health
        # agent core (cyclops.agent.loop.Agent) — wired by the server; None = stub
        self.agent = agent
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
        (progress / step ticks). Kind is a string like 'progress' or 'step'."""
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

    def push_hud(self, text):
        """Push a glanceable banner line to the wearable HUD (Omi/G2 style).

        Called by the server's /api/agent endpoint so the agent answer shows up
        on the glasses without the device initiating it.
        """
        banner = (text or "").split("\n", 1)[0][:40]
        self.last_banner = banner
        self.mode = "AGENT"
        self._emit_text("AGENT: " + banner)
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
            self._emit_text("SSH: $ " + (arg or "whoami"))
            return ("ssh", arg)
        if act == ACT_CONFIRM_YES:
            self._emit_text("CONFIRMED")
            return ("confirm_yes", None)
        if act == ACT_CONFIRM_NO:
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
            self._emit_hud(
                HUD_KINDS.index("agent"),
                [ln[:18] for ln in ans.split("\n") if ln][:4],
                more=len(ans) > 72,
            )
            return ("agent", ans)
        if act == ACT_AGENT_ABORT:
            self._emit_text("AGENT: aborted")
            return ("agent_abort", None)
        if act == ACT_PHOTO:
            # B-long path: capture a frame, analyze, speak the result back (TTS).
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
            self._st = 0
            self._got = 0
