"""Offline tests for the expanded tool set + capability registry."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.capabilities import CAPABILITIES, describe, names
from agent.config import AgentConfig
from agent.models import ChatResult
from agent.tools import build_registry
from agent.tools.calendar import make_calendar_tool
from agent.tools.clipboard import make_clipboard_tool
from agent.tools.health import make_health_tool
from agent.tools.screen import make_screen_tool
from agent.tools.vision import make_vision_tool
from agent.tools.wearable import make_hud_tool
from agent.tools.web import make_web_tool


def test_registry_has_all_capabilities():
    reg = build_registry(AgentConfig())
    for name in names():
        assert name in reg, f"missing tool: {name}"
    # 16 capabilities registered
    assert len(reg) == len(CAPABILITIES)


def test_calendar_add_list():
    cfg = AgentConfig()
    reg = build_registry(cfg, disable={"terminal"})
    reg.register(make_calendar_tool(cfg))
    out = reg.run(
        "calendar", {"action": "add", "title": "call mom", "when": "tomorrow"}
    )
    assert "added" in out and "call mom" in out
    out2 = reg.run("calendar", {"action": "list"})
    assert "call mom" in out2


def test_clipboard_set_get():
    reg = build_registry(AgentConfig())
    reg.run("clipboard", {"action": "set", "text": "hello-clip"})
    got = reg.run("clipboard", {"action": "get"})
    assert "hello-clip" in got


def test_web_offline_stub():
    t = make_web_tool()
    assert "offline" in t.run({"action": "search", "query": "x"})
    assert "offline" in t.run({"action": "fetch", "url": "http://x"})


def test_vision_offline():
    t = make_vision_tool(AgentConfig(local_mode=True))
    out = t.run({"image": "http://example.com/p.jpg", "prompt": "what?"})
    assert "error" in out or "offline" in out  # no model -> error path


def test_wearable_offline_stub():
    t = make_hud_tool(AgentConfig())
    out = t.run({"text": "turn left"})
    assert "offline" in out


def test_health_no_data():
    reg = build_registry(AgentConfig(digigio_home="/no/such"))
    out = reg.run("health", {"action": "summary"})
    assert "no health data" in out


def test_screen_offline():
    t = make_screen_tool(AgentConfig())
    out = t.run({"describe": False})
    assert "offline" in out


def test_capabilities_describe():
    assert "Cyclops capabilities" in describe()
    assert "terminal" in names()


def test_agent_multi_tool_routing():
    """Fake router that asks for calendar then answers — full offline loop."""
    cfg = AgentConfig()
    reg = build_registry(
        cfg,
        disable={
            "terminal",
            "device",
            "brain",
            "vision",
            "web",
            "clipboard",
            "health",
            "hud",
            "notify",
            "capture",
            "screen",
            "whatsapp_export",
            "media_ingest",
            "fs",
        },
    )

    class FakeRouter:
        def __init__(self):
            self.n = 0

        def chat(self, messages, tools=None, temperature=0.4, **_kwargs):
            self.n += 1
            if self.n == 1:
                return ChatResult(
                    text="",
                    tool_calls=[
                        {
                            "function": {
                                "name": "calendar",
                                "arguments": json.dumps(
                                    {
                                        "action": "add",
                                        "title": "standup",
                                        "when": "tomorrow",
                                    }
                                ),
                            }
                        }
                    ],
                )
            return ChatResult(text="Reminder set for tomorrow.")

    from agent.loop import Agent

    a = Agent(cfg, router=FakeRouter(), registry=reg)
    res = a.run("remind me of standup tomorrow")
    assert res.tool_calls == 1
    assert "Reminder set" in res.text
