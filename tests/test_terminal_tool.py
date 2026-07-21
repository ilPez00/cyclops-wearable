"""Tests for agent/tools/terminal.py — shell injection guards + safety."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.config import AgentConfig
from agent.tools.terminal import make_terminal_tool


def test_safe_command_runs():
    cfg = AgentConfig(terminal_confirm=False)
    t = make_terminal_tool(cfg)
    out = t.run({"command": "echo hello"})
    assert "hello" in out and "error" not in out


def test_empty_command():
    cfg = AgentConfig()
    t = make_terminal_tool(cfg)
    out = t.run({"command": ""})
    assert "empty" in out


def test_blocked_mkfs():
    cfg = AgentConfig(terminal_confirm=False)
    t = make_terminal_tool(cfg)
    out = t.run({"command": "mkfs.ext4 /dev/sda1"})
    assert "blocked" in out


def test_blocked_dd():
    cfg = AgentConfig(terminal_confirm=False)
    t = make_terminal_tool(cfg)
    out = t.run({"command": "dd if=/dev/zero of=/dev/sda bs=1M"})
    assert "blocked" in out


def test_blocked_dev_redirect():
    cfg = AgentConfig(terminal_confirm=False)
    t = make_terminal_tool(cfg)
    out = t.run({"command": "echo foo > /dev/sda"})
    assert "blocked" in out


def test_blocked_chmod_000():
    cfg = AgentConfig(terminal_confirm=False)
    t = make_terminal_tool(cfg)
    out = t.run({"command": "chmod -R 000 /"})
    assert "blocked" in out


def test_confirm_rejects_rm():
    cfg = AgentConfig(terminal_confirm=True)
    t = make_terminal_tool(cfg, confirm=None)
    out = t.run({"command": "rm -rf /"})
    assert "cancelled" in out


def test_confirm_callback_overrides():
    cfg = AgentConfig(terminal_confirm=True)
    allowed = []

    def confirm(cmd):
        allowed.append(cmd)
        return True

    t = make_terminal_tool(cfg, confirm=confirm)
    out = t.run({"command": "ls -la"})
    assert len(allowed) == 1
    assert "error" not in out


def test_shell_injection_via_semicolon():
    cfg = AgentConfig(terminal_confirm=False)
    t = make_terminal_tool(cfg)
    # shlex.split will include ; as a literal arg, not as shell control char
    out = t.run({"command": "echo hello; rm -rf /"})
    # With shell=False, the semicolon is a literal argument, not an injection
    assert "error" not in out


def test_timeout():
    cfg = AgentConfig(terminal_confirm=False)
    t = make_terminal_tool(cfg)
    out = t.run({"command": "echo hi", "timeout": 5})
    assert "hi" in out
