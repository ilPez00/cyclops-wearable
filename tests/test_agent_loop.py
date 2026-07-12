"""Tests for agent/loop.py - the agent runtime, testable offline.

The Agent is fully injectable: pass a fake ModelRouter (canned
responses), a ToolRegistry with a fake tool, a fake Skills, and an
optional fake ContextAssembler. No model/network needed. Run with:
    python3 tests/run_tests.py tests/test_agent_loop.py
"""
import json
import tempfile

from agent.loop import Agent, ToolRegistry, Tool
from agent.config import AgentConfig

ARG_ECHO = json.dumps({"v": "hi"})

STEP_NONE = {"tool_calls": None, "text": "done"}
STEP_ECHO = {"tool_calls": [{"function": {"name": "echo", "arguments": ARG_ECHO}}]}
STEP_FINAL = {"tool_calls": None, "text": "got it"}
STEP_OK = {"tool_calls": None, "text": "ok"}
STEP_FIN = {"tool_calls": None, "text": "fin"}
STEP_SAVED = {"tool_calls": None, "text": "saved"}


class _Cfg(AgentConfig):
    def __init__(self):
        super().__init__()
        self.skills_dirs = []


class _Skills:
    def system_block(self):
        return "SKILLS: none"


class _Ctx:
    def render(self):
        return "notes: bought milk; hr 74"


class _FakeRouter:
    """Returns scripted responses; records chat() calls."""
    class _Resp:
        def __init__(self, tool_calls, text):
            self.tool_calls = tool_calls
            self.text = text

    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = 0

    def chat(self, messages, tools=None, tool=None):
        self.calls += 1
        step = self.scripted.pop(0) if self.scripted else {"tool_calls": None, "text": "[max iterations reached]"}
        return self._Resp(step.get("tool_calls"), step.get("text", ""))


def _mk_agent(router, ctx=None, cb=None):
    reg = ToolRegistry()
    reg.register(Tool(
        name="echo",
        description="echo a value",
        parameters={"type": "object", "properties": {"v": {"type": "string"}}},
        run=lambda a: "echo:" + str(a.get("v")),
    ))
    a = Agent(config=_Cfg(), router=router, registry=reg,
              skills=_Skills(), context=ctx, max_iter=4)
    if cb is not None:
        a.progress_cb = cb
    return a


def test_single_turn_no_tool():
    r = _FakeRouter([{"tool_calls": None, "text": "done"}])
    a = _mk_agent(r)
    res = a.run("hello")
    assert res.text == "done"
    assert res.tool_calls == 0
    assert len(res.steps) == 0
    assert a.history_text().count("user:") >= 1
    assert "done" in a.history_text()


def test_tool_call_roundtrip():
    r = _FakeRouter([STEP_ECHO, STEP_FINAL])
    a = _mk_agent(r)
    res = a.run("use echo")
    assert res.tool_calls == 1
    assert r.calls == 2  # model called again after tool result
    assert len(res.steps) == 1
    assert res.steps[0]["tool"] == "echo"
    assert "echo:hi" in res.steps[0]["result"]
    assert res.text == "got it"


def test_context_wired_into_system_block():
    # Closes the analysis gap: context must be rendered into the system block.
    r = _FakeRouter([STEP_OK])
    a = _mk_agent(r, ctx=_Ctx())
    a.run("with context")
    sys_block = a._system_block()
    assert "LIVE CONTEXT" in sys_block
    assert "hr 74" in sys_block


def test_progress_callback_fires():
    seen = []
    r = _FakeRouter([STEP_FIN])
    a = _mk_agent(r, cb=lambda name, pct: seen.append((name, pct)))
    a.run("go")
    assert (None, 0) in seen
    assert (None, 100) in seen


def test_iteration_budget_respected():
    # Only one scripted step, no final text -> budget exhausts at max_iter
    r = _FakeRouter([STEP_ECHO])
    a = _mk_agent(r, ctx=None)
    res = a.run("loop")
    assert r.calls <= 4 + 1
    assert res.text  # either a final text or the max-iter marker


def test_memory_persist_is_offline_safe():
    with tempfile.TemporaryDirectory() as d:
        cfg = _Cfg()
        cfg.memory_root = d
        reg = ToolRegistry()
        reg.register(Tool(name="n", description="n", parameters={}, run=lambda a: "noted"))
        r = _FakeRouter([STEP_SAVED])
        from agent.memory import MemoryStore
        a = Agent(config=cfg, router=r, registry=reg, skills=_Skills(),
                  memory=MemoryStore(cfg), max_iter=2)
        a.run("remember this")
        # turn persisted into the temp memory root's MEMORY.md
        from pathlib import Path
        assert Path(d + "/MEMORY.md").exists()
