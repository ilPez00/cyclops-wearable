"""Shared stdlib HTTP session — minimal requests-like wrapper over urllib.

Used by transcriber, LLM extractor, and agent model router so there is a single
transport implementation to maintain. The session supports:
  - POST with raw body (data=bytes) and JSON headers
  - POST with multipart/form-data (files=dict) for audio uploads
  - Injectable everywhere so unit tests run with no network.

No third-party dependency.
"""
from __future__ import annotations

import json as _json
import urllib.request as _req
import urllib.error as _err


class Resp:
    def __init__(self, status: int, body: str):
        self.status = status
        self._body = body

    def json(self):
        return _json.loads(self._body)


class Session:
    """Minimal requests-like wrapper over stdlib urllib (no third-party dep)."""

    def post(self, url, data=None, headers=None, timeout=30, files=None):
        if files is not None:
            boundary = "----cyclopsboundary"
            parts = []
            for k, v in files.items():
                if isinstance(v, tuple):
                    fname, fdata, ctype = v
                    parts.append(f"--{boundary}\r\n".encode()
                                 + f'Content-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'.encode()
                                 + f"Content-Type: {ctype}\r\n\r\n".encode()
                                 + fdata + b"\r\n")
                else:
                    parts.append(f"--{boundary}\r\n".encode()
                                 + f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
                                 + v.encode() + b"\r\n")
            body = b"".join(parts) + f"--{boundary}--\r\n".encode()
            h = dict(headers or {})
            h["Content-Type"] = f"multipart/form-data; boundary={boundary}"
            req = _req.Request(url, data=body, headers=h, method="POST")
        else:
            req = _req.Request(url, data=data, headers=headers or {}, method="POST")
        try:
            with _req.urlopen(req, timeout=timeout) as r:
                return Resp(r.status, r.read().decode("utf-8", "ignore"))
        except _err.HTTPError as e:
            return Resp(e.code, e.read().decode("utf-8", "ignore"))


def stdlib_session() -> Session:
    """Factory: return a new stdlib-only HTTP Session instance."""
    return Session()
