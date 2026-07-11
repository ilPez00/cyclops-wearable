"""Offline: P1-B local-first pipeline enforcement.

Guarantees the offline default is enforced by policy, not by accident: under
local_first (default) with no API keys the pipeline uses the deterministic
offline stub; cloud is only reachable when explicitly opted in.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.config import AgentConfig
from brain.pipeline import resolve_mode_name, resolve_stt
from brain.transcriber import CloudTranscriber, StubTranscriber


def _clear_keys():
    for k in ("DEEPGRAM_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY",
              "OPENROUTER_API_KEY"):
        os.environ.pop(k, None)


def test_default_is_offline():
    _clear_keys()
    cfg = AgentConfig()  # local_first=True by default
    assert resolve_mode_name(cfg) == "offline"
    t = resolve_stt(cfg)
    assert isinstance(t, StubTranscriber)
    print("OK default config resolves offline (local-first)")


def test_local_first_blocks_implicit_cloud():
    _clear_keys()
    cfg = AgentConfig()
    cfg.local_first = True
    # even if a cloud key existed, local_first must NOT pick cloud implicitly
    os.environ["DEEPGRAM_API_KEY"] = "x"
    assert resolve_mode_name(cfg) == "offline"
    assert isinstance(resolve_stt(cfg), StubTranscriber)
    os.environ.pop("DEEPGRAM_API_KEY", None)
    print("OK local_first refuses implicit cloud even with a key present")


def test_explicit_cloud_allowed():
    _clear_keys()
    cfg = AgentConfig()
    cfg.inference_mode = "cloud"
    # with no real key the cloud builder still returns a CloudTranscriber
    # (it errors at call-time, not build-time) -> proves the policy picked cloud
    t = resolve_stt(cfg)
    assert isinstance(t, CloudTranscriber)
    print("OK explicit inference_mode=cloud selects cloud backend")


def test_local_mode_selects_local():
    _clear_keys()
    cfg = AgentConfig()
    cfg.local_mode = True
    assert resolve_mode_name(cfg) == "local"
    print("OK local_mode resolves to local")


def test_env_override():
    os.environ["CYCLOPS_LOCAL_FIRST"] = "0"
    cfg = AgentConfig.load(env=dict(os.environ))
    assert cfg.local_first is False
    os.environ.pop("CYCLOPS_LOCAL_FIRST", None)
    print("OK CYCLOPS_LOCAL_FIRST=0 overrides default")


if __name__ == "__main__":
    test_default_is_offline()
    test_local_first_blocks_implicit_cloud()
    test_explicit_cloud_allowed()
    test_local_mode_selects_local()
    test_env_override()
    print("PASS tests/test_pipeline.py")
