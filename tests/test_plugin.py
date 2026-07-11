"""Offline: P2-A local-first plugin marketplace.

Verifies manifest validation, registry discovery, install, and offline-safe
sync — no network needed.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.plugins import PluginManifest, PluginRegistry, sync_index


def test_manifest_validation():
    good = PluginManifest(
        name="hud-clock",
        version="1.0",
        kind="hud",
        description="clock layout",
        author="g",
    )
    assert good.validate() == []
    bad = PluginManifest(name="", version="", kind="bogus", description="")
    problems = bad.validate()
    assert "missing 'name'" in problems
    assert any("invalid kind 'bogus'" in p for p in problems)
    print("OK manifest validation accepts good / rejects bad")


def test_registry_discovers_and_installs():
    d = tempfile.mkdtemp()
    reg = PluginRegistry(d)
    assert reg.list() == []
    m = PluginManifest(
        name="g2-weather",
        version="0.2",
        kind="hud",
        description="weather on G2",
        capabilities=["display"],
    )
    path = reg.install(m)
    assert os.path.exists(path)
    reg.scan()
    assert reg.get("g2-weather") is not None
    assert reg.get("g2-weather").capabilities == ["display"]
    print("OK registry discovers + installs manifest")


def test_invalid_plugin_rejected():
    d = tempfile.mkdtemp()
    reg = PluginRegistry(d)
    try:
        reg.install(PluginManifest(name="x", version="", kind="bad", description=""))
        assert False, "should have refused invalid plugin"
    except ValueError:
        pass
    print("OK invalid plugin refused at install")


def test_sync_offline_safe():
    d = tempfile.mkdtemp()
    # point at a URL that won't resolve in offline CI; must not raise, returns []
    installed = sync_index("http://127.0.0.1:9/nope.json", d, timeout=1.0)
    assert installed == []
    assert reg_list_empty(d)
    print("OK sync_index offline-safe (no network, no crash)")


def reg_list_empty(d):
    return PluginRegistry(d).list() == []


def test_plugin_tool_offline():
    from agent.config import AgentConfig
    from agent.tools.plugin import make_plugin_tool

    d = tempfile.mkdtemp()
    cfg = AgentConfig(config_dir=d, plugin_index_url="http://127.0.0.1:9/idx.json")
    tool = make_plugin_tool(cfg, plugin_dir=d, index_url=cfg.plugin_index_url)
    # no plugins yet
    out = tool.run({"action": "list"})
    assert "no plugins" in out
    # sync offline -> graceful
    out = tool.run({"action": "sync"})
    assert "offline" in out
    # install via registry, then list shows it
    reg = PluginRegistry(d)
    reg.install(
        PluginManifest(
            name="hud-timer",
            version="1.1",
            kind="hud",
            description="countdown",
            capabilities=["display"],
        )
    )
    out = tool.run({"action": "list"})
    assert "hud-timer" in out
    print("OK plugin tool list/sync offline + install visible")


if __name__ == "__main__":
    test_manifest_validation()
    test_registry_discovers_and_installs()
    test_invalid_plugin_rejected()
    test_sync_offline_safe()
    test_plugin_tool_offline()
    print("PASS tests/test_plugin.py")
