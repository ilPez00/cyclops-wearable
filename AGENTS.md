# cyclops-wearable — agent notes

<!-- BEGIN free-agent-orchestration -->
## Free-agent orchestration (fleet convention)

Proceed with free-agent orchestration for development work whenever possible.

- Route tasks through the fleet orchestrator instead of paid APIs:
  `free-agent run "<task>" -w <repo> --json` — it picks the free worker with
  live quota headroom and fails over automatically.
- Bounded build/verify loops:
  `free-agent loop "<task>" -w <repo> --check "<cmd>" --max-iterations N`.
- Planners/orchestrators: `--planner bl` (Bailian qwen4-max) or `--planner bl-flash`
  (qwen-flash-character, verified free); other planners: codex, claude, grok, kimi, agy.
- Check pool state first: `free-agent status`. Workers include freebuff/free-pi
  (daily free, top priority), opencode, copilot, pi-<provider> variants (keys
  resolved from ~/.env), bl/bl-flash (Bailian free grants), commandcode,
  omniroute (127.0.0.1:20128), fcm (:19280), freeglm (:20530) when their
  daemons are up.
- Free keys live in ~/.env (never commit them). Add new free routes data-driven
  (agents.json / `free-agent cli-agents add`), not by hardcoding in Python.
- Keep credentials out of task text and logs. Free tiers may retain prompts:
  never paste secrets; be deliberate with sensitive code.
- Paid/subscription routes only when the operator explicitly asks.
<!-- END free-agent-orchestration -->
