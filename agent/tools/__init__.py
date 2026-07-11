"""Tool registry factory — wires every built-in tool into a ToolRegistry.

Mirrors Hermes: tools are discovered and registered centrally. The session arg
is an injectable HTTP transport used by device/brain/vision tools for offline
tests. `disable` lets the UI/TUI customize which tools are active.
"""

from __future__ import annotations

from ..config import AgentConfig
from ..loop import ToolRegistry
from .brain import make_brain_tool
from .calendar import make_calendar_tool
from .camera import make_camera_tool
from .clipboard import make_clipboard_tool
from .consent import make_consent_tool
from .context import make_context_tool
from .device import make_device_tool
from .fs import make_fs_tool
from .health import make_health_tool
from .history import make_history_tool
from .media import make_media_tool
from .memory_tool import make_memory_tool
from .omi import make_omi_tool
from .plugin import make_plugin_tool
from .screen import make_screen_tool
from .terminal import make_terminal_tool
from .vision import make_vision_tool
from .wearable import make_capture_tool, make_hud_tool, make_notify_tool
from .web import make_web_tool
from .whatsapp import make_whatsapp_tool


def build_registry(
    config: AgentConfig,
    session=None,
    confirm=None,
    disable: set[str] | None = None,
    agent=None,
    context_assembler=None,
) -> ToolRegistry:
    disable = disable or set()
    reg = ToolRegistry()
    factories = {
        "terminal": lambda: make_terminal_tool(config, confirm=confirm),
        "whatsapp_export": make_whatsapp_tool,
        "media_ingest": lambda: make_media_tool(config),
        "device": lambda: make_device_tool(config, session=session),
        "brain": lambda: make_brain_tool(config, session=session),
        "fs": lambda: make_fs_tool(config),
        "vision": lambda: make_vision_tool(config, session=session),
        "web": lambda: make_web_tool(config, session=session),
        "calendar": lambda: make_calendar_tool(config),
        "clipboard": lambda: make_clipboard_tool(config),
        "health": lambda: make_health_tool(config),
        "hud": lambda: make_hud_tool(config, session=session),
        "notify": lambda: make_notify_tool(config, session=session),
        "capture": lambda: make_capture_tool(config, session=session),
        "camera": lambda: make_camera_tool(config, session=session),
        "consent": lambda: make_consent_tool(config),
        "omi": lambda: make_omi_tool(config),
        "context": lambda: make_context_tool(config, assembler=context_assembler),
        "plugin": lambda: make_plugin_tool(config),
        "screen": lambda: make_screen_tool(config),
        "memory": lambda: make_memory_tool(config),
    }
    for name, factory in factories.items():
        if name in disable:
            continue
        reg.register(factory())
    # history needs the live agent instance; register only when available
    if agent is not None and "history" not in disable:
        reg.register(make_history_tool(agent))
    return reg
