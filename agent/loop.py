"""Agent loop + tool registry — mirrors Hermes conversation_loop.py (simplified).

The loop: build system context (memory + skills), call the model, if the model
returns tool_calls execute them and feed results back, repeat until the model
returns final text or the iteration budget is exhausted. The model and tools
are injectable so the whole loop is testable offline.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Optional

from .config import AgentConfig
from .memory import MemoryStore
from .skills import Skills
from .models import ModelRouter, ChatResult


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict                 # JSON-schema-ish
    run: Callable[[dict], str]      # args -> string result

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def run(self, name: str, args: dict) -> str:
        if name not in self._tools:
            return f"error: unknown tool {name}"
        try:
            return str(self._tools[name].run(args or {}))
        except Exception as e:
            return f"error: {e}"


@dataclass
class TurnResult:
    text: str
    steps: list[dict] = field(default_factory=list)   # audit trail
    tool_calls: int = 0


class Agent:
    def __init__(self, config: AgentConfig, router: Optional[ModelRouter] = None,
                 registry: Optional[ToolRegistry] = None, skills: Optional[Skills] = None,
                 memory: Optional[MemoryStore] = None, max_iter: int = 0):
        self.cfg = config
        self.router = router or ModelRouter(config)
        self.registry = registry or ToolRegistry()
        self.skills = skills or Skills(config.skills_dirs)
        self.memory = memory or MemoryStore(config)
        self.max_iter = max_iter or config.max_tool_iter
        self.history: list[dict] = []   # prior turns (role/content), in-session memory

    def reset(self):
        """Clear in-session conversation history."""
        self.history.clear()

    def history_text(self) -> str:
        lines = []
        for m in self.history:
            role = m.get("role")
            c = m.get("content")
            if isinstance(c, list):
                c = " ".join(b.get("text", "") for b in c if isinstance(b, dict))
            lines.append(f"{role}: {c}")
        return "\n".join(lines)

    # -- public -------------------------------------------------------------
    def run(self, user_text: str, images: list[str] | None = None,
            audio_transcript: str | None = None) -> TurnResult:
        sys_block = self._system_block()
        messages = [{"role": "system", "content": sys_block}]
        # replay in-session history so the model has conversational context
        messages.extend(self.history)
        content = self._user_content(user_text, images, audio_transcript)
        messages.append({"role": "user", "content": content})

        result = TurnResult(text="")
        for _ in range(self.max_iter):
            try:
                resp = self.router.chat(messages, tools=self.registry.schemas() or None)
            except Exception as e:
                result.text = f"[model error] {e}"
                self._remember("user", content)
                self._remember("assistant", result.text)
                return result
            if resp.tool_calls:
                messages.append({"role": "assistant", "content": resp.text or "",
                                 "tool_calls": resp.tool_calls})
                for tc in resp.tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("argument", fn.get("arguments", "{}")) or "{}")
                    except Exception:
                        args = {}
                    out = self.registry.run(name, args)
                    result.tool_calls += 1
                    result.steps.append({"tool": name, "args": args, "result": out[:500]})
                    messages.append({"role": "tool", "name": name,
                                     "content": out[:4000]})
                continue
            result.text = resp.text
            self._remember("user", content)
            self._remember("assistant", resp.text)
            return result
        result.text = result.text or "[max iterations reached]"
        self._remember("user", content)
        self._remember("assistant", result.text)
        return result

    def _remember(self, role: str, content):
        # keep history bounded (last ~40 messages) to limit context growth
        self.history.append({"role": role, "content": content})
        if len(self.history) > 40:
            self.history = self.history[-40:]

    # -- internals ----------------------------------------------------------
    def _system_block(self) -> str:
        mem = self.memory.read()
        blk = mem.system_block()
        skills_blk = self.skills.system_block()
        base = ("You are Cyclops, a personal AI agent that routes text, audio and "
                "images to tools and returns concise results. You can control a "
                "terminal, read/write files, search the web, read the user's memory/"
                "persona/health, manage calendar/clipboard, describe images, ingest "
                "photos/voice/places, export WhatsApp chats, and talk to a wearable "
                "device (HUD, notifications, capture). Prefer tools when they help. "
                "Be terse unless asked otherwise.")
        if self.cfg.system_note:
            base = self.cfg.system_note + "\n\n" + base
        parts = [base]
        if blk: parts.append(blk)
        if skills_blk: parts.append(skills_blk)
        return "\n\n".join(parts)

    def _user_content(self, text, images, audio_transcript):
        blocks = []
        if audio_transcript:
            blocks.append({"type": "text", "text": f"[audio transcript] {audio_transcript}"})
        if text:
            blocks.append({"type": "text", "text": text})
        for url in (images or []):
            blocks.append({"type": "image_url", "image_url": {"url": url}})
        if not blocks:
            blocks.append({"type": "text", "text": ""})
        return blocks if len(blocks) > 1 else blocks[0]["text"]
