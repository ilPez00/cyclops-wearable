# Talon Voice — Research Compendium

Sources for Cyclops wearable AI note-taker's voice / HUD / agent design.

## 1. chaosparrot/talon_hud (Unofficial Talon Head Up Display)

- **URL**: <https://github.com/chaosparrot/talon_hud>
- **Key ideas**:
  - Gaming-inspired HUD overlay for voice-control state
  - **Speech history** — rolling event log, auto-clear, freeze for pair sessions
  - **Status bar** — mode indicator (sleep/awake/command/dictation), mic mute, language
  - **Walkthrough system** — step-by-step interactive guides
  - **Content toolkit** — browsable docs + debugging panels
  - **Focus tracking** — orange box overlay on active window
  - **Inactivity hiding** — auto-hide on fullscreen video
  - **Keyboard nav** — Tab/Space/arrows/Enter
  - **Environments** — per-context layout (browser vs IDE vs terminal)
  - **WYSIWYS** — "What You See Is What You Say": visible text = voice command
  - **Three persona design** — User (prefs), Scripter (content), Themer (look)
- **Widgets**: status bar, event log, choice panel, context menu, screen overlay, eye tracker content
- **Config**: themes.csv (HEX colors), preferences, images

## 2. C-Loftus/talon-ai-tools (MIT)

- **URL**: <https://github.com/C-Loftus/talon-ai-tools>
- **License**: MIT
- **Key ideas**:
  - Query LLMs / AI tools via voice commands
  - Multi-provider (OpenAI, Anthropic, local)
  - `models.json` — per-model API options, system prompt, temperature
  - **Threads** — `start thread:` for conversation follow-ups
  - **Dictation fix** — voice command to rephrase/rewrite using LLM
  - Strip unwanted markdown from responses
  - Action context — pass selection / clipboard into prompt
- **Voice commands**: "GPT ask", "GPT format", "GPT rewrite", "GPT continue"

## 3. hortocam/jarvis_ai (MIT, already ported to aion)

- **URL**: <https://github.com/hortocam/jarvis_ai>
- **Key ideas applicable to Cyclops**: numbered UI sections, activity feed, status dots, cinematic boot sequence, KV-rows with accent colors

## 3b. chrisguevara805-prog/J.AR.V.I.S. (+ upstream DawoodTouseef/J.AR.V.I.S.)

- **URL**: <https://github.com/chrisguevara805-prog/J.AR.V.I.S.> (fork of <https://github.com/DawoodTouseef/J.AR.V.I.S.>)
- **License**: Apache 2.0 (note: not MIT)
- **Stack**: PyQt5 desktop + OpenCV
- **Key ideas for Cyclops (wearable HUD)**:
  - **Proactive suggestions from camera/screenshot analysis** — directly transferable: Cyclops IS the wearable cam, so its HUD can proactively suggest based on what the user is looking at
  - Voice activation + system monitor + proactive triad (what aion built in Cycle 3)
  - Witty JARVIS persona charm (maps to aion's voice/persona.py)
- **Relevance**: strongest design reference for Cyclops' "AI note-taker that anticipates" goal

## 4. Community ecosystem

- **Rango** — Browser voice navigation
- **Cursorless** — Parse-tree voice coding
- **gaze-OCR** — Eye tracking + OCR
- **Parrot** — Noise/click control

## Design Principles for Cyclops

1. **Always-visible state** — mode, connection, recording shown at a glance on HUD
2. **Speech as first-class data** — log commands, make debuggable
3. **Low attention UI** — glanceable, minimal, auto-clears
4. **Voice + button + touch** — never force one input modality
5. **Context-aware** — what you're doing changes what the HUD shows
6. **Ephemeral by default** — command log auto-clears, screen returns to calm
7. **Walk-through > reference** — interactive setup guides
