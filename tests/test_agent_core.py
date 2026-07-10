"""Offline tests for the agent core (no network, no keys)."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # repo root for 'agent' pkg

from agent.config import AgentConfig
from agent.models import ModelRouter, ChatResult
from agent.memory import MemoryStore
from agent.skills import Skills
from agent.loop import Agent, ToolRegistry
from agent.tools import build_registry
from agent.tools.whatsapp import parse_export


# --- fake model router: first calls a tool, then answers -----------------
class FakeRouter:
    def __init__(self):
        self.calls = 0
    def chat(self, messages, tools=None, temperature=0.4, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return ChatResult(text="", tool_calls=[{
                "function": {"name": "whatsapp_export",
                             "arguments": json.dumps({"path": "/tmp/fake_wa.txt"})}}])
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
    reg._tools["whatsapp_export"].run = lambda a: f"participants: Marco, You (read {path})"
    res = agent.run("summarize my whatsapp with Marco")
    assert res.tool_calls == 1, res.steps
    assert "WhatsApp" in res.text, res.text
    assert res.steps[0]["tool"] == "whatsapp_export"
    os.unlink(path)


def test_whatsapp_parser():
    txt = ("12/04/2026, 14:33 - Marco: are we still on for friday?\n"
           "12/04/2026, 14:34 - You: yes, 3pm\n"
           "12/04/2026, 14:35 - Marco: perfect\n")
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
    cfg = AgentConfig(hermes_home="/no/such", digigio_home="/no/such")
    cfg.memory_root = tempfile.mkdtemp()   # isolate from shared ~/.cyclops/memory
    mem = MemoryStore(cfg).read()
    assert mem == ""                       # empty -> '' (card store markdown)


def test_local_mode_endpoint():
    cfg = AgentConfig(local_mode=True, local_base_url="http://127.0.0.1:1234/v1")
    assert cfg.effective_endpoint() == "http://127.0.0.1:1234/v1"


def test_skills_load_from_disk():
    with tempfile.TemporaryDirectory() as d:
        sd = os.path.join(d, "myskill")
        os.makedirs(sd)
        open(os.path.join(sd, "SKILL.md"), "w").write(
            "---\nname: myskill\ndescription: does x\n---\nBody text here.\n")
        sk = Skills([d]).load("myskill")
        assert sk is not None and sk.name == "myskill"
        assert "Body text" in sk.system_block()
