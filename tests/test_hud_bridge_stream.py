"""Offline: brain HUD bridge streams live agent progress + tool-step ticks.

Drives HudBridge.dispatch(ACT_AGENT) with a FakeAgent whose run fires
progress_cb per tool call, and asserts the sink received:
  - intermediate "  · <tool>" step lines (live ticking)
  - intermediate progress HUD frames ("…NN%")
  - the final "AGENT: <banner>" line
No network/keys/device involved.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.config import AgentConfig
from agent.loop import Agent, Tool, ToolRegistry
from brain.hud_bridge import ACT_AGENT, HudBridge
from brain.protocol_v2 import parse_hud


class FakeSink:
    def __init__(self):
        self.texts = []
        self.frames = []  # parsed v2 HUD frames (K...)
        self.raw = []  # raw DISPLAY_CMD bytes written

    def render_text(self, t):
        self.texts.append(t)

    def write(self, b):
        self.raw.append(bytes(b))
        if b[:1] == b"K":
            self.frames.append(parse_hud(b))


def test_live_agent_streaming():
    # registry with two tools so the agent runs >1 iteration
    reg = ToolRegistry()
    reg.register(
        Tool("device", "device", {"type": "object", "properties": {}}, lambda a: "ok")
    )
    reg.register(
        Tool("web", "web", {"type": "object", "properties": {}}, lambda a: "ok")
    )

    # FakeRouter: always returns a tool_call first, then final text
    class FakeRouter:
        def __init__(self):
            self.n = 0

        def chat(self, messages, tools=None, temperature=0.4, **_kwargs):
            from agent.models import ChatResult

            if self.n == 0:
                self.n += 1
                return ChatResult(
                    text="",
                    tool_calls=[{"function": {"name": "device", "arguments": "{}"}}],
                )
            if self.n == 1:
                self.n += 1
                return ChatResult(
                    text="",
                    tool_calls=[{"function": {"name": "web", "arguments": "{}"}}],
                )
            return ChatResult(text="Final answer here")

    agent = Agent(AgentConfig(), router=FakeRouter(), registry=reg)
    sink = FakeSink()
    br = HudBridge(sink, agent=agent)

    res = br.dispatch(ACT_AGENT, "do the thing")
    assert res[0] == "agent"

    step_lines = [t for t in sink.texts if t.startswith("  · ")]
    # both tool ticks streamed live (device + web)
    assert any("device" in t for t in step_lines), f"no device tick: {sink.texts}"
    assert any("web" in t for t in step_lines), f"no web tick: {sink.texts}"

    # intermediate progress + step DISPLAY_CMD frames emitted
    import json as _json

    def _json_of(raw):
        i = raw.find(b"{")
        j = raw.rfind(b"}")
        return _json.loads(raw[i : j + 1]) if i >= 0 and j >= i else {}

    prog = [f for f in sink.raw if b"progress" in f]
    step = [f for f in sink.raw if b"step" in f]
    assert prog, f"no progress DISPLAY_CMD: {[r[:40] for r in sink.raw]}"
    assert step, f"no step DISPLAY_CMD: {[r[:40] for r in sink.raw]}"
    # progress value is numeric and <=100
    first = _json_of(prog[0])
    assert 0 <= int(first.get("p", -1)) <= 100, first

    # final banner present
    assert any(t.startswith("AGENT: ") for t in sink.texts), sink.texts
    print(
        "OK live streaming: %d step lines, %d progress frames"
        % (len(step_lines), len(prog))
    )


def test_stub_no_streaming_on_error():
    # agent with no progress_cb path must still return final text
    sink = FakeSink()
    br = HudBridge(sink, agent=None)
    res = br.dispatch(ACT_AGENT, "hi")
    assert res[0] == "agent"
    assert any(t.startswith("AGENT: ") for t in sink.texts)


if __name__ == "__main__":
    test_live_agent_streaming()
    test_stub_no_streaming_on_error()
    print("PASS tests/test_hud_bridge_stream.py")
