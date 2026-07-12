"""Model routing — cloud providers + local OpenAI-compatible servers.

Mirrors Hermes model config: a single OpenAI-compatible chat/completions call
works for both cloud (openrouter/openai/groq/...) and local (ollama/lmstudio/
custom). The transport is injectable so tests run offline. Multimodal content
(text + image_url + audio transcript) is supported.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .config import AgentConfig


@dataclass
class ChatResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class ModelError(RuntimeError):
    """A provider call failed. `status` carries the HTTP code (0 = transport
    error / timeout) so a cascade can classify the failure and back off."""

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


# --- transport shim (stdlib default; injectable) -------------------------
def _default_session():
    from brain.http_session import stdlib_session

    return stdlib_session()


class ModelRouter:
    def __init__(self, config: AgentConfig, session=None):
        self.cfg = config
        self.session = session or _default_session()

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.4,
        tool: str | None = None,
        provider: str | None = None,
        endpoint: str | None = None,
        key: str | None = None,
    ) -> ChatResult:
        # per-tool override from companion settings (provider/model/endpoint/key)
        ov = (self.cfg.tool_overrides or {}).get(tool) if tool else None
        if ov:
            provider = provider or ov.get("provider")
            model = model or ov.get("model")
            endpoint = endpoint or ov.get("endpoint")
            key = key or ov.get("key")
        model = model or self._resolve_model(provider=provider if provider else None)
        base_endpoint = endpoint or self.cfg.effective_endpoint(
            provider=provider if provider else None
        )
        endpoint_url = base_endpoint.rstrip("/") + "/chat/completions"
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        resolved_key = key or self.cfg.resolve_key(
            provider=provider if provider else None
        )
        headers = {"Content-Type": "application/json"}
        if resolved_key:
            headers["Authorization"] = f"Bearer {resolved_key}"
        try:
            resp = self.session.post(
                endpoint_url,
                data=json.dumps(payload).encode(),
                headers=headers,
                timeout=120,
            )
        except Exception as e:  # transport error / timeout
            raise ModelError(f"transport error: {e}", status=0) from e
        status = getattr(resp, "status", 200)
        if status and status >= 400:
            body = ""
            try:
                body = json.dumps(resp.json())[:200]
            except Exception:
                pass
            raise ModelError(f"HTTP {status}: {body}", status=status)
        data = resp.json()
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise ModelError(f"model response error: {e} ({data})", status=status)
        text = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []
        return ChatResult(text=text, tool_calls=tool_calls, raw=data)

    def _resolve_model(self, provider: str | None = None) -> str:
        if self.cfg.model and self.cfg.model != "auto":
            return self.cfg.model
        if self.cfg.local_mode or (provider or self.cfg.provider) in (
            "ollama",
            "lmstudio",
            "custom",
        ):
            return os_environ_model("ollama") or self.cfg.local_model or "llama3.1"
        return "openai/gpt-4o-mini"  # cheap default for cloud


_urllib_session = _default_session  # alias used by tools


def os_environ_model(fallback_provider: str) -> str:
    import os

    return os.environ.get("CYCLOPS_LOCAL_MODEL") or ""
