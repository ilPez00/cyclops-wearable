"""Tests for agent conversation history + memory write-back."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.config import AgentConfig
from agent.tools import build_registry
from agent.models import ChatResult
from agent.loop import Agent


class FakeRouter:
    """Echoes a deterministic answer; never calls tools, just replies."""
    def chat(self, messages, tools=None, temperature=0.4):
        # last user message text
        last = messages[-1]
        text = last.get("content") if isinstance(last.get("content"), str) else str(last.get("content"))
        return ChatResult(text=f"reply to: {text}")


def test_history_accumulates():
    cfg = AgentConfig()
    agent = Agent(cfg, router=FakeRouter(), registry=build_registry(cfg, agent=None))
    r1 = agent.run("hello")
    assert "reply to: hello" in r1.text
    r2 = agent.run("how are you?")
    assert "reply to: how are you?" in r2.text
    # history now has user+assistant for both turns
    htxt = agent.history_text()
    assert "hello" in htxt and "how are you?" in htxt
    assert htxt.count("user:") == 2 and htxt.count("assistant:") == 2


def test_history_replayed_into_context():
    cfg = AgentConfig()
    seen = []
    class SpyRouter:
        def chat(self, messages, tools=None, temperature=0.4):
            seen.append(messages)
            return ChatResult(text="ok")
    agent = Agent(cfg, router=SpyRouter(), registry=build_registry(cfg, agent=None))
    agent.run("first turn")
    agent.run("second turn")
    # second call's messages must include the first turn (history replay)
    msgs = seen[-1]
    joined = json.dumps(msgs)
    assert "first turn" in joined and "second turn" in joined


def test_reset_clears_history():
    cfg = AgentConfig()
    agent = Agent(cfg, router=FakeRouter(), registry=build_registry(cfg, agent=None))
    agent.run("a"); agent.run("b")
    assert len(agent.history) >= 2
    agent.reset()
    assert agent.history == []


def test_history_tool_uses_agent():
    cfg = AgentConfig()
    a = Agent(cfg, router=FakeRouter(), registry=None)
    a.registry = build_registry(cfg, agent=a)
    a.run("remember this")
    assert "history" in a.registry.names()
    out = a.registry.run("history", {"limit": 5})
    assert "remember this" in out


def test_memory_writeback():
    cfg = AgentConfig()
    # point memory root at a temp dir to avoid touching ~/.hermes
    tmp = tempfile.mkdtemp()
    cfg.hermes_home = tmp
    from agent.memory import MemoryStore
    store = MemoryStore(cfg)
    path = store.append_note("buy milk", kind="reminder")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        rec = json.loads(f.readline())
    assert rec["kind"] == "reminder" and rec["text"] == "buy milk"
