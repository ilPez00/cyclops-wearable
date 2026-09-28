"""Tests for brain/translator.py — local-first cascade.

Ollama when reachable, dict otherwise, identity never an error string.
The runner is pytest-free (see tests/run_tests.py), so the Ollama gate is
a runtime probe: live assertions run when the daemon is up, the offline
fallback path always runs.
"""

import os

from brain.translator import (
    DictTranslator,
    OllamaTranslator,
    _dict_translate,
    get_translator,
)


def _ollama_up() -> bool:
    if os.environ.get("CYCLOPS_NO_OLLAMA"):
        return False
    try:
        OllamaTranslator(timeout=5.0).translate("ciao")
        return True
    except RuntimeError:
        return False


def test_dict_is_deterministic():
    assert _dict_translate("ciao mondo") == "hello mondo"
    assert DictTranslator().translate("grazie") == "thank you"


def test_forced_dict_path():
    t = get_translator(prefer="dict")
    assert t.name == "dict"
    assert t.translate("buongiorno") == "good morning"


def test_unknown_words_pass_through():
    # never an error string dressed as a translation
    assert DictTranslator().translate("xyzzy plugh") == "xyzzy plugh"


def test_live_or_fallback_end_to_end():
    # with the daemon up: real sentence translation; without: the dict
    # still answers a known word. Either way no exception, no stub text.
    t = get_translator()
    if t.name == "ollama":
        out = t.translate("Dove si trova la stazione?")
        assert "station" in out.lower()
    else:
        assert t.translate("ciao") == "hello"
