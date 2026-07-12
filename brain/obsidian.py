"""Obsidian vault sink: mirror extracted notes into a vault as linked .md files.

An Obsidian vault is just a folder of Markdown, so this needs zero deps and
zero Obsidian plugins. Each note becomes one file with YAML frontmatter
(Obsidian's Properties) under ``<vault>/<folder>/``, and gets a bullet in a
daily note (``<folder>/Daily/YYYY-MM-DD.md``) via a ``[[wikilink]]`` so the
graph view and daily-notes workflow both pick Cyclops notes up natively.

Offline-safe: no vault configured -> no sink -> NoteStore behaves as before.
Activate with ``CYCLOPS_OBSIDIAN_VAULT=/path/to/vault`` (see app/server.py)
or by passing ``vault=ObsidianVault(...)`` to NoteStore.

The agent's card memory can live in the same vault for free — point the
``memory_root`` config key at a vault subfolder (e.g. ``~/Vault/Cyclops/Memory``)
and MEMORY.md / USER.md become ordinary vault pages.
"""

from __future__ import annotations

import os
import re

_SLUG_MAX = 40


def _slug(text: str) -> str:
    """Filesystem/wikilink-safe slug from the note text."""
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"[\s_]+", "-", s)
    return s[:_SLUG_MAX].rstrip("-") or "note"


def _yaml_escape(v: str) -> str:
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


class ObsidianVault:
    """Writes Note objects into an Obsidian vault folder."""

    def __init__(self, vault_path: str, folder: str = "Cyclops"):
        self.root = os.path.expanduser(vault_path)
        self.folder = folder
        self.notes_dir = os.path.join(self.root, folder)
        self.daily_dir = os.path.join(self.notes_dir, "Daily")
        os.makedirs(self.daily_dir, exist_ok=True)

    # -- paths ---------------------------------------------------------------

    def _note_basename(self, note) -> str:
        day = (note.created or "")[:10] or "undated"
        return f"{day} {_slug(note.text)} {note.id}"

    def note_path(self, note) -> str:
        return os.path.join(self.notes_dir, self._note_basename(note) + ".md")

    def daily_path(self, day: str) -> str:
        return os.path.join(self.daily_dir, f"{day}.md")

    # -- writes --------------------------------------------------------------

    def write_note(self, note) -> str:
        """One .md per note: frontmatter + text + daily wikilink. Idempotent
        per note id (same note object rewrites the same file)."""
        day = (note.created or "")[:10]
        lines = [
            "---",
            f"id: {_yaml_escape(note.id)}",
            f"type: {note.type}",
            f"created: {_yaml_escape(note.created)}",
        ]
        if note.due:
            lines.append(f"due: {_yaml_escape(note.due)}")
        lines += [
            f"source: {note.source}",
            "tags:",
            "  - cyclops",
            f"  - cyclops/{note.type}",
            "---",
            "",
            note.text,
            "",
        ]
        if day:
            lines.append(f"Daily: [[{day}]]")
            lines.append("")
        path = self.note_path(note)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        if day:
            self._append_daily(day, note)
        return path

    def _append_daily(self, day: str, note) -> None:
        """Bullet in the daily note linking back; skip if already linked."""
        dpath = self.daily_path(day)
        base = self._note_basename(note)
        link = f"[[{self.folder}/{base}|{note.text}]]"
        existing = ""
        if os.path.exists(dpath):
            with open(dpath, "r", encoding="utf-8") as f:
                existing = f.read()
        if base in existing:
            return
        hhmm = note.created[11:16] if len(note.created or "") >= 16 else ""
        bullet = f"- {hhmm} #{note.type} {link}".replace("-  ", "- ", 1)
        with open(dpath, "a", encoding="utf-8") as f:
            if not existing:
                f.write(f"# {day}\n\n")
            f.write(bullet + "\n")


def vault_from_env(env: dict | None = None) -> "ObsidianVault | None":
    """CYCLOPS_OBSIDIAN_VAULT=/path -> sink; unset/empty -> None (disabled)."""
    env = env if env is not None else dict(os.environ)
    path = (env.get("CYCLOPS_OBSIDIAN_VAULT") or "").strip()
    if not path:
        return None
    folder = (env.get("CYCLOPS_OBSIDIAN_FOLDER") or "Cyclops").strip() or "Cyclops"
    return ObsidianVault(path, folder=folder)


__all__ = ["ObsidianVault", "vault_from_env"]
