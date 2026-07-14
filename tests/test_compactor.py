"""Memory compaction: distill old cards, keep recent, offline-safe. Offline."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.compactor import compact
from agent.config import AgentConfig
from agent.memory import MemoryStore


def _store():
    return MemoryStore(
        AgentConfig(memory_root=tempfile.mkdtemp(), memory_max_cards=1000)
    )


class FakeRouter:
    def __init__(self, reply):
        self.reply = reply
        self.seen = None

    def chat(self, messages, **kw):
        self.seen = messages

        class R:
            text = self.reply

        return R()


def test_noop_without_router():
    s = _store()
    for i in range(100):
        s.append(f"card {i}")
    r = compact(s, router=None)
    assert r["compacted"] == 0 and len(s.list()) == 100
    print("OK no router -> no-op, nothing lost")


def test_noop_when_too_few_cards():
    s = _store()
    for i in range(10):
        s.append(f"card {i}")
    r = compact(s, router=FakeRouter('{"facts":["x"]}'), keep_recent=20, batch_min=30)
    assert r["compacted"] == 0 and len(s.list()) == 10
    print("OK too few cards -> no-op")


def test_compacts_old_keeps_recent():
    s = _store()
    for i in range(60):
        s.append(f"card {i}")
    router = FakeRouter('{"facts":["distilled A","distilled B"]}')
    r = compact(s, router=router, keep_recent=20, batch_min=30, max_facts=8)
    assert r["removed"] == 40 and r["compacted"] == 2
    texts = [c.text for c in s.list()]
    # newest 20 preserved, old 40 replaced by 2 distilled facts
    assert "card 59" in texts and "card 40" in texts  # recent kept
    assert "card 0" not in texts and "card 39" not in texts  # old gone
    assert "distilled A" in texts and "distilled B" in texts
    assert len(texts) == 22
    print("OK compaction distills old cards, preserves recent")


def test_bad_model_output_is_safe():
    s = _store()
    for i in range(60):
        s.append(f"card {i}")
    r = compact(s, router=FakeRouter("not json"), keep_recent=20, batch_min=30)
    assert r["compacted"] == 0 and len(s.list()) == 60  # untouched
    print("OK unparseable output -> nothing removed")
