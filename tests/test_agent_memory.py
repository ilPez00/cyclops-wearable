"""Offline: agent memory persists + recalls across turns (T3.1).

- MemoryStore.append -> recall round-trips last N cards.
- Agent.run writes the Q/A to memory; a second Agent over the SAME MemoryStore
  sees the prior turn injected into its system block (real cross-session recall).
No network/keys.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.config import AgentConfig
from agent.loop import Agent, Tool, ToolRegistry
from agent.memory import MemoryStore
from agent.models import ChatResult


def test_memory_recall():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d)
    ms = MemoryStore(cfg)
    assert ms.recall() == ""  # empty -> ''
    for i in range(12):
        ms.append(f"note {i}", target="agent")
    rec = ms.recall(limit=3)
    assert "note 11" in rec and "note 10" in rec and "note 9" in rec
    assert "note 0" not in rec  # only last 3
    print("OK memory recall round-trips")


def test_agent_persists_across_runs():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d, memory_recall=8)
    reg = ToolRegistry()
    reg.register(
        Tool("echo", "echo", {"type": "object", "properties": {}}, lambda a: "ok")
    )

    # first agent run
    class R1:
        def chat(self, m, tools=None, temperature=0.4, **_kwargs):
            return ChatResult(text="Paris is the capital of France.")

    a1 = Agent(cfg, router=R1(), registry=reg, memory=MemoryStore(cfg))
    a1.run("what is the capital of France?")

    # a second, fresh agent over the SAME memory store
    class R2:
        def chat(self, m, tools=None, temperature=0.4, **_kwargs):
            # surface whether the system block contains the prior turn
            sysblk = m[0]["content"]
            R2.saw = "capital of France" in sysblk
            return ChatResult(text="I recall we discussed France earlier.")

    a2 = Agent(cfg, router=R2(), registry=reg, memory=MemoryStore(cfg))
    a2.run("remind me what we talked about")
    assert getattr(R2, "saw", False), "prior turn not injected into system block"
    print("OK agent recalls prior turn across runs")


def test_persist_offline_safe_on_error():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=os.path.join(d, "nested", "mem"))
    ms = MemoryStore(cfg)
    ms.append("x")  # dir auto-created; must not raise
    a = Agent(cfg, router=None, registry=ToolRegistry(), memory=ms)
    # run with no router -> model error path; must not raise, still returns
    res = a.run("hi")
    assert res.text.startswith("[model error]")
    print("OK agent error path is offline-safe")


def test_append_respects_max_cards():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d, memory_max_cards=5)
    ms = MemoryStore(cfg)
    for i in range(12):
        ms.append(f"note {i}", target="agent")
    c = ms.counts()
    assert c["agent"] == 5, f"expected 5 cards, got {c['agent']}"
    # oldest (note 0..6) evicted; newest 5 (note 7..11) remain
    rec = ms.read(target="agent")
    assert "note 11" in rec and "note 7" in rec
    assert "note 0" not in rec and "note 6" not in rec
    # indexing still 0-based over remaining cards
    assert ms.list(target="agent")[0].text == "note 7"
    print("OK append FIFO-evicts oldest past max_cards")


def test_append_dedup_skips_duplicate():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d, memory_dedup=True)
    ms = MemoryStore(cfg)
    i1 = ms.append("same fact", target="user")
    i2 = ms.append("same fact", target="user")  # identical -> not re-added
    assert i1 == i2, "duplicate should return same index"
    assert ms.counts()["user"] == 1, "duplicate card must not accumulate"
    # disabling dedup allows the repeat
    cfg2 = AgentConfig(memory_root=d, memory_dedup=False)
    ms2 = MemoryStore(cfg2)
    ms2.append("x")
    ms2.append("x")
    assert ms2.counts()["agent"] == 2
    print("OK append dedups identical cards when enabled")


if __name__ == "__main__":
    test_memory_recall()
    test_agent_persists_across_runs()
    test_persist_offline_safe_on_error()
    test_append_respects_max_cards()
    test_append_dedup_skips_duplicate()
    print("PASS tests/test_agent_memory.py")
