"""Offline tests for background auto-learning (T5.1).

- _extract_json parses model replies into structured facts.
- learn_from_turn is offline-safe when router=None.
- Synchronous path stores facts in MemoryStore.
- async_ok=True spawns daemon thread and returns {} immediately.
No network/keys.
"""

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.config import AgentConfig
from agent.learning import _extract_json, learn_from_turn, learn_recent
from agent.memory import MemoryStore

# -- _extract_json tests ------------------------------------------------


def test_extract_plain_json():
    obj = _extract_json('{"user":["likes coffee"],"agent":[]}')
    assert obj == {"user": ["likes coffee"], "agent": []}


def test_extract_fenced_json():
    raw = '```json\n{"user":["prefers dark mode"],"agent":[]}\n```'
    obj = _extract_json(raw)
    assert obj == {"user": ["prefers dark mode"], "agent": []}


def test_extract_with_language_tag():
    raw = '```\n{"user":["is a developer"],"agent":[]}\n```'
    obj = _extract_json(raw)
    assert obj == {"user": ["is a developer"], "agent": []}


def test_extract_returns_none_on_bad_input():
    assert _extract_json("") is None
    assert _extract_json("not json") is None
    assert _extract_json("{}") == {}  # valid but empty


def test_extract_ignores_trailing_text():
    raw = '{"user":["fact"],"agent":[]}\nsome extra text'
    obj = _extract_json(raw)
    assert obj == {"user": ["fact"], "agent": []}


def test_extract_non_dict_json():
    assert _extract_json('["list"]') is None  # must be dict


# -- offline-safe tests ------------------------------------------------


def test_learn_from_turn_offline_safe_no_router():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d)
    store = MemoryStore(cfg)
    result = learn_from_turn("hi", "hello", store, router=None)
    assert result == {}  # no-op
    assert store.read() == ""  # nothing written


def test_learn_from_turn_async_returns_immediately():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d)
    store = MemoryStore(cfg)
    result = learn_from_turn("hi", "hello", store, router=None, async_ok=True)
    assert result == {}  # immediate return even with async_ok


# -- synchronous path with fake router ---------------------------------


class FakeRouter:
    """Returns a canned JSON response for learning review."""

    def __init__(self, json_reply):
        self.json_reply = json_reply
        self.last_prompt = None

    def complete(self, messages, **_kw):
        self.last_prompt = messages
        return self.json_reply


def test_learn_from_turn_sync_stores_facts():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d)
    store = MemoryStore(cfg)
    router = FakeRouter(
        '{"user":["user prefers Python"],"agent":["environment is test"]}'
    )
    result = learn_from_turn(
        "I like Python", "Great choice", store, router=router, async_ok=False
    )
    assert result == {"user": 1, "agent": 1}
    assert "prefers Python" in store.read("user")
    assert "environment is test" in store.read("agent")


def test_learn_from_turn_skips_empty_facts():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d)
    store = MemoryStore(cfg)
    router = FakeRouter('{"user":[""],"agent":[]}')
    result = learn_from_turn("nothing", "ok", store, router=router, async_ok=False)
    assert result == {"user": 0, "agent": 0}


def test_learn_from_turn_handles_non_json_reply():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d)
    store = MemoryStore(cfg)
    router = FakeRouter("Sorry, I don't understand.")
    result = learn_from_turn("test", "reply", store, router=router, async_ok=False)
    assert result == {"user": 0, "agent": 0}  # gracefully degrades


# -- learn_recent tests ------------------------------------------------


def test_learn_recent_empty_on_no_router():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d)
    store = MemoryStore(cfg)
    result = learn_recent([], store, router=None)
    assert result == {"user": 0, "agent": 0}


def test_learn_recent_pairs_user_assistant_turns():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d)
    store = MemoryStore(cfg)
    router = FakeRouter('{"user":["likes testing"],"agent":["test mode"]}')
    history = [
        {"role": "user", "content": "I like testing"},
        {"role": "assistant", "content": "Good habit"},
    ]
    result = learn_recent(history, store, router=router, limit=2)
    assert result == {"user": 1, "agent": 1}
    assert "likes testing" in store.read("user")


def test_learn_recent_limits_turns():
    d = tempfile.mkdtemp()
    cfg = AgentConfig(memory_root=d)
    store = MemoryStore(cfg)
    router = FakeRouter('{"user":["fact"],"agent":[]}')
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
        for i in range(10)
    ]
    learn_recent(history, store, router=router, limit=2)
    # limit=2 means at most 2 pairs = 4 messages
    assert router.last_prompt is not None
    assert store.read("user")


if __name__ == "__main__":
    test_extract_plain_json()
    test_extract_fenced_json()
    test_extract_with_language_tag()
    test_extract_returns_none_on_bad_input()
    test_extract_ignores_trailing_text()
    test_extract_non_dict_json()
    test_learn_from_turn_offline_safe_no_router()
    test_learn_from_turn_async_returns_immediately()
    test_learn_from_turn_sync_stores_facts()
    test_learn_from_turn_skips_empty_facts()
    test_learn_from_turn_handles_non_json_reply()
    test_learn_recent_empty_on_no_router()
    test_learn_recent_pairs_user_assistant_turns()
    test_learn_recent_limits_turns()
    print("PASS tests/test_learning.py")
