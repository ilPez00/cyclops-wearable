---
id: CY-001
track: cyclops
phase: 1
status: todo
rung: 2
depends: [CY-000]
gate: "python3 tests/run_tests.py tests/test_mcp_server.py && python3 brain/mcp_server.py --selfcheck"
commit: "branch agent/CY-001"
---

# Brain as MCP server — notes become fleet-queryable context

## Why
Omi (the 13.4k-star category leader) ships an MCP server so any agent can
query the wearer's memory. Cyclops' brain already stores transcribed smart-
notes (task/reminder/decision/idea/summary) with a zero-dep store — exposing
them over MCP makes every agent on the fleet (hermes, opencode, aion) able to
recall 'what did I note down about X'. That is the cheapest large multiplier
in this repo.

## Steps
1. Design note first: which tools (search_notes, today, reminders_due,
   by_kind), what transport (stdio for local agents; HTTP+token ONLY bound to
   the node's Tailscale address if remote — see randomesh rules), and the
   consent story (these are the user's private thoughts; the token file is
   0600 and per-agent scoping is a later packet).
2. Implement brain/mcp_server.py over the existing store API — stdlib only
   (zero-dep is a repo feature); MCP is line-delimited JSON-RPC, no SDK needed
   for a useful subset.
3. Register in the fleet: mesh mem remembers the tool surface; aion/memd do
   NOT cache note contents (privacy) — query live.
4. Wire into hermes skill fleet-delegate docs (one line: notes queryable).

## Tests you must add
- **Unit:** store query layer (by kind, by date, due-date parse already
  exists — reuse).
- **Integration:** tests/test_mcp_server.py — initialize → tools/list →
  tools/call search_notes over a fixture store; malformed JSON-RPC → error
  object, no crash; server binds nothing by default (stdio).

## Gate
```bash
python3 tests/run_tests.py tests/test_brain.py tests/test_mcp_server.py
```

## Never
- Bind HTTP to 0.0.0.0. Embed note contents in memd. Add a pip dependency for
  this. Return raw audio transcripts in tool results (summaries/kinds only
  unless explicitly asked).
