"""Sanity checks on the static OAuth provider catalog."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.oauth_catalog import CATALOG, get


def test_catalog_ids_are_unique():
    ids = [e["id"] for e in CATALOG]
    assert len(ids) == len(set(ids))
    print("OK catalog ids are unique")


def test_every_entry_has_required_keys():
    required = {"id", "label", "flow", "needs_client_id", "needs_client_secret", "note"}
    for e in CATALOG:
        missing = required - e.keys()
        assert not missing, f"{e.get('id')} missing {missing}"
    print("OK every catalog entry has the required keys")


def test_device_and_pkce_entries_have_their_urls():
    for e in CATALOG:
        if e["flow"] == "device":
            assert e.get("device_auth_url") and e.get("token_url"), e["id"]
        elif e["flow"] == "pkce":
            assert e.get("authorize_url") and e.get("token_url"), e["id"]
    print("OK device/pkce entries carry the URLs their flow needs")


def test_openrouter_needs_no_client_id():
    e = get("openrouter")
    assert e is not None
    assert e["needs_client_id"] is False
    assert e["needs_client_secret"] is False
    print("OK openrouter is the zero-registration entry")


def test_unsupported_entries_marked_clearly():
    for pid in ("claude", "chatgpt"):
        e = get(pid)
        assert e is not None
        assert e["flow"] == "unsupported"
        assert e["note"]
    print("OK claude/chatgpt are present but marked unsupported")


def test_get_unknown_id_returns_none():
    assert get("not-a-real-provider") is None
    print("OK get() returns None for an unknown id")
