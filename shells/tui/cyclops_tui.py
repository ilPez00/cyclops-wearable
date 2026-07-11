"""Cyclops desktop TUI (Win/Mac/Linux) — a shell over the agent core.

Mirrors Hermes' interactive CLI: a chat-like screen where you type text (or
attach an image / paste an audio transcript), the agent routes it through its
tools and model, and results + tool steps stream back. Built on `textual`
when available; falls back to a plain stdin/stdout REPL if textual isn't
installed, so it runs anywhere Python 3.10+ exists.

The TUI also mirrors the wearable HUD: a glanceable banner (the agent's first
line) is shown at the top, echoing what the glasses would display (Omi/G2 style).

Usage:
  python3 shells/tui/cyclops_tui.py
  CYCLOPS_LOCAL=1 python3 shells/tui/cyclops_tui.py   # force local model
"""

from __future__ import annotations

import os

from agent.config import AgentConfig
from agent.loop import Agent
from agent.tools import build_registry


def build_agent() -> Agent:
    cfg = AgentConfig.load(env=dict(os.environ))
    reg = build_registry(cfg)
    return Agent(cfg, registry=reg)


def run_repl():
    """Fallback REPL when textual is unavailable."""
    agent = build_agent()
    print("Cyclops TUI (REPL mode). Type 'exit' to quit.")
    print(
        f"model={agent.cfg.model} provider={agent.cfg.provider} "
        f"local={agent.cfg.local_mode}\n"
    )
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
        # glanceable banner (what the glasses HUD would show)
        banner = res.text.split("\n", 1)[0][:60] if res.text else "(no response)"
        print(f"  [HUD] {banner}")
        if res.tool_calls:
            for s in res.steps:
                print(f"  · {s['tool']}({s['args']}) -> {s['result'][:120]}")
        print("cyclops>", res.text or "(no response)")


def main():
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, ScrollableContainer, Vertical
        from textual.widgets import (
            Checkbox,
            Footer,
            Header,
            Input,
            RichLog,
            Select,
            Static,
            Switch,
        )
    except Exception:
        run_repl()
        return

    class CyclopsTUI(App):
        TITLE = "Cyclops"
        BINDINGS = [("ctrl+q", "quit", "Quit")]

        def __init__(self):
            super().__init__()
            self.agent = build_agent()
            # capability toggles (offline tools always available; device/web need transport)
            self.disabled = {
                "device",
                "brain",
                "vision",
                "web",
                "hud",
                "notify",
                "capture",
            }

        def compose(self) -> ComposeResult:
            yield Header()
            with Vertical():
                yield Static("HUD: ready", id="hud")
                yield RichLog(id="log", markup=False, wrap=True, max_lines=2000)
                with Horizontal():
                    yield Input(placeholder="message / attach image url…", id="inp")
                    yield Switch(value=self.agent.cfg.local_mode, id="local")
                    yield Select(
                        [("wifi", "wifi"), ("bt", "bt"), ("cable", "cable")],
                        value=self.agent.cfg.device_transport,
                        id="transport",
                        allow_blank=False,
                    )
                with ScrollableContainer(id="caps"):
                    for name in sorted(self.agent.registry.names()):
                        yield Checkbox(
                            name, value=name not in self.disabled, id=f"cap_{name}"
                        )
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#log").write(
                f"[Cyclops] model={self.agent.cfg.model} "
                f"provider={self.agent.cfg.provider} "
                f"local={self.agent.cfg.local_mode}"
            )
            self.query_one("#log").write(
                f"[tools] {len(self.agent.registry)} available"
            )

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
            # glanceable banner (mirrors wearable HUD)
            banner = res.text.split("\n", 1)[0][:60] if res.text else "(no response)"
            self.query_one("#hud").update(f"HUD: {banner}")

        def on_switch_changed(self, ev) -> None:
            if ev.switch.id == "local":
                self.agent.cfg.local_mode = ev.value

        def on_select_changed(self, ev) -> None:
            if getattr(ev.select, "id", "") == "transport":
                self.agent.cfg.device_transport = str(ev.value)

        def on_checkbox_changed(self, ev) -> None:
            cid = getattr(ev.checkbox, "id", "") or ""
            if cid.startswith("cap_"):
                name = cid[4:]
                if ev.value:
                    self.disabled.discard(name)
                else:
                    self.disabled.add(name)
                # rebuild registry with new disabled set
                self.agent.registry = build_registry(
                    self.agent.cfg, disable=self.disabled
                )

    CyclopsTUI().run()


if __name__ == "__main__":
    main()
