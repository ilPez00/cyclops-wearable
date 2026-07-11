"""Tools: web search + fetch (injectable transport, offline-safe)."""

from __future__ import annotations


from ..loop import Tool


def make_web_tool(config=None, session=None) -> Tool:
    sess = session

    def _search(args: dict) -> str:
        q = args.get("query", "")
        if not q:
            return "error: query required"
        if sess is None:
            return f"offline: would search '{q}'"
        try:
            url = "https://duckduckgo.com/html/?q=" + _enc(q)
            resp = sess.get(url, timeout=20)
            return _snippet(resp.text if hasattr(resp, "text") else str(resp), 1500)
        except Exception as e:
            return f"error: {e}"

    def _fetch(args: dict) -> str:
        u = args.get("url", "")
        if not u:
            return "error: url required"
        if sess is None:
            return f"offline: would fetch {u}"
        try:
            resp = sess.get(u, timeout=20)
            html = resp.text if hasattr(resp, "text") else str(resp)
            return _to_text(html)[:4000]
        except Exception as e:
            return f"error: {e}"

    return Tool(
        name="web",
        description="Search the web or fetch a URL and extract readable text.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["search", "fetch"]},
                "query": {"type": "string"},
                "url": {"type": "string"},
            },
            "required": ["action"],
        },
        run=lambda a: _search(a) if a.get("action") == "search" else _fetch(a),
    )


def _enc(s: str) -> str:
    import urllib.parse as p

    return p.quote(s)


def _snippet(html: str, n: int) -> str:
    import re

    titles = re.findall(r"result__a[^>]*>(.*?)</a>", html)
    return " | ".join(t.replace("<.*?>", "") for t in titles)[:n] or html[:n]


def _to_text(html: str) -> str:
    import re

    html = re.sub(r"<(script|style).*?</\1>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()
