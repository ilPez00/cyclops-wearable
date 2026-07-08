"""Cyclops desktop TUI (Win/Mac/Linux) — a shell over the agent core.

Mirrors Hermes' interactive CLI: a chat-like screen where you type text (or
attach an image / paste an audio transcript), the agent routes it through its
tools and model, and results + tool steps stream back. Built on `textual`
when available; falls back to a plain stdin/stdout REPL if textual isn't
installed, so it runs anywhere Python 3.10+ exists.

Usage:
  python3 shells/tui/cyclops_tui.py
  CYCLOPS_LOCAL=1 python3 shells/tui/cyclops_tui.py   # force local model
"""
from __future__ import annotations

import os
import sys

from agent.config import AgentConfig
from agent.tools import build_registry
from agent.loop import Agent


def build_agent() -> Agent:
    cfg = AgentConfig.load(env=dict(os.environ))
    reg = build_registry(cfg)
    return Agent(cfg, registry=reg)


def run_repl():
    """Fallback REPL when textual is unavailable."""
    agent = build_agent()
    print("Cyclops TUI (REPL mode). Type 'exit' to quit.")
    print(f"model={agent.cfg.model} provider={agent.cfg.provider} "
          f"local={agent.cfg.local_mode}\n")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("exit", "quit"):
            break
        if not text:
            continue
        res = agent.run(text)
        if res.tool_calls:
            for s in res.steps:
                print(f"  · {s['tool']}({s['args']}) -> {s['result'][:120]}")
        print("cyclops>", res.text or "(no response)")


def main():
    try:
        from textual.app import App, ComposeResult
        from textual.widgets import Header, Footer, Input, RichLog, Static, Switch, Select
        from textual.containers import Vertical, Horizontal
    except Exception:
        run_repl()
        return

    class CyclopsTUI(App):
        TITLE = "Cyclops"
        BINDINGS = [("ctrl+q", "quit", "Quit")]

        def __init__(self):
            super().__init__()
            self.agent = build_agent()

        def compose(self) -> ComposeResult:
            yield Header()
            with Vertical():
                yield RichLog(id="log", markup=False, wrap=True)
                with Horizontal():
                    yield Input(placeholder="message / attach image url…", id="inp")
                    yield Switch(value=self.agent.cfg.local_mode, id="local")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#log").write(
                f"[Cyclops] model={self.agent.cfg.model} "
                f"provider={self.agent.cfg.provider} "
                f"local={self.agent.cfg.local_mode}")

        def on_input_submitted(self, ev) -> None:
            text = ev.value.strip()
            if not text:
                return
            self.query_one("#inp").value = ""
            log = self.query_one("#log")
            log.write(f"you> {text}")
            res = self.agent.run(text)
            for s in res.steps:
                log.write(f"  · tool {s['tool']} -> {s['result'][:160]}")
            log.write(f"cyclops> {res.text or '(no response)'}")

        def on_switch_changed(self, ev) -> None:
            if ev.switch.id == "local":
                self.agent.cfg.local_mode = ev.value

    CyclopsTUI().run()


if __name__ == "__main__":
    main()
