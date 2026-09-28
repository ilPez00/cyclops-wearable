#!/usr/bin/env python3
"""physis-next CLI for the cyclops loop (MCP over HTTP, stdlib only).

Why this exists: physis-next has no `system` subcommand — `remember`, `history`
and `predict` live only on its MCP surface. The old justfile recipes shelled
out to physis-pro (`system history|remember|predict`), which is retired, so
`just recall/remember/start` were dead. This script is the replacement: it
speaks one `tools/call` to a running physis-next HTTP server.

Usage:
  python3 scripts/physis_mcp.py status
  python3 scripts/physis_mcp.py search "single button"
  python3 scripts/physis_mcp.py context "hud bindings" --budget 400
  python3 scripts/physis_mcp.py remember "text" --outcome success --actor opencode
  python3 scripts/physis_mcp.py history "hud bindings"
  python3 scripts/physis_mcp.py predict -- just apk-gate

Exit codes: 0 ok · 2 physis-next unreachable (honest, never a silent pass).
Start the server with:  physis serve --http 127.0.0.1:19876 --path <ROOT>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from brain import physis_next as pn  # noqa: E402


def _emit(payload) -> None:
    """Text first (the MCP rendering), then the structured blob when asked."""
    if isinstance(payload, dict) and payload.get("_text"):
        print(payload["_text"])
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="physis-next MCP client (cyclops)")
    ap.add_argument("cmd", choices=[
        "status", "search", "context", "remember", "history", "predict",
        "capabilities", "tools"])
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--budget", type=int, default=800)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--outcome", default="unverified")
    ap.add_argument("--actor", default="cyclops")
    ap.add_argument("--json", action="store_true", help="structured output")
    ap.add_argument("rest", nargs="*", default=[],
                    help="argv for `predict` (everything after --)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "status":
            out = pn.status()
            if a.json:
                print(json.dumps(out))
            else:
                state = "live" if out["reachable"] else "unreachable"
                print(f"physis-next: {state} · {out['url']}"
                      f" · workspace={out.get('workspace') or '?'}")
                if not out["reachable"]:
                    print("  " + out["detail"])
                    print("  start: physis serve --http 127.0.0.1:19876 "
                          "--path <ROOT>")
            return 0 if out["reachable"] else 2
        if a.cmd == "search":
            payload = {"results": pn.search(a.query, a.limit)}
        elif a.cmd == "context":
            payload = pn.context_stats(a.query, a.budget)
        elif a.cmd == "remember":
            payload = pn.remember(a.query, a.outcome, a.actor)
        elif a.cmd == "history":
            payload = pn.history(a.query, a.limit)
        elif a.cmd == "predict":
            payload = pn.predict(a.rest or [a.query])
        elif a.cmd == "capabilities":
            payload = pn.capabilities()
        else:  # tools
            payload = pn.rpc("physis.tools.list", {})
        if a.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            _emit(payload)
        return 0
    except pn.PhysisNextUnavailable as e:
        print(f"physis-next unreachable: {e}", file=sys.stderr)
        print("start: physis serve --http 127.0.0.1:19876 --path <ROOT>",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
