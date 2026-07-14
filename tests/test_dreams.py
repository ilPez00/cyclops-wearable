"""Dream/proposal loop: LLM review + offline fallback + dismiss. Offline."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.dreams import DreamStore, review


def _s():
    return DreamStore(path=os.path.join(tempfile.mkdtemp(), "dreams.jsonl"))


class FakeRouter:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, messages, **kw):
        class R:
            text = self.reply

        return R()


def test_review_uses_router_json():
    store = _s()
    router = FakeRouter(
        '{"dreams":[{"kind":"proposal","message":"batch the antenna order"}]}'
    )
    rows = review(["a note"], [], router=router, store=store)
    assert len(rows) == 1 and rows[0]["kind"] == "proposal"
    assert store.active()[0]["message"] == "batch the antenna order"
    print("OK review parses model dreams into the store")


def test_review_falls_back_offline():
    store = _s()
    # no router -> rule-based fallback fires on a weak domain
    doms = [{"domain": "study", "avg": 0.2, "count": 3, "pdca": "Check"}]
    rows = review(notes=[], domains=doms, router=None, store=store)
    assert rows and "study" in rows[0]["message"]
    print("OK offline fallback proposes on weak domains")


def test_review_bad_json_falls_back():
    store = _s()
    rows = review(
        ["n1", "n2", "n3", "n4", "n5"], [], router=FakeRouter("not json"), store=store
    )
    assert rows  # fallback (>=5 notes) still produces something
    print("OK bad model output degrades to fallback, never empty-crashes")


def test_dismiss_hides_dream():
    store = _s()
    d = store.add("insight", "x")
    assert len(store.active()) == 1
    assert store.dismiss(d["id"])
    assert store.active() == []
    print("OK dismiss removes a dream from active")
