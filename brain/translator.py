"""Translation backend — pluggable, local-first (mirrors brain/transcriber.py).

Cascade: Ollama (gemma3:4b, OpenAI-compatible /api/chat on localhost:11434)
-> tiny built-in IT dict -> identity (source returned unchanged, never an
error string dressed as a translation). Stdlib-only, session injectable so
tests run offline. A miss here is silent, not an error surfaced to the
wearer; this feeds gestures, not chat.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Optional

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "gemma3:4b"

_IT_FALLBACK = {
    "ciao": "hello",
    "buongiorno": "good morning",
    "grazie": "thank you",
    "si": "yes",
    "no": "no",
    "note": "note",
    "riunione": "meeting",
    "g2": "g2",
}


def _dict_translate(text: str) -> str:
    return " ".join(_IT_FALLBACK.get(w, w) for w in text.lower().split())


class Translator:
    name = "base"

    def translate(self, text: str, target: str = "English") -> str:
        raise NotImplementedError


class DictTranslator(Translator):
    name = "dict"

    def translate(self, text: str, target: str = "English") -> str:
        return _dict_translate(text)


class OllamaTranslator(Translator):
    """Local LLM translation via Ollama's /api/chat (OpenAI-ish, stdlib HTTP).

    Raises RuntimeError when the daemon/model is unreachable so the caller
    (get_translator) can fall through to the dict. Prompt pins the output
    shape (translation only) because chat models otherwise narrate.
    """

    name = "ollama"

    def __init__(self, model: str = OLLAMA_MODEL, url: str = OLLAMA_URL,
                 timeout: float = 60.0):
        self.model = model
        self.url = url
        self.timeout = timeout

    def translate(self, text: str, target: str = "English") -> str:
        body = json.dumps({
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system",
                 "content": f"Translate the user's text to {target}. "
                            "Reply with ONLY the translation, no quotes, "
                            "no commentary, no explanation."},
                {"role": "user", "content": text},
            ],
        }).encode()
        try:
            req = urllib.request.Request(
                self.url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.load(resp)
            out = (data.get("message", {}).get("content") or "").strip()
        except Exception as e:
            raise RuntimeError(f"ollama translation unavailable: {e}")
        if not out:
            raise RuntimeError("ollama translation empty")
        return out


def get_translator(prefer: str = "auto") -> Translator:
    """auto: Ollama if reachable -> dict. Anything else: dict.

    The probe is one real localhost call ("ciao" -> English); when the
    daemon is down it fails in ~ms (connection refused), so auto costs
    nothing offline. TheProbeTranslator below reuses the probe result so
    the first real translation does not pay for a second call.
    """
    if prefer in ("auto", "ollama"):
        try:
            t = OllamaTranslator()
            first = t.translate("ciao", target="English")
            if first.lower().strip() == "hello":
                return t
        except RuntimeError:
            pass
    return DictTranslator()
