"""Tool registry factory — wires every built-in tool into a ToolRegistry.

Mirrors Hermes: tools are discovered and registered centrally. The session arg
is an injectable HTTP transport used by device/brain tools for offline tests.
"""
from __future__ import annotations

from ..config import AgentConfig
from ..loop import ToolRegistry
from .terminal import make_terminal_tool
from .whatsapp import make_whatsapp_tool
from .media import make_media_tool
from .device import make_device_tool
from .brain import make_brain_tool
from .fs import make_fs_tool


def build_registry(config: AgentConfig, session=None, confirm=None) -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(make_terminal_tool(config, confirm=confirm))
    reg.register(make_whatsapp_tool())
    reg.register(make_media_tool(config))
    reg.register(make_device_tool(config, session=session))
    reg.register(make_brain_tool(config, session=session))
    reg.register(make_fs_tool(config))
    return reg
