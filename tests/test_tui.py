"""Offline tests for the TUI shell (no textual needed, no network)."""

import json
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
)  # /home/gio
sys.path.insert(
    0, os.path.dirname(os.path.dirname(__file__))
)  # repo root /home/gio/cyclops

from agent.models import ChatResult
from shells.tui.cyclops_tui import build_agent


class FakeRouter:
    def chat(self, messages, tools=None, temperature=0.4, **_kwargs):
        # final answer only (no tools) so the TUI turn completes offline
        return ChatResult(text="I am Cyclops. Ready.")


def test_build_agent_offline():
    agent = build_agent()
    assert agent.cfg is not None
    assert "terminal" in agent.registry
    assert "whatsapp_export" in agent.registry
    assert "device" in agent.registry
    assert "media_ingest" in agent.registry


def test_tui_turn_offline():
    agent = build_agent()
    agent.router = FakeRouter()
    res = agent.run("hello")
    assert res.text == "I am Cyclops. Ready."
    assert res.tool_calls == 0
