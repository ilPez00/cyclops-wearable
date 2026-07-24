"""Provider cascade: fall through burnt keys, back off by status. Offline."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.cascade import CascadingRouter, backoff_for, build_router
from agent.config import AgentConfig
from agent.models import ModelRouter


class FakeKeys:
    def __init__(self, names):
        self._names = list(names)

    def available(self):
        return list(self._names)


class FakeResp:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def json(self):
        return self._body


class ScriptedSession:
    """Returns a queued (status, body) per POST; records the endpoints hit."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=30, files=None):
        self.calls.append(url)
        status, body = self.script.pop(0)
        return FakeResp(status, body)


_OK = {"choices": [{"message": {"content": "hi", "tool_calls": []}}]}


def _cfg():
    c = AgentConfig()
    c.provider = ""  # force endpoint resolution per-provider
    return c


def test_backoff_by_status():
    assert backoff_for(401) == 3600.0
    assert backoff_for(429) == 300.0
    assert backoff_for(503) == 60.0
    assert backoff_for(0) == 30.0
    assert backoff_for(500) == 15.0


def test_cascade_falls_through_dead_provider_to_next():
    # first provider 429s, second succeeds
    sess = ScriptedSession([(429, {"error": "rate"}), (200, _OK)])
    r = CascadingRouter(_cfg(), session=sess, keys=FakeKeys(["groq", "openrouter"]))
    res = r.chat([{"role": "user", "content": "hey"}])
    assert res.text == "hi"
    assert len(sess.calls) == 2  # tried groq then openrouter
    print("OK cascade falls through a rate-limited provider")


def test_dead_provider_skipped_until_backoff():
    sess = ScriptedSession([(401, {}), (200, _OK), (200, _OK)])
    r = CascadingRouter(_cfg(), session=sess, keys=FakeKeys(["groq", "openrouter"]))
    r.chat([{"role": "user", "content": "1"}])  # groq 401 -> dead 1h, openrouter ok
    # next call must skip groq entirely (still on cooldown) and hit openrouter
    r.chat([{"role": "user", "content": "2"}])
    assert sess.calls[1].__class__  # sanity
    # 3 posts total: groq(401), openrouter, openrouter — groq skipped 2nd round
    assert len(sess.calls) == 3
    print("OK burnt key skipped until its backoff expires")


def test_all_dead_raises_last_error():
    sess = ScriptedSession([(500, {}), (500, {})])
    r = CascadingRouter(_cfg(), session=sess, keys=FakeKeys(["groq", "openrouter"]))
    # fcm/OmniRoute is tried before the keyed cascade (priority 0, see chat());
    # this test is about the keyed-provider list exhausting, so pre-mark fcm
    # dead rather than consuming one of the two scripted responses on it.
    r._dead_until["fcm"] = time.time() + 999
    try:
        r.chat([{"role": "user", "content": "x"}])
        assert False, "should raise when every provider fails"
    except Exception as e:
        assert "HTTP 500" in str(e)
    print("OK exhausted cascade raises the last error")


def test_build_router_gates_on_key_count():
    # <=1 provider -> plain ModelRouter (no cascade)
    one = build_router(_cfg(), keys=FakeKeys(["groq"]))
    assert isinstance(one, ModelRouter) and not isinstance(one, CascadingRouter)
    many = build_router(_cfg(), keys=FakeKeys(["groq", "openrouter"]))
    assert isinstance(many, CascadingRouter)
    print("OK cascade only engages with >1 keyed provider")


def test_explicit_provider_bypasses_cascade():
    sess = ScriptedSession([(200, _OK)])
    r = CascadingRouter(_cfg(), session=sess, keys=FakeKeys(["groq", "openrouter"]))
    res = r.chat([{"role": "user", "content": "x"}], provider="openai")
    assert res.text == "hi" and len(sess.calls) == 1
    print("OK explicit provider= bypasses the cascade")
