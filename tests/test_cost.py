"""Cost tracker: per-provider token + USD tally, JSONL-persisted. Offline."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.cost import CostTracker


def _t():
    return CostTracker(path=os.path.join(tempfile.mkdtemp(), "costs.jsonl"))


def test_record_and_summary_tallies_per_provider():
    c = _t()
    c.record("groq", "groq", 1000, 500)
    c.record("groq", "groq", 2000, 1000)
    c.record("openai", "openai/gpt-4o-mini", 1_000_000, 1_000_000)
    s = c.summary()
    assert s["total"]["calls"] == 3
    assert s["providers"]["groq"]["in"] == 3000
    assert s["providers"]["groq"]["out"] == 1500
    # gpt-4o-mini: 0.15 in + 0.60 out per 1M -> 0.75 for 1M+1M
    assert abs(s["providers"]["openai"]["usd"] - 0.75) < 1e-6
    assert s["total"]["usd"] > 0
    print("OK cost tallies tokens + USD per provider")


def test_unknown_provider_costs_zero_but_counts_tokens():
    c = _t()
    usd = c.record("mystery", "who/knows", 5000, 5000)
    assert usd == 0.0
    s = c.summary()
    assert (
        s["providers"]["mystery"]["in"] == 5000
        and s["providers"]["mystery"]["usd"] == 0.0
    )
    print("OK unknown provider: 0 USD, tokens still counted")


def test_summary_empty_is_safe():
    c = _t()
    s = c.summary()
    assert s["providers"] == {} and s["total"]["calls"] == 0
    print("OK empty summary is safe")


def test_router_tallies_when_tracker_wired():
    from agent.config import AgentConfig
    from agent.models import ModelRouter

    class FakeResp:
        status = 200

        def json(self):
            return {
                "choices": [{"message": {"content": "hi", "tool_calls": []}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 4},
            }

    class FakeSession:
        def post(self, *a, **k):
            return FakeResp()

    c = _t()
    r = ModelRouter(AgentConfig(), session=FakeSession(), cost_tracker=c)
    r.chat([{"role": "user", "content": "x"}], provider="groq", model="groq")
    s = c.summary()
    assert s["total"]["in"] == 10 and s["total"]["out"] == 4
    print("OK ModelRouter records usage into the tracker")
