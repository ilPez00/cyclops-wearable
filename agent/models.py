"""Model routing — cloud providers + local OpenAI-compatible servers.

Mirrors Hermes model config: a single OpenAI-compatible chat/completions call
works for both cloud (openrouter/openai/groq/...) and local (ollama/lmstudio/
custom). The transport is injectable so tests run offline. Multimodal content
(text + image_url + audio transcript) is supported.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .config import AgentConfig


@dataclass
class ChatResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


# --- transport shim (stdlib default; injectable) -------------------------
def _default_session():
    import urllib.request as req
    import urllib.error as err

    class Resp:
        def __init__(self, status, body):
            self.status = status; self._b = body
        def json(self): return json.loads(self._b)

    class Sess:
        def post(self, url, data=None, headers=None, timeout=60, files=None):
            r = req.Request(url, data=data, headers=headers or {}, method="POST")
            try:
                with req.urlopen(r, timeout=timeout) as resp:
                    return Resp(resp.status, resp.read().decode("utf-8", "ignore"))
            except err.HTTPError as e:
                return Resp(e.code, e.read().decode("utf-8", "ignore"))
    return Sess()


class ModelRouter:
    def __init__(self, config: AgentConfig, session=None):
        self.cfg = config
        self.session = session or _default_session()

    def chat(self, messages: list[dict], model: str | None = None,
             tools: list[dict] | None = None, temperature: float = 0.4) -> ChatResult:
        model = model or self._resolve_model()
        endpoint = self.cfg.effective_endpoint().rstrip("/") + "/chat/completions"
        payload: dict = {"model": model, "messages": messages, "temperature": temperature}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        key = self.cfg.resolve_key()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        resp = self.session.post(endpoint, data=json.dumps(payload).encode(), headers=headers, timeout=120)
        data = resp.json()
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"model response error: {e} ({data})")
        text = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []
        return ChatResult(text=text, tool_calls=tool_calls, raw=data)

    def _resolve_model(self) -> str:
        if self.cfg.model and self.cfg.model != "auto":
            return self.cfg.model
        if self.cfg.local_mode or self.cfg.provider in ("ollama", "lmstudio", "custom"):
            return os_environ_model("ollama") or "llama3.1"
        return "openai/gpt-4o-mini"  # cheap default for cloud


def os_environ_model(fallback_provider: str) -> str:
    import os
    return os.environ.get("CYCLOPS_LOCAL_MODEL") or ""
