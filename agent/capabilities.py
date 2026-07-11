"""Capability registry — the single source of truth for what Cyclops can do.

Used by the app/TUI to render a customization panel (enable/disable tools,
set defaults). Each capability maps to a tool name + human description + the
domain it touches. This is what makes 'as many customization functions as
possible' concrete and discoverable.
"""

from __future__ import annotations

CAPABILITIES = [
    # name, domain, description, requires
    ("terminal", "system", "Run shell commands / control terminal sessions.", []),
    ("fs", "system", "Safely read/write files under allowed roots.", []),
    (
        "vision",
        "multimodal",
        "Describe or analyze images (photos, screenshots).",
        ["model"],
    ),
    ("web", "knowledge", "Search the web or fetch & read a URL.", []),
    ("calendar", "productivity", "Add/list/delete reminders and events.", []),
    ("clipboard", "productivity", "Read or write the system clipboard.", []),
    ("health", "health", "Read/log health data from the digiGio brain.", ["digigio"]),
    ("hud", "wearable", "Show short text on the glasses HUD (Omi/G2).", ["device"]),
    (
        "notify",
        "wearable",
        "Trigger a haptic buzz / notification on the device.",
        ["device"],
    ),
    (
        "capture",
        "wearable",
        "Ask the wearable to take a photo or record voice.",
        ["device"],
    ),
    (
        "camera",
        "multimodal",
        "Capture a frame from the OpenGlass/XIAO camera and analyze it.",
        ["device", "model"],
    ),
    (
        "consent",
        "privacy",
        "Consent Mode: gate capture/recording behind explicit opt-in.",
        [],
    ),
    (
        "omi",
        "multimodal",
        "Capture audio from the Omi pendant and transcribe it.",
        ["device", "model"],
    ),
    (
        "context",
        "context",
        "Show the fused live context (notes + health + calendar).",
        [],
    ),
    (
        "plugin",
        "system",
        "List/sync the local-first plugin marketplace (offline-safe).",
        [],
    ),
    ("screen", "system", "Capture and optionally describe the desktop screen.", []),
    (
        "whatsapp_export",
        "social",
        "Export & summarize WhatsApp chats to feed the AI.",
        [],
    ),
    (
        "media_ingest",
        "context",
        "Index photos, voice recordings and places visited.",
        [],
    ),
    (
        "device",
        "wearable",
        "Connect to the XIAO wearable over wifi/bt/cable.",
        ["device"],
    ),
    (
        "brain",
        "memory",
        "Read/write the Cyclops note brain (tasks/ideas/decisions).",
        [],
    ),
    ("memory", "memory", "Access persona, health and long-term memory.", []),
]


def describe() -> str:
    lines = ["Cyclops capabilities:"]
    for name, domain, desc, _ in CAPABILITIES:
        lines.append(f"  - {name} [{domain}]: {desc}")
    return "\n".join(lines)


def names() -> list[str]:
    return [c[0] for c in CAPABILITIES]
