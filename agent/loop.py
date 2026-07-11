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

from . import learning as learning_mod
from .config import AgentConfig
from .memory import MemoryStore
from .models import ChatResult, ModelRouter
from .skills import Skills


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
                 memory: Optional[MemoryStore] = None, max_iter: int = 0,
                 context=None):
        self.cfg = config
        self.router = router or ModelRouter(config)
        self.registry = registry or ToolRegistry()
        self.skills = skills or Skills(config.skills_dirs)
        self.memory = memory or MemoryStore(config)
        self.max_iter = max_iter or config.max_tool_iter
        self.context = context  # brain.context.ContextAssembler (live fused context)
        self.history: list[dict] = []   # prior turns (role/content), in-session memory
        # optional live progress callback: cb(tool_name, progress_pct) per iteration
        self.progress_cb: Optional[Callable[[Optional[str], int], None]] = None
        self._last_tool: Optional[str] = None   # last invoked tool (for per-tool model override)

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
        if self.progress_cb:
            self.progress_cb(None, 0)   # thinking…
        for _ in range(self.max_iter):
            try:
                resp = self.router.chat(messages, tools=self.registry.schemas() or None,
                                        tool=self._last_tool)
            except Exception as e:
                result.text = f"[model error] {e}"
                self._remember("user", content)
                self._remember("assistant", result.text)
                if self.progress_cb:
                    self.progress_cb(None, 100)
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
                    self._last_tool = name   # feed into next model call for per-tool override
                    result.tool_calls += 1
                    result.steps.append({"tool": name, "args": args, "result": out[:500]})
                    if self.progress_cb:
                        pct = min(95, 20 + 75 * result.tool_calls // max(1, self.max_iter))
                        self.progress_cb(name, pct)
                    messages.append({"role": "tool", "name": name,
                                     "content": out[:4000]})
                continue
            result.text = resp.text
            self._remember("user", content)
            self._remember("assistant", resp.text)
            if self.progress_cb:
                self.progress_cb(None, 100)
            self.persist_turn(user_text, result.text)
            # Hermes-style learning: review the turn off-thread and persist any
            # durable user/agent facts to memory. Never blocks the reply.
            self._learn(user_text, result.text)
            return result
        result.text = result.text or "[max iterations reached]"
        self._remember("user", content)
        self._remember("assistant", result.text)
        self.persist_turn(user_text, result.text)
        return result

    def _remember(self, role: str, content):
        # keep history bounded (last ~40 messages) to limit context growth
        self.history.append({"role": role, "content": content})
        if len(self.history) > 40:
            self.history = self.history[-40:]

    # -- internals ----------------------------------------------------------
    def _system_block(self) -> str:
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
        # Hermes-style durable memory: agent facts (MEMORY.md) + user profile (USER.md)
        agent_mem = self.memory.read(target="agent")
        if agent_mem:
            parts.append("AGENT MEMORY (durable facts about the world/environment):\n" + agent_mem)
        user_mem = self.memory.read(target="user")
        if user_mem:
            parts.append("USER PROFILE (who the user is, preferences, how they work):\n" + user_mem)
        if skills_blk: parts.append(skills_blk)
        rec = self.memory.recall(limit=self.cfg.memory_recall or 8)
        if rec: parts.append("RECENT MEMORY (persisted across sessions):\n" + rec)
        if self.context is not None:
            fused = self.context.render()
            if fused and fused != "[context] empty":
                parts.append("LIVE CONTEXT (fused notes/health/calendar):\n" + fused)
        return "\n\n".join(parts)

    def persist_turn(self, user_text: str, answer: str):
        """Write the Q/A back to persistent memory (offline-safe)."""
        try:
            self.memory.append(f"user: {user_text}", target="agent")
            if answer:
                self.memory.append(f"cyclops: {answer[:500]}", target="agent")
        except Exception:
            pass

    def _learn(self, user_text: str, answer: str):
        """Kick off a Hermes-style learning review of the completed turn.

        Runs on a daemon thread (via learning.learn_from_turn) so the agent's
        reply is never delayed. No-op when the router can't reach a model.
        """
        try:
            learning_mod.learn_from_turn(
                user_text, answer, self.memory,
                router=self.router, async_ok=True)
        except Exception:
            pass

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
