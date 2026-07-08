"""Agent configuration — mirrors Hermes cli-config.yaml semantics (subset).

Paths are configurable so the same core runs on the phone, desktop, or the
wearable. Environment variables + a config file are both supported; env wins.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AgentConfig:
    # Model routing -------------------------------------------------------
    model: str = "auto"
    provider: str = "auto"          # auto|openrouter|groq|openai|ollama|lmstudio|custom|...
    base_url: str = ""              # for local/custom OpenAI-compatible servers
    api_key: str = ""               # optional; falls back to env / key store

    # Local-model toggle (the "run AI on device" switch) -------------------
    local_mode: bool = False        # True -> force a local endpoint
    local_base_url: str = "http://127.0.0.1:11434/v1"  # ollama default
    local_model: str = "llama3.1"
    local_vision_model: str = "llava"
    local_stt: str = "http://127.0.0.1:11434"
    vision_model: str = ""          # cloud vision model override

    # Memory / persona / health roots (configurable; default to what exists) -
    hermes_home: str = "~/.hermes"
    digigio_home: str = "~/digigio"     # mounted digigio brain (persona/health)
    memory_file: str = "MEMORY.md"
    user_file: str = "USER.md"

    # Skills --------------------------------------------------------------
    skills_dirs: list[str] = field(default_factory=lambda: ["~/.hermes/skills"])

    # Device transport (how the app reaches the wearable) ------------------
    device_transport: str = "wifi"  # wifi|bt|cable
    device_host: str = "192.168.1.50"
    device_port: int = 8080

    # Safety --------------------------------------------------------------
    terminal_confirm: bool = True   # require confirm before shell exec
    allow_fs_write: bool = False

    # Customization -------------------------------------------------------
    system_note: str = ""           # extra system prompt text
    max_tool_iter: int = 6

    @classmethod
    def load(cls, path: Optional[str] = None, env: Optional[dict] = None) -> "AgentConfig":
        env = env if env is not None else dict(os.environ)
        cfg = cls()
        if path and os.path.exists(path):
            cfg._from_file(path)
        # env overrides
        if env.get("CYCLOPS_MODEL"): cfg.model = env["CYCLOPS_MODEL"]
        if env.get("CYCLOPS_PROVIDER"): cfg.provider = env["CYCLOPS_PROVIDER"]
        if env.get("CYCLOPS_BASE_URL"): cfg.base_url = env["CYCLOPS_BASE_URL"]
        if env.get("CYCLOPS_LOCAL") in ("1", "true", "yes"):
            cfg.local_mode = True
        if env.get("CYCLOPS_DEVICE_HOST"): cfg.device_host = env["CYCLOPS_DEVICE_HOST"]
        if env.get("CYCLOPS_DEVICE_TRANSPORT"):
            cfg.device_transport = env["CYCLOPS_DEVICE_TRANSPORT"]
        return cfg

    def _from_file(self, path: str):
        # minimal YAML-ish: only the keys we care about, flat or 'model:' block
        section = None
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line.strip() or line.strip().startswith("#"):
                    continue
                if line.startswith(" ") and ":" in line:
                    k, _, v = line.strip().partition(":")
                    v = v.strip().strip('"').strip("'")
                    if section == "model":
                        if k == "default": self.model = v
                        elif k == "provider": self.provider = v
                        elif k == "base_url": self.base_url = v
                    continue
                k, _, v = line.partition(":")
                k = k.strip(); v = v.strip().strip('"').strip("'")
                if k == "model":
                    section = "model"; continue
                section = None
                if k == "local_mode": self.local_mode = v in ("true", "1", "yes")
                elif k == "local_base_url": self.local_base_url = v
                elif k == "device_transport": self.device_transport = v
                elif k == "device_host": self.device_host = v
                elif k == "terminal_confirm": self.terminal_confirm = v in ("true", "1", "yes")

    def effective_endpoint(self) -> str:
        """Resolve the OpenAI-compatible base_url for the current provider."""
        if self.local_mode or self.provider in ("ollama", "lmstudio", "custom"):
            return self.local_base_url or self.base_url or "http://127.0.0.1:11434/v1"
        return self.base_url or "https://openrouter.ai/api/v1"

    def provider_for(self, capability: str) -> dict:
        """Return a per-capability provider override if configured in env.

        capability in: vision | stt | chat.  Looks for CYCLOPS_<CAP>_PROVIDER /
        CYCLOPS_<CAP>_ENDPOINT / CYCLOPS_<CAP>_MODEL. Falls back to base config.
        """
        cap = capability.upper()
        prov = os.environ.get(f"CYCLOPS_{cap}_PROVIDER", self.provider)
        endpoint = os.environ.get(f"CYCLOPS_{cap}_ENDPOINT",
                                  self.effective_endpoint())
        model = os.environ.get(f"CYCLOPS_{cap}_MODEL", self.model)
        return {"provider": prov, "endpoint": endpoint, "model": model}

    def resolve_key(self, keys=None):
        """Best-effort API key: explicit -> env -> ai key store."""
        if self.api_key:
            return self.api_key
        if self.provider != "auto":
            envk = (self.provider.upper() + "_API_KEY")
            if os.environ.get(envk):
                return os.environ[envk]
        # try the cyclops ai key store
        try:
            from brain.aikeys import AiKeys
            k = AiKeys()
            for name in (self.provider, "openrouter", "openai", "groq"):
                if name == "auto":
                    continue
                val = k.get_key(name) or k.get_key(name + "_api_key")
                if val:
                    return val
        except Exception:
            pass
        return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
