"""GGUF offline backend + text tool-call parser + cascade fallback. Offline.

No llama-cpp-python and no model needed: a fake Llama is injected.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.cascade import CascadingRouter
from agent.config import AgentConfig
from agent.models import ModelError
from brain.gguf_backend import GgufRouter, available, parse_tool_calls


class FakeLlama:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def create_chat_completion(self, messages, temperature=0.4):
        self.calls += 1
        return {"choices": [{"message": {"content": self.content}}]}


def test_parse_tool_calls_from_text():
    txt = 'sure <tool_call>{"name":"web_search","arguments":{"q":"cats"}}</tool_call>'
    tc = parse_tool_calls(txt)
    assert tc and tc[0]["function"]["name"] == "web_search"
    assert '"cats"' in tc[0]["function"]["arguments"]
    # fenced json form
    tc2 = parse_tool_calls('```json\n{"name":"calc","arguments":{"x":1}}\n```')
    assert tc2 and tc2[0]["function"]["name"] == "calc"
    # no tool call -> empty
    assert parse_tool_calls("just a plain answer") == []
    print("OK tool calls parsed from GGUF text (native tool_calls absent)")


def test_gguf_router_returns_chat_result():
    r = GgufRouter("/nope.gguf", llama=FakeLlama("hello from gguf"))
    res = r.chat([{"role": "user", "content": "hi"}])
    assert res.text == "hello from gguf" and res.tool_calls == []
    print("OK GgufRouter yields a ChatResult")


def test_gguf_parses_tools_only_when_requested():
    r = GgufRouter("/nope.gguf", llama=FakeLlama('<tool_call>{"name":"t"}</tool_call>'))
    with_tools = r.chat([{"role": "user", "content": "x"}], tools=[{"x": 1}])
    assert with_tools.tool_calls and with_tools.tool_calls[0]["function"]["name"] == "t"
    without = r.chat([{"role": "user", "content": "x"}])
    assert without.tool_calls == []  # not requested -> not parsed
    print("OK tools parsed only when tools= is passed")


def test_available_checks_path_exists():
    cfg = AgentConfig()
    assert available(cfg) is False  # unset
    with tempfile.NamedTemporaryFile(suffix=".gguf") as f:
        cfg.gguf_model_path = f.name
        assert available(cfg) is True
    print("OK available() gates on a real .gguf path")


def test_cascade_falls_back_to_gguf_when_cloud_dead():
    # cloud provider 500s, GGUF slot answers -> offline resilience
    class DeadSession:
        class R:
            status = 500

            def json(self):
                return {"error": "down"}

        def post(self, *a, **k):
            return self.R()

    class FakeKeys:
        def available(self):
            return ["groq"]

    gg = GgufRouter("/nope.gguf", llama=FakeLlama("offline answer"))
    r = CascadingRouter(AgentConfig(), session=DeadSession(), keys=FakeKeys(), gguf=gg)
    res = r.chat([{"role": "user", "content": "x"}])
    assert res.text == "offline answer"
    print("OK cascade falls back to local GGUF when cloud is dead")


def test_gguf_inference_error_is_model_error():
    class Boom:
        def create_chat_completion(self, **k):
            raise RuntimeError("oom")

    r = GgufRouter("/nope.gguf", llama=Boom())
    try:
        r.chat([{"role": "user", "content": "x"}])
        assert False
    except ModelError as e:
        assert e.status == 0
    print("OK GGUF failure raises ModelError (cascade can classify)")
