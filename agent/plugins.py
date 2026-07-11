"""Local-first plugin marketplace (P2-A).

A plugin is a signed-by-trust descriptor (``*.plugin.json``) describing a
wearable/agent extension: a HUD layout, a tool, a gesture handler, etc. This
module is the local registry + a sync client that pulls an index from a URL
but degrades gracefully to an offline stub (no network required).

No remote code execution: "install" only drops a *validated manifest* into the
plugin dir; the host loads behavior from manifests it already trusts.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Optional

REQUIRED_FIELDS = ("name", "version", "kind", "description")
VALID_KINDS = ("hud", "tool", "gesture", "source", "skill")


@dataclass
class PluginManifest:
    name: str
    version: str
    kind: str
    description: str
    author: str = "unknown"
    entry: str = ""
    capabilities: list = field(default_factory=list)
    source: str = ""  # where it came from (index url or "local")

    def validate(self) -> list[str]:
        """Return a list of human-readable problems (empty == valid)."""
        problems = []
        for f in REQUIRED_FIELDS:
            if not getattr(self, f):
                problems.append(f"missing '{f}'")
        if self.kind not in VALID_KINDS:
            problems.append(f"invalid kind '{self.kind}' (want {VALID_KINDS})")
        if self.capabilities and not isinstance(self.capabilities, list):
            problems.append("capabilities must be a list")
        return problems

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_dict(cls, d: dict, source: str = "") -> "PluginManifest":
        known = {
            k: d.get(k, "")
            for k in (
                "name",
                "version",
                "kind",
                "description",
                "author",
                "entry",
                "source",
            )
        }
        known["capabilities"] = d.get("capabilities", []) or []
        known["source"] = source or d.get("source", "")
        return cls(**known)


class PluginRegistry:
    """Scans a directory for ``*.plugin.json`` manifests."""

    def __init__(self, plugin_dir: str):
        self.plugin_dir = plugin_dir
        os.makedirs(plugin_dir, exist_ok=True)
        self._cache: dict[str, PluginManifest] = {}
        self.scan()

    def scan(self) -> None:
        self._cache = {}
        for fn in sorted(os.listdir(self.plugin_dir)):
            if not fn.endswith(".plugin.json"):
                continue
            path = os.path.join(self.plugin_dir, fn)
            try:
                with open(path, encoding="utf-8") as f:
                    m = PluginManifest.from_dict(json.load(f), source="local")
            except Exception:
                continue
            if m.validate():
                continue  # skip invalid manifests silently
            self._cache[m.name] = m

    def list(self) -> list[PluginManifest]:
        return list(self._cache.values())

    def get(self, name: str) -> Optional[PluginManifest]:
        return self._cache.get(name)

    def install(self, manifest: PluginManifest) -> str:
        """Drop a validated manifest into the registry dir. Returns its path."""
        if manifest.validate():
            raise ValueError(
                "refuse to install invalid plugin: " + "; ".join(manifest.validate())
            )
        path = os.path.join(self.plugin_dir, f"{manifest.name}.plugin.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(manifest.to_json())
        self.scan()
        return path


def sync_index(url: str, dest_dir: str, timeout: float = 5.0) -> list[PluginManifest]:
    """Fetch a plugin index (JSON list) from ``url`` and install each manifest.

    Offline-safe: if the network is unavailable, returns an empty list and
    writes nothing (the caller reports a graceful 'offline' status). Never
    raises on network errors.
    """
    os.makedirs(dest_dir, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return []  # offline: no sync
    installed = []
    for item in data if isinstance(data, list) else []:
        m = PluginManifest.from_dict(item, source=url)
        if m.validate():
            continue
        PluginRegistry(dest_dir).install(m)
        installed.append(m)
    return installed
