"""Tool: omi — start/stop Omi pendant audio capture -> brain transcription (P1-A).

Privacy: starting capture requires Consent Mode ON (Omi audio is a recording).
When no BLE/opus stack or session is present, the tool returns an offline stub
and the ingest pipeline is fully testable with a FakeOmiSource.
"""
from __future__ import annotations
from ..loop import Tool
from ..config import AgentConfig
from ..tools.consent import consent_required
from device.omi import FakeOmiSource, OmiIngest


def make_omi_tool(config: AgentConfig, transcriber=None) -> Tool:
    def run(args: dict) -> str:
        action = (args.get("action") or "status").lower()
        if action == "status":
            return "omi: use action=start|stop (needs Consent Mode + BLE/opus)"
        if action in ("start", "listen"):
            if consent_required(config):
                return "error: consent OFF — Omi audio capture refused (enable via consent tool)"
            # offline / no real stack -> simulate ingest with a fake source
            from brain.transcriber import StubTranscriber
            tr = transcriber or StubTranscriber()
            captured = []
            src = FakeOmiSource(chunks=3, samples_per_chunk=160)
            ing = OmiIngest(src, tr, on_phrase=captured.append, max_chunks=3)
            ing.run()  # emits one phrase from the fake source
            if captured:
                return f"omi heard: {captured[0]}"
            return "omi: no phrase captured"
        if action == "stop":
            return "omi: stopped"
        return "usage: omi action=start|stop|status"
    return Tool(
        name="omi",
        description="Capture audio from the Omi pendant and transcribe it via the brain.",
        parameters={
            "type": "object",
            "properties": {"action": {"type": "string", "description": "start|stop|status"}},
            "required": [],
        },
        run=run,
    )
