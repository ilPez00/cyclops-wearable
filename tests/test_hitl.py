import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.hitl import GateBook


def test_safe_action_needs_no_gate():
    book = GateBook()
    assert book.pending() == []
    assert not book.has_pending()


def test_request_then_approve():
    book = GateBook()
    gate = book.request("ssh", "whoami")
    assert book.has_pending()
    assert book.pending() == [gate]
    resolved = book.resolve_latest(True)
    assert resolved is gate
    assert gate.resolved and gate.approved
    assert not book.has_pending()


def test_reject():
    book = GateBook()
    gate = book.request("ssh", "rm -rf /")
    book.resolve_latest(False)
    assert gate.resolved and not gate.approved


def test_resolve_latest_targets_newest():
    book = GateBook()
    first = book.request("ssh", "one")
    second = book.request("ssh", "two")
    resolved = book.resolve_latest(True)
    assert resolved is second
    assert not first.resolved
    assert book.pending() == [first]


def test_expired_gate_reads_as_rejected_fail_closed():
    book = GateBook()
    gate = book.request("ssh", "whoami")
    # simulate timeout without sleeping the test
    gate.created_at = time.monotonic() - 10_000
    assert not book.has_pending()
    assert gate.resolved and not gate.approved


def test_double_resolve_is_a_noop():
    book = GateBook()
    gate = book.request("ssh", "whoami")
    assert book.resolve(gate.id, True)
    assert not book.resolve(gate.id, False)
    assert gate.approved  # first resolution wins
