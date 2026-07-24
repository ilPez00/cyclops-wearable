"""Offline tests for the agent core (no network, no keys)."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(
    0, os.path.dirname(os.path.dirname(__file__))
)  # repo root for 'agent' pkg

from agent.config import AgentConfig
from agent.loop import Agent
from agent.memory import MemoryStore
from agent.models import ChatResult
from agent.skills import Skills
from agent.tools import build_registry
from agent.tools.whatsapp import parse_export


# --- fake model router: first calls a tool, then answers -----------------
class FakeRouter:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools=None, temperature=0.4, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return ChatResult(
                text="",
                tool_calls=[
                    {
                        "function": {
                            "name": "whatsapp_export",
                            "arguments": json.dumps({"path": "/tmp/fake_wa.txt"}),
                        }
                    }
                ],
            )
        return ChatResult(text="Parsed the WhatsApp export and found the chat.")


def test_loop_executes_tool_then_answers():
    cfg = AgentConfig()
    reg = build_registry(cfg)
    agent = Agent(cfg, router=FakeRouter(), registry=reg, max_iter=5)
    # create a fake whatsapp export the tool can read
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("12/04/2026, 14:33 - Marco: hey\n12/04/2026, 14:34 - You: hi marco\n")
        path = f.name
    # patch the tool to read our temp file
    reg._tools["whatsapp_export"].run = lambda a: (
        f"participants: Marco, You (read {path})"
    )
    res = agent.run("summarize my whatsapp with Marco")
    assert res.tool_calls == 1, res.steps
    assert "WhatsApp" in res.text, res.text
    assert res.steps[0]["tool"] == "whatsapp_export"
    os.unlink(path)


def test_whatsapp_parser():
    txt = (
        "12/04/2026, 14:33 - Marco: are we still on for friday?\n"
        "12/04/2026, 14:34 - You: yes, 3pm\n"
        "12/04/2026, 14:35 - Marco: perfect\n"
    )
    d = parse_export(txt)
    assert "Marco" in d["participants"] and "You" in d["participants"]
    assert d["counts"]["Marco"] == 2
    assert "friday" in d["threads"]["Marco"][0]


def test_terminal_tool_guarded():
    cfg = AgentConfig(terminal_confirm=True)
    reg = build_registry(cfg)
    # destructive command refused without UI confirm callback
    out = reg.run("terminal", {"command": "rm -rf /"})
    assert "cancelled" in out or "error" in out, out
    # safe command allowed
    out2 = reg.run("terminal", {"command": "echo hello"})
    assert "hello" in out2, out2


def test_memory_reads_empty_when_absent():
    cfg = AgentConfig(digigio_home="/no/such", memory_root=tempfile.mkdtemp())
    mem = MemoryStore(cfg).read()
    assert mem == ""  # empty -> '' (card store markdown)


def test_local_mode_endpoint():
    cfg = AgentConfig(local_mode=True, local_base_url="http://127.0.0.1:1234/v1")
    assert cfg.effective_endpoint() == "http://127.0.0.1:1234/v1"


def test_agent_router_explicit_none_stays_none_not_auto_cascade():
    # Regression: Agent(cfg, router=None, ...) used to be indistinguishable
    # from omitting router= entirely (both defaulted the same way), so an
    # explicit "no router" call silently built a real CascadingRouter instead
    # -- which can make real outbound network calls to whatever providers
    # happen to have keys on the host. router=None must mean exactly that.
    cfg = AgentConfig()
    a = Agent(cfg, router=None)
    assert a.router is None
    # omitting router= is unaffected -- still auto-builds a router (may be a
    # plain ModelRouter or a CascadingRouter depending on how many provider
    # keys this host has; either way it must not be None)
    a2 = Agent(cfg)
    assert a2.router is not None


def test_effective_endpoint_falls_back_to_aikeys_per_provider_endpoint():
    # Regression: a provider's *key* already resolved via AiKeys generically
    # (resolve_key()), but effective_endpoint() ignored AiKeys' endpoint for
    # every provider except ollama/lmstudio/custom, silently sending every
    # cascade-routed request to the hardcoded OpenRouter URL instead.
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "ai_api.txt")
        with open(p, "w") as f:
            f.write("groq:gsk_test\ngroq_endpoint:https://api.groq.com/openai/v1\n")
        old = os.environ.get("CYCLOPS_AI_API_TXT")
        os.environ["CYCLOPS_AI_API_TXT"] = p
        try:
            cfg = AgentConfig()  # provider left as "" via effective_endpoint(provider=)
            assert cfg.effective_endpoint(provider="groq") == "https://api.groq.com/openai/v1"
            # a provider with no AiKeys entry at all still falls back to the default
            assert cfg.effective_endpoint(provider="totally_unknown_provider") == "https://openrouter.ai/api/v1"
            # explicit base_url still wins over any per-provider lookup
            cfg.base_url = "https://my-proxy.example/v1"
            assert cfg.effective_endpoint(provider="groq") == "https://my-proxy.example/v1"
        finally:
            if old is None:
                os.environ.pop("CYCLOPS_AI_API_TXT", None)
            else:
                os.environ["CYCLOPS_AI_API_TXT"] = old


def test_skills_load_from_disk():
    with tempfile.TemporaryDirectory() as d:
        sd = os.path.join(d, "myskill")
        os.makedirs(sd)
        open(os.path.join(sd, "SKILL.md"), "w").write(
            "---\nname: myskill\ndescription: does x\n---\nBody text here.\n"
        )
        sk = Skills([d]).load("myskill")
        assert sk is not None and sk.name == "myskill"
        assert "Body text" in sk.system_block()
