"""Offline GGUF inference via llama-cpp-python — true on-device, no server.

pika-hermes runs GGUF models in-app through a llama.cpp JNI layer; the clean
Python analog is llama-cpp-python (same GGUF files, same llama.cpp, pip wheel).
This backend is the last cascade slot: when a .gguf model is configured and
the lib is installed, Cyclops answers with ZERO network — the genuine offline
path. Everything is lazy + optional so the zero-dep stdlib server is untouched
when GGUF is not used:

  - llama_cpp is imported only on first chat() (not at module load / not in CI).
  - No model is bundled; the user supplies a .gguf path (config.gguf_model_path).
  - Local GGUF models don't emit native `tool_calls`, so tool intents are
    parsed out of the text (parse_tool_calls) — ported from pika's LlamaBackend.
"""

from __future__ import annotations

import json
import re

from agent.models import ChatResult, ModelError

# A GGUF model asked to use tools emits them as text; accept a few shapes.
_TOOLCALL_RES = [
    re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL),
    re.compile(r"```(?:json)?\s*(\{[^`]*\"name\"[^`]*\})\s*```", re.DOTALL),
]


def parse_tool_calls(text: str) -> list[dict]:
    """Extract tool intents from raw model text (GGUF has no native
    tool_calls). Returns OpenAI-shaped tool_calls; empty if none found."""
    out = []
    for rx in _TOOLCALL_RES:
        for m in rx.finditer(text or ""):
            obj = _balanced_json(m.group(1))
            if obj and "name" in obj:
                out.append(
                    {
                        "id": f"gguf_{len(out)}",
                        "type": "function",
                        "function": {
                            "name": obj["name"],
                            "arguments": json.dumps(
                                obj.get("arguments", obj.get("args", {}))
                            ),
                        },
                    }
                )
    return out


def _balanced_json(s: str) -> dict | None:
    s = s.strip()
    depth = 0
    end = -1
    for i, ch in enumerate(s):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        return None
    try:
        obj = json.loads(s[:end])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


class GgufRouter:
    """Router-shaped wrapper around a llama-cpp-python model.

    Matches ModelRouter.chat's return so it drops into the cascade as a slot.
    `llama` is injectable for tests (any object with create_chat_completion).
    """

    def __init__(self, model_path: str, n_ctx: int = 4096, llama=None):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self._llama = llama

    def _model(self):
        if self._llama is not None:
            return self._llama
        try:
            from llama_cpp import Llama
        except Exception as e:  # pragma: no cover - optional dep
            raise ModelError(
                "llama-cpp-python not installed: `pip install llama-cpp-python`",
                status=0,
            ) from e
        self._llama = Llama(model_path=self.model_path, n_ctx=self.n_ctx, verbose=False)
        return self._llama

    def chat(
        self, messages, model=None, tools=None, temperature=0.4, **kw
    ) -> ChatResult:
        llama = self._model()
        try:
            resp = llama.create_chat_completion(
                messages=messages, temperature=temperature
            )
        except Exception as e:
            raise ModelError(f"gguf inference failed: {e}", status=0) from e
        try:
            text = resp["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError(f"gguf response error: {e}", status=0)
        # tools requested -> parse them out of the text (no native tool_calls)
        tool_calls = parse_tool_calls(text) if tools else []
        return ChatResult(text=text, tool_calls=tool_calls, raw=resp)


def available(config) -> bool:
    """True if a GGUF model path is configured (existence checked lazily)."""
    import os

    p = getattr(config, "gguf_model_path", "") or ""
    return bool(p) and os.path.exists(os.path.expanduser(p))


__all__ = ["GgufRouter", "parse_tool_calls", "available"]
