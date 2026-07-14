"""Provider cascade — try configured providers in order, skip burnt keys.

Ported from pika-hermes's ProviderCascade (its "40-provider cloud cascade"),
adapted to Cyclops's Python ModelRouter. A single dead OpenRouter key used to
be a hard failure; the cascade falls through to the next provider that has a
key and self-heals: a provider that returns 401/429/503 is skipped until a
per-status backoff expires.

Sequential by design (KISS); parallel racing is a possible v2. Uses the same
AiKeys store the rest of the brain uses, so no new configuration surface.
"""

from __future__ import annotations

import time

from .models import ChatResult, ModelError, ModelRouter

# Default try-order. Only providers with a key/endpoint in the store are used;
# the sketchy keyless-proxy / public-Ollama slots from pika are deliberately
# NOT included (security + reliability).
DEFAULT_ORDER = [
    "groq",
    "openrouter",
    "deepinfra",
    "together",
    "openai",
    "anthropic",
    "gemini",
    "mistral",
]


def backoff_for(status: int) -> float:
    """Seconds to skip a provider after a failure, by HTTP status.
    Mirrors pika's ProviderCascade.backoffFor."""
    if status == 401 or status == 403:
        return 3600.0  # bad key: an hour
    if status == 429:
        return 300.0  # rate/quota: 5 min
    if status == 503:
        return 60.0  # overloaded: 1 min
    if status == 0:
        return 30.0  # transport/timeout
    return 15.0  # anything else


class CascadingRouter:
    """Wraps a ModelRouter; iterates providers, skipping ones on cooldown."""

    def __init__(self, config, session=None, keys=None, order=None, gguf=None):
        self.cfg = config
        self.router = ModelRouter(config, session=session)
        self._keys = keys
        self.order = order or list(DEFAULT_ORDER)
        self._dead_until: dict[str, float] = {}
        # optional last-resort GGUF slot (true offline inference); only used
        # when configured, and always tried AFTER cloud providers
        self._gguf = gguf

    def _providers(self) -> list[str]:
        """Configured providers in try-order (only ones with a key/endpoint)."""
        if self._keys is None:
            from brain.aikeys import AiKeys

            self._keys = AiKeys()
        have = set(self._keys.available())
        ordered = [p for p in self.order if p in have]
        # any keyed provider not in the explicit order goes last
        ordered += sorted(have - set(ordered))
        return ordered

    def _alive(self, name: str, now: float) -> bool:
        return self._dead_until.get(name, 0.0) <= now

    def chat(self, messages, **kw) -> ChatResult:
        """Try each live provider in order; return the first success.
        Raises ModelError only after every provider is exhausted."""
        # an explicit provider= bypasses the cascade (caller knows best)
        if kw.get("provider"):
            return self.router.chat(messages, **kw)
        now = time.time()
        providers = self._providers()
        if not providers:
            return self.router.chat(messages, **kw)  # no keys: let it degrade
        last: ModelError | None = None
        tried = 0
        for name in providers:
            if not self._alive(name, now):
                continue
            tried += 1
            try:
                return self.router.chat(messages, provider=name, **kw)
            except ModelError as e:
                last = e
                self._dead_until[name] = time.time() + backoff_for(e.status)
                continue
        # cloud exhausted (or all on cooldown) -> fall back to local GGUF
        if self._gguf is not None:
            try:
                return self._gguf.chat(messages, **kw)
            except ModelError as e:
                last = last or e
        if last is not None:
            raise last
        # every provider was on cooldown and no GGUF — try soonest-reviving
        soonest = min(providers, key=lambda n: self._dead_until.get(n, 0.0))
        return self.router.chat(messages, provider=soonest, **kw)


def build_router(config, session=None, keys=None):
    """Return a CascadingRouter when several providers have keys OR a GGUF
    model is configured (offline fallback), else a plain ModelRouter."""
    k = keys
    if k is None:
        from brain.aikeys import AiKeys

        k = AiKeys()
    # optional last-resort local model (true offline inference)
    gguf = None
    try:
        from brain import gguf_backend

        if gguf_backend.available(config):
            gguf = gguf_backend.GgufRouter(
                model_path=getattr(config, "gguf_model_path", "")
            )
    except Exception:
        gguf = None
    engage = (len(k.available()) > 1 or gguf is not None) and getattr(
        config, "cascade_enabled", True
    )
    if engage:
        return CascadingRouter(config, session=session, keys=k, gguf=gguf)
    return ModelRouter(config, session=session)


__all__ = ["CascadingRouter", "build_router", "backoff_for", "DEFAULT_ORDER"]
