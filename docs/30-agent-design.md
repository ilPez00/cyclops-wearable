# Cyclops Agent — Design (factory/loop plan)

Goal: the "perfect app to route text / audio / images to AI and get results
back", usable from (a) an Android phone and (b) a desktop TUI (Win/Mac/Linux).
It mirrors how the **Hermes agent** on this disk works: an agent loop that
calls a model, dispatches tools, loads skills, and maintains memory — so the
same brain powers the wearable companion, the phone, and the desktop.

## Architecture (one core, two shells)
```
cyclops/agent/            # the reusable brain (mirrors hermes-agent/agent)
  loop.py                 # conversation loop: model -> tool calls -> results
  models.py               # provider router: cloud (openrouter/openai/groq/...) + LOCAL (ollama/lmstudio/custom)
  memory.py               # reads/writes persona, health, memory (configurable paths)
  skills.py               # loads SKILL.md from disk (reuses ~/.hermes/skills)
  tools/                  # the "tools" the agent can call
    terminal.py           # control a terminal session (exec cmds, streaming)
    whatsapp.py           # export WhatsApp chats -> feed AI
    media.py              # photos / voice recordings / places visited ingest
    device.py             # connect to wearable: wifi (HTTP) / bluetooth (RFCOMM) / cable (ADB/serial)
    brain.py              # talk to the cyclops brain server (notes/extract/chat)
    fs.py                 # safe file read/write
  config.py               # cli-config.yaml-like schema; .env precedence
shells/
  companion_android/      # existing Android app, extended to full router
  tui/                    # textual-based desktop TUI (Win/Mac/Linux)
.github/workflows/        # build APK on GitHub, upload artifact
```

## Hermes-mirroring decisions
- Loop = model call -> parse tool_calls -> execute tools -> feed results -> repeat
  (iteration budget, compression-aware, like conversation_loop.py).
- Model routing = "auto" picks cloud key from key store; "local" uses Ollama /
  LM Studio / custom OpenAI-compatible endpoint (no key needed).
- Skills = load SKILL.md from a skills dir; same shape as ~/.hermes/skills.
- Memory = read USER.md/MEMORY.md + digigio persona/health if present; inject as
  system context. Write-back allowed (notes/reminders).
- Tool safety = file_safety-style guard; terminal tool sandboxed behind confirm.

## Features mapped to the request
- "full access to memories, persona, health" -> memory.py (configurable roots).
- "export WhatsApp chats to feed the AI" -> tools/whatsapp.py (parse export .txt).
- "pictures, voice recordings, places visited" -> tools/media.py (gallery, audio,
  location history from JSON/GPX).
- "route text/audio/images to AI, get results" -> loop accepts multimodal;
  audio transcribed (whisper/cloud), images -> vision model or described.
- "customization functions" -> config.py + per-tool toggles + persona editor.
- "connect via wifi/bt/cable" -> tools/device.py transports.
- "run AI model locally" -> models.py local providers.
- "Omi + EvenRealities G2 features" -> device.py exposes: audio capture, glanceable
  HUD text, notifications, smart notes, teleprompt scroll, + terminal control.
- "control terminal sessions" -> tools/terminal.py.

## Build & verify loop (per component)
Each component ships with an offline test (no keys, no network):
  tests/test_agent_core.py     (loop with fake model + fake tools)
  tests/test_tools_*.py        (whatsapp parse, media scan, device registry)
  tests/test_tui.py            (TUI app constructs, routes a fake turn)
  android contract re-verify
GitHub Actions builds the APK (debug + release) and uploads it as an artifact;
the workflow does NOT need local SDK.
