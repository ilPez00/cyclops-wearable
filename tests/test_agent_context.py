"""Offline: wire fused context into the agent loop + context tool (P2-B).

Verifies the live ContextAssembler is injected into the agent's system block
and exposed via the `context` tool, without needing a live model/router.
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.config import AgentConfig
from agent.loop import Agent
from agent.tools import build_registry
from brain.context import ContextAssembler
from brain.extractor import extract
from device.health_fuse import HealthAggregator


def test_agent_injects_fused_context():
    notes = extract("Remind me to ship by friday. Decision: go local-first.")
    agg = HealthAggregator().from_colmi(hr=71, spo2=99, battery=92, ts=1)
    cp = tempfile.mktemp(suffix=".jsonl")
    open(cp, "w").write(json.dumps({"title": "Demo", "start": "2026-07-20"}) + "\n")
    asm = ContextAssembler().add_notes(notes).set_health(agg).load_calendar(cp)
    ag = Agent(AgentConfig(), context=asm)
    block = ag._system_block()
    assert "LIVE CONTEXT" in block
    assert "hr=71" in block and "Demo" in block and "Ship by friday" in block
    os.remove(cp)
    print("OK agent system block contains fused context")


def test_agent_without_context_is_fine():
    ag = Agent(AgentConfig())  # no context wired
    assert "LIVE CONTEXT" not in ag._system_block()
    print("OK agent without context emits no fused block")


def test_context_tool_registered_and_reports():
    asm = ContextAssembler().set_health(
        HealthAggregator().from_colmi(hr=68, spo2=97, battery=80, ts=1))
    reg = build_registry(AgentConfig(), context_assembler=asm)
    assert "context" in reg.names()
    out = reg.run("context", {"action": "show"})
    assert "hr=68" in out
    print("OK context tool registered + reports fused health:", repr(out))


if __name__ == "__main__":
    test_agent_injects_fused_context()
    test_agent_without_context_is_fine()
    test_context_tool_registered_and_reports()
    print("PASS tests/test_agent_context.py")
