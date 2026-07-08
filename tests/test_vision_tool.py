"""Offline tests for the vision tool (local Ollama path + cloud + stub)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.config import AgentConfig
from agent.tools.vision import make_vision_tool


class Resp:
    def __init__(self, d): self._d = d
    def json(self): return self._d


class Session:
    def __init__(self): self.last = None
    def post(self, url, data=None, headers=None, timeout=30):
        self.last = (url, json.loads(data), headers)
        return Resp({"choices": [{"message": {"content": "a red apple on a table"}}]})


def test_offline_stub():
    cfg = AgentConfig()
    tool = make_vision_tool(cfg)  # no session -> offline stub
    out = tool.run({"image": "http://x/a.jpg", "prompt": "what is this?"})
    assert out.startswith("offline:") and "describe" in out


def test_local_ollama_path():
    cfg = AgentConfig(); cfg.local_mode = True; cfg.local_base_url = "http://localhost:11434/v1"
    s = Session()
    tool = make_vision_tool(cfg, session=s)
    out = tool.run({"image": "data:image/png;base64,AAAA", "prompt": "describe"})
    assert out == "a red apple on a table"
    url, payload, headers = s.last
    assert url == "http://localhost:11434/v1/chat/completions"
    assert payload["model"] in ("llava", "llava-phi3")  # local_vision_model default
    assert "image_url" in payload["messages"][0]["content"][1]


def test_cloud_path_uses_provider():
    cfg = AgentConfig(); cfg.local_mode = False
    cfg.api_key = "sk-test"; cfg.base_url = "https://api.openai.com/v1"
    s = Session()
    tool = make_vision_tool(cfg, session=s)
    out = tool.run({"image": "http://x/a.jpg"})
    assert out == "a red apple on a table"
    url, payload, headers = s.last
    assert url == "https://api.openai.com/v1/chat/completions"
