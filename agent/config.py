"""Agent configuration — mirrors Hermes cli-config.yaml semantics (subset).

Paths are configurable so the same core runs on the phone, desktop, or the
wearable. Environment variables + a config file are both supported; env wins.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentConfig:
    # Model routing -------------------------------------------------------
    model: str = "auto"
    provider: str = "auto"  # auto|openrouter|groq|openai|ollama|lmstudio|custom|...
    base_url: str = ""  # for local/custom OpenAI-compatible servers
    api_key: str = ""  # optional; falls back to env / key store

    # Local-model toggle (the "run AI on device" switch) -------------------
    local_mode: bool = False  # True -> force a local endpoint
    local_first: bool = True  # P1-B: prefer offline/local; cloud only if explicit
    inference_mode: str = "auto"  # auto|offline|local|cloud (resolved by resolve_mode)
    local_base_url: str = "http://127.0.0.1:11434/v1"  # ollama default
    local_model: str = "llama3.1"
    gguf_model_path: str = ""  # a .gguf file -> true offline inference (llama-cpp)
    local_vision_model: str = "llava"
    local_stt: str = "http://127.0.0.1:11434"
    vision_model: str = ""  # cloud vision model override

    # Memory / persona / health roots (configurable; default to what exists) -
    hermes_home: str = "~/.hermes"
    digigio_home: str = "~/digigio"  # mounted digigio brain (persona/health)
    memory_file: str = "MEMORY.md"
    user_file: str = "USER.md"
    # Cyclops writes its OWN memory here so it never clobbers the user's real
    # ~/.hermes/MEMORY.md / USER.md.
    memory_root: str = "~/.cyclops/memory"
    memory_max_chars: int = 240  # per-card char budget (Hermes-style, cache-cheap)
    memory_max_cards: int = 200  # hard cap on card COUNT per target (FIFO evict oldest)
    memory_dedup: bool = (
        True  # skip re-appending an identical card (learning-loop spam guard)
    )
    memory_recall: int = 8  # how many persisted turns to inject as context
    cascade_enabled: bool = True  # try providers in order, skip burnt keys
    config_dir: str = "~/.config/cyclops"  # P2-A: plugin registry root
    plugin_index_url: str = ""  # P2-A: marketplace index (empty = offline)

    # Skills --------------------------------------------------------------
    skills_dirs: list[str] = field(default_factory=lambda: ["~/.hermes/skills"])

    # Device transport (how the app reaches the wearable) ------------------
    device_transport: str = "wifi"  # wifi|bt|cable
    device_host: str = "192.168.1.50"
    device_port: int = 8080
    camera_source: str = "openglass"  # openglass|xiao|phone (P0-B)

    # Privacy (P0-D, Omi-style Consent Mode) ----------------------------
    consent_mode: bool = True  # when off, capture/recording is refused

    # Safety --------------------------------------------------------------
    terminal_confirm: bool = True  # require confirm before shell exec
    allow_fs_write: bool = False

    # Customization -------------------------------------------------------
    persona: str = ""  # companion-app persona (mirrors system_note)
    system_note: str = ""  # extra system prompt text
    max_tool_iter: int = 6
    tool_overrides: dict = field(
        default_factory=dict
    )  # tool -> {provider,model,endpoint,key}

    # ---- JSON profile (companion settings persist here) ----
    def to_dict(self) -> dict:
        out = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            out[k] = v
        return out

    def save(self, path: str):
        """Persist the full profile (incl. per-tool overrides) to JSON."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)

    @classmethod
    def load_json(cls, path: str) -> "AgentConfig":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        cfg = cls()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    @classmethod
    def load(
        cls, path: Optional[str] = None, env: Optional[dict] = None
    ) -> "AgentConfig":
        env = env if env is not None else dict(os.environ)
        cfg = cls()
        if path and os.path.exists(path):
            cfg._from_file(path)
        # env overrides
        if env.get("CYCLOPS_MODEL"):
            cfg.model = env["CYCLOPS_MODEL"]
        if env.get("CYCLOPS_PROVIDER"):
            cfg.provider = env["CYCLOPS_PROVIDER"]
        if env.get("CYCLOPS_BASE_URL"):
            cfg.base_url = env["CYCLOPS_BASE_URL"]
        if env.get("CYCLOPS_LOCAL") in ("1", "true", "yes"):
            cfg.local_mode = True
        if env.get("CYCLOPS_LOCAL_FIRST") in ("0", "false", "no"):
            cfg.local_first = False
        if env.get("CYCLOPS_INFERENCE_MODE") in ("offline", "local", "cloud", "auto"):
            cfg.inference_mode = env["CYCLOPS_INFERENCE_MODE"]
        if env.get("CYCLOPS_DEVICE_HOST"):
            cfg.device_host = env["CYCLOPS_DEVICE_HOST"]
        if env.get("CYCLOPS_DEVICE_TRANSPORT"):
            cfg.device_transport = env["CYCLOPS_DEVICE_TRANSPORT"]
        if env.get("CYCLOPS_CAMERA_SOURCE"):
            cfg.camera_source = env["CYCLOPS_CAMERA_SOURCE"]
        if env.get("CYCLOPS_CONSENT") in ("0", "false", "no"):
            cfg.consent_mode = False
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
                        if k == "default":
                            self.model = v
                        elif k == "provider":
                            self.provider = v
                        elif k == "base_url":
                            self.base_url = v
                    continue
                k, _, v = line.partition(":")
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "model":
                    section = "model"
                    continue
                section = None
                if k == "local_mode":
                    self.local_mode = v in ("true", "1", "yes")
                elif k == "local_first":
                    self.local_first = v in ("true", "1", "yes")
                elif k == "inference_mode":
                    self.inference_mode = v
                elif k == "local_base_url":
                    self.local_base_url = v
                elif k == "device_transport":
                    self.device_transport = v
                elif k == "device_host":
                    self.device_host = v
                elif k == "consent_mode":
                    self.consent_mode = v in ("true", "1", "yes")
                elif k == "terminal_confirm":
                    self.terminal_confirm = v in ("true", "1", "yes")

    def effective_endpoint(self, provider: str | None = None) -> str:
        """Resolve the OpenAI-compatible base_url for the current provider."""
        prov = provider or self.provider
        if self.local_mode or prov in ("ollama", "lmstudio", "custom"):
            return self.local_base_url or self.base_url or "http://127.0.0.1:11434/v1"
        if self.base_url:
            return self.base_url
        # per-provider endpoint (static ai_api.txt/.env entry, or an
        # authenticated OAuth device-flow provider's api_base_url) takes
        # priority over the hardcoded OpenRouter default -- without this, a
        # provider whose *key* resolves correctly (resolve_key() below does
        # consult AiKeys generically) still had every request sent to
        # OpenRouter's URL regardless.
        if prov and prov != "auto":
            try:
                from brain.aikeys import AiKeys

                ep = AiKeys().get_endpoint(prov)
                if ep:
                    return ep
            except Exception:
                pass  # AiKeys is best-effort here; fall through to the default
        return "https://openrouter.ai/api/v1"

    def provider_for(self, capability: str) -> dict:
        """Return a per-capability provider override if configured in env.

        capability in: vision | stt | chat.  Looks for CYCLOPS_<CAP>_PROVIDER /
        CYCLOPS_<CAP>_ENDPOINT / CYCLOPS_<CAP>_MODEL. Falls back to base config.
        """
        cap = capability.upper()
        prov = os.environ.get(f"CYCLOPS_{cap}_PROVIDER", self.provider)
        endpoint = os.environ.get(f"CYCLOPS_{cap}_ENDPOINT", self.effective_endpoint())
        model = os.environ.get(f"CYCLOPS_{cap}_MODEL", self.model)
        return {"provider": prov, "endpoint": endpoint, "model": model}

    def resolve_mode(self) -> str:
        """Resolve the effective inference mode (P1-B local-first policy).

        - explicit cloud -> cloud (only when the user opted in)
        - local_first + local_mode -> local
        - local_first (default) -> offline unless a local model is reachable
        - auto -> local-first offline by default
        """
        m = self.inference_mode
        if m == "cloud":
            return "cloud"
        if m == "offline":
            return "offline"
        if m == "local" or self.local_mode:
            return "local"
        # auto / local_first default: stay offline-first
        return "offline" if self.local_first else "cloud"

    def resolve_key(self, keys=None, provider: str | None = None):
        """Best-effort API key: explicit -> env -> ai key store."""
        if self.api_key:
            return self.api_key
        prov = provider or self.provider
        if prov != "auto":
            envk = prov.upper() + "_API_KEY"
            if os.environ.get(envk):
                return os.environ[envk]
        # try the cyclops ai key store
        try:
            from brain.aikeys import AiKeys

            k = AiKeys()
            for name in (prov, "openrouter", "openai", "groq"):
                if name == "auto":
                    continue
                val = k.get_key(name) or k.get_key(name + "_api_key")
                if val:
                    return val
        except Exception:
            pass
        return (
            os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )
