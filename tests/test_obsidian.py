"""Obsidian vault sink: note -> vault .md page + daily wikilink. Offline, no deps."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.extractor import Note
from brain.obsidian import ObsidianVault, vault_from_env
from brain.store import NoteStore


def _note(nid="n1", text="ship the demo tomorrow", typ="task"):
    return Note(nid, typ, text, created="2026-07-12T10:30:00", due="2026-07-13")


def test_write_note_creates_page_with_frontmatter():
    d = tempfile.mkdtemp()
    v = ObsidianVault(d, folder="Cyclops")
    path = v.write_note(_note())
    assert os.path.exists(path) and path.endswith(".md")
    body = open(path, encoding="utf-8").read()
    assert body.startswith("---")
    assert 'id: "n1"' in body and "type: task" in body
    assert 'due: "2026-07-13"' in body
    assert "  - cyclops/task" in body
    assert "ship the demo tomorrow" in body
    assert "Daily: [[2026-07-12]]" in body
    print("OK vault page has frontmatter + wikilink")


def test_daily_note_links_back_once():
    d = tempfile.mkdtemp()
    v = ObsidianVault(d)
    n = _note()
    v.write_note(n)
    v.write_note(n)  # idempotent: same id -> same file, no duplicate bullet
    daily = open(v.daily_path("2026-07-12"), encoding="utf-8").read()
    assert daily.startswith("# 2026-07-12")
    assert daily.count("ship the demo tomorrow") == 1
    assert "#task" in daily and "10:30" in daily
    print("OK daily note links back exactly once")


def test_slug_survives_hostile_text():
    d = tempfile.mkdtemp()
    v = ObsidianVault(d)
    n = _note(nid="n2", text='rm -rf / && echo "ha?" *[]|<>: yes')
    path = v.write_note(n)
    assert os.path.exists(path)
    base = os.path.basename(path)
    assert "/" not in base.replace(".md", "") and '"' not in base
    print("OK hostile text slugs to a safe filename")


def test_notestore_mirrors_into_vault():
    d = tempfile.mkdtemp()
    v = ObsidianVault(os.path.join(d, "vault"))
    store = NoteStore(os.path.join(d, "notes.jsonl"), vault=v)
    store.add(_note(nid="n3", text="decide on the antenna cap", typ="decision"))
    pages = [f for f in os.listdir(v.notes_dir) if f.endswith(".md")]
    assert len(pages) == 1 and "decide-on-the-antenna-cap" in pages[0]
    # store still fully functional
    assert store.all()[0].id == "n3"
    print("OK NoteStore mirrors adds into the vault")


def test_vault_off_by_default_and_env_toggle():
    d = tempfile.mkdtemp()
    assert vault_from_env(env={}) is None
    assert vault_from_env(env={"CYCLOPS_OBSIDIAN_VAULT": ""}) is None
    v = vault_from_env(
        env={"CYCLOPS_OBSIDIAN_VAULT": d, "CYCLOPS_OBSIDIAN_FOLDER": "Inbox"}
    )
    assert v is not None and v.notes_dir.endswith("Inbox")
    # no vault -> NoteStore.add unaffected
    store = NoteStore(os.path.join(d, "notes.jsonl"))
    store.add(_note(nid="n4"))
    assert store.all()[0].id == "n4"
    print("OK sink is opt-in via CYCLOPS_OBSIDIAN_VAULT")


if __name__ == "__main__":
    test_write_note_creates_page_with_frontmatter()
    test_daily_note_links_back_once()
    test_slug_survives_hostile_text()
    test_notestore_mirrors_into_vault()
    test_vault_off_by_default_and_env_toggle()
    print("PASS tests/test_obsidian.py")
