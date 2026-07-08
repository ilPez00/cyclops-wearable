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
import json, time
from .protocol import encode, MSG
from .protocol_v2 import (parse_hud, build_hud, MSG_HUD_FRAME, HUD_KINDS,
                          ACT_TRANSCRIBE_START, ACT_TRANSLATE, ACT_HEALTH,
                          ACT_NAV, ACT_TELEPROMPTER, ACT_CAMERA,
                          ACT_IMAGE_ANALYSIS, ACT_SSH, ACT_CONFIRM_YES,
                          ACT_CONFIRM_NO, ACT_NOTES, ACT_AGENT, ACT_AGENT_ABORT,
                          build_hud_agent)

# numeric id of MSG_CMD in the firmware protocol
MSG_CMD = 9
from .protocol import MSG as _MSG
from .transcriber import get_transcriber
MSG_AUDIO_META = _MSG["AUDIO_META"]
MSG_AUDIO_CHUNK = _MSG["AUDIO_CHUNK"]
MSG_AUDIO_STOP = _MSG["AUDIO_STOP"]

# --- tiny local stubs (replace with real backends) ---
_IT_TRANSLATE = {"ciao": "hello", "buongiorno": "good morning", "grazie": "thank you",
                 "si": "yes", "no": "no", "note": "note", "riunione": "meeting", "g2": "g2"}

def _translate(text):
    out = []
    for w in text.lower().split():
        out.append(_IT_TRANSLATE.get(w, w))
    return " ".join(out)

_MASK = 0xFF

class HudBridge:
    def __init__(self, sink, store=None, transcriber=None, health=None, agent=None):
        self.sink = sink
        self.store = store
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

    def _emit_text(self, text):
        if hasattr(self.sink, "render_text"):
            self.sink.render_text(text)
        else:
            self.sink.write(encode(MSG["DISPLAY_CMD"], json.dumps({"kind": "text", "data": text}).encode()))

    def _emit_hud(self, kind, lines, more=False):
        if hasattr(self.sink, "write"):
            self.sink.write(build_hud(kind, lines, more))

    def push_hud(self, text):
        """Push a glanceable banner line to the wearable HUD (Omi/G2 style).

        Called by the server's /api/agent endpoint so the agent answer shows up
        on the glasses without the device initiating it.
        """
        banner = (text or "").split("\n", 1)[0][:40]
        self._emit_text("AGENT: " + banner)
        self._emit_hud(HUD_KINDS.index("agent"),
                       [l[:18] for l in (text or "").split("\n") if l][:4], more=len(text or "") > 72)

    def handle_cmd(self, payload):
        try:
            d = json.loads(payload.decode())
        except Exception:
            return None
        act = int(d.get("a", 0)); arg = d.get("arg", "") or ""
        return self.dispatch(act, arg)

    def handle_audio(self, typ, payload):
        """Accumulate PCM from the device; transcribe on STOP."""
        if typ == MSG_AUDIO_META:
            if len(payload) >= 4:
                self._audio_bits = payload[0] | (payload[1] << 8)
                self._audio_rate = payload[2] | (payload[3] << 8)
            return ("meta", (self._audio_rate, self._audio_bits))
        if typ == MSG_AUDIO_CHUNK:
            self._audio_buf.extend(payload)
            return ("chunk", len(self._audio_buf))
        if typ == MSG_AUDIO_STOP:
            pcm = bytes(self._audio_buf); self._audio_buf = bytearray()
            txt = self.trans.transcribe(pcm, self._audio_rate) if self.trans else "stub: heard something"
            if self.store:
                from .extractor import get_extractor
                extr = getattr(self, '_extr', None) or get_extractor()
                for n in extr.extract(txt):
                    self.store.add(n)
            self._emit_text("TRANSCRIBE: " + txt[:120])
            return ("transcribed", txt)
        return (None, None)

        try:
            d = json.loads(payload.decode())
        except Exception:
            return None
        act = int(d.get("a", 0)); arg = d.get("arg", "") or ""
        return self.dispatch(act, arg)

    def dispatch(self, act, arg=""):
        if act == ACT_TRANSCRIBE_START:
            txt = self.trans.transcribe(b"") if self.trans else "stub: meeting notes captured"
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
                line = ("HR %d SpO2 %d%% ring %dmV" % (s.hr, s.spo2, s.batt_mv)) if s else "no ring data"
            else:
                line = "HR -- SpO2 --% (stub)"
            self._emit_text(line)
            return ("health", line)
        if act == ACT_NAV:
            self._emit_text("NAV: dest set (stub)")
            return ("nav", "stub")
        if act == ACT_TELEPROMPTER:
            self.tele_script = ["Welcome to the demo.", "Scroll the wheel to advance.",
                                "This is a local teleprompter.", "End of script."]
            self._emit_hud(HUD_KINDS.index("teleprompter"),
                           [l[:18] for l in self.tele_script[:4]], more=len(self.tele_script) > 4)
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
        if act == ACT_NOTES:
            if self.store:
                self._emit_text("NOTES: %d stored" % len(self.store.all()))
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
                    self._emit_hud(HUD_KINDS.index("agent"),
                                   ["…" + str(pct) + "%"], more=True)
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
            self._emit_hud(HUD_KINDS.index("agent"), [l[:18] for l in ans.split("\n") if l][:4], more=len(ans) > 72)
            return ("agent", ans)
        if act == ACT_AGENT_ABORT:
            self._emit_text("AGENT: aborted")
            return ("agent_abort", None)
        return (None, None)


class FrameReceiver:
    """Phone-side glue: feeds a byte stream (USB-serial / BLE) of v2 frames
    into a HudBridge. Stateless decoder mirrors the firmware FrameDecoder."""
    def __init__(self, bridge):
        self.br = bridge
        self._st = 0; self._len = 0; self._got = 0; self._type = 0
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
            self._len = b; self._st = 3
        elif self._st == 3:
            self._len = self._len | (b << 8); self._got = 0; self._st = 4
        elif self._st == 4:
            self._type = b
            self._buf[0] = self._len & _MASK
            self._buf[1] = (self._len >> 8) & _MASK
            self._buf[2] = b
            self._got = 3
            self._st = 5 if self._len else 6
        elif self._st == 5:
            if self._got < len(self._buf):
                self._buf[self._got] = b
            self._got += 1
            if self._got - 3 >= self._len:
                self._st = 6
        elif self._st == 6:
            self._st = 7
        elif self._st == 7:
            if self._type == MSG_CMD:
                self.br.handle_cmd(bytes(self._buf[3:3 + self._len]))
            elif self._type in (MSG_AUDIO_META, MSG_AUDIO_CHUNK, MSG_AUDIO_STOP):
                self.br.handle_audio(self._type, bytes(self._buf[3:3 + self._len]))
            self._st = 0; self._got = 0
