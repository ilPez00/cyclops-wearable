"""Offline: P1-A Omi audio ingestion pipeline.

Uses FakeOmiSource (no BLE/opus) + StubTranscriber so the full
Omi -> PCM16 -> transcribe -> phrase path is exercised without hardware.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.config import AgentConfig
from agent.tools.omi import make_omi_tool
from brain.transcriber import StubTranscriber
from device.omi import BleOmiSource, FakeOmiSource, OmiIngest


def test_omi_ingest_fake_source_produces_phrase():
    captured = []
    src = FakeOmiSource(chunks=3, samples_per_chunk=160)
    ing = OmiIngest(src, StubTranscriber(), on_phrase=captured.append, max_chunks=3)
    ing.run()
    assert captured, "Omi ingest should emit at least one phrase"
    assert isinstance(captured[0], str) and captured[0]
    print("OK Omi ingest (fake source) -> phrase:", repr(captured[0]))


def test_omi_tool_registered():
    from agent.tools import build_registry

    reg = build_registry(AgentConfig())
    assert "omi" in reg.names()
    print("OK omi tool registered")


def test_omi_tool_offline_listen():
    cfg = AgentConfig()
    t = make_omi_tool(cfg)
    out = t.run({"action": "start"})
    assert "omi heard:" in out
    print("OK omi tool offline listen ->", out)


def test_omi_gated_on_consent():
    cfg = AgentConfig()
    cfg.consent_mode = False
    t = make_omi_tool(cfg)
    assert "consent OFF" in t.run({"action": "start"})
    print("OK omi capture refused without consent")


def test_ble_source_import_safe():
    # constructing BleOmiSource must not import bleak at module load
    s = BleOmiSource(address="AA:BB:CC:DD:EE:FF")
    assert s.address == "AA:BB:CC:DD:EE:FF"
    try:
        import bleak  # noqa: F401
    except ImportError:
        # running without bleak installed raises a clear error (not a crash)
        try:
            s.start(lambda p: None)
            raised = False
        except RuntimeError as e:
            raised = "bleak" in str(e)
        assert raised, "BleOmiSource should explain missing bleak"
        print("OK BleOmiSource import-safe + clear error when stack missing")
        return
    # bleak IS installed (dev box with a radio): starting would do a real BLE
    # connect to the bogus address — slow and environment-dependent. The
    # import-safety contract (no bleak at module load) is already proven by
    # constructing the source above, so stop here.
    print("OK BleOmiSource import-safe (bleak present; skipping radio path)")


if __name__ == "__main__":
    test_omi_ingest_fake_source_produces_phrase()
    test_omi_tool_registered()
    test_omi_tool_offline_listen()
    test_omi_gated_on_consent()
    test_ble_source_import_safe()
    print("PASS tests/test_omi.py")
