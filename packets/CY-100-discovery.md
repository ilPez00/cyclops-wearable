---
id: CY-100
track: cyclops
phase: D
status: todo
rung: 3
depends: [CY-000]
gate: "test -f packets/CY-1xx-proposals.md && test $(grep -c '^## CY-' packets/CY-1xx-proposals.md) -ge 3"
commit: "branch agent/CY-100"
---

# DISCOVERY: next quarter's cyclops packets

## Market context (checked 2026-09-02)
Omi (BasedHardware) is the open-source leader: 13.4k stars, Flutter app +
Python/FastAPI backend + Firebase + nRF/Zephyr firmware, and its differentiation
is an APP/PERSONAS ecosystem, device SDKs in 5 languages, and an MCP server.
Users there want: 24h battery, privacy/local-first, meeting summaries, and
integrations. Cyclops' honest position: local-first and zero-dependency,
 hardware the user already verified on metal. Do NOT chase Omi's stack;
chase the local-first niche Omi structurally cannot serve.

## Sources for proposals
packets/reports unknowns; STATUS.md 'next' section; docs/00-superplan.md;
G2/pebble sink feedback; OP-009 (open-source strategy) once it exists.
Candidate seeds (validate, do not assume): scheduled Briefing mode (morning
note digest on HUD), meeting-receipt output like Omi's SPEC pattern,
per-agent note scopes (consent tiers), G2 teleprompt integration, iOS sink,
physis-coherence display on the HUD (wilting-as-turgor applied to your own
notes backlog).

## Gate
```bash
test -f packets/CY-1xx-proposals.md && grep -c '^## CY-' packets/CY-1xx-proposals.md
```

## Never
- Propose cloud-first features that betray local-first. Propose hardware
  purchases without a bench-first packet.
