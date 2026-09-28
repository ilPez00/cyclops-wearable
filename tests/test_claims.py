"""Tests for brain/claims.py (34 Phase 2): the belief layer.

Deterministic rules only — no LLM, no network. Covers the three reconcile
outcomes, the evidence/confidence arithmetic, bi-temporality, the revision
log, and the structure hash's model-swap property.
"""

import os
import tempfile

from brain.claims import (
    REINFORCE,
    SUPERSEDE,
    Claim,
    ClaimStore,
    similarity,
    structure_hash,
)


def _store(tmp=None):
    d = tempfile.mkdtemp()
    return ClaimStore(os.path.join(d, "claims.jsonl"),
                      os.path.join(d, "revisions.jsonl"))


def test_similarity_bounds_and_symmetry():
    assert similarity("the sky is blue", "the sky is blue") == 1.0
    assert similarity("", "x") == 0.0
    assert similarity("a b", "c d") == 0.0
    assert abs(similarity("a b c", "a b d") - similarity("a b d", "a b c")) < 1e-9
    # exact restatement reinforces
    assert similarity("meeting moved to tuesday", "meeting moved to tuesday") >= REINFORCE
    # one-token change lands in the supersede band, not reinforce
    s = similarity("the meeting is moved to tuesday at ten",
                   "the meeting is moved to tuesday at eleven")
    assert SUPERSEDE <= s < REINFORCE, s


def test_independent_when_dissimilar():
    s = _store()
    c1, a1 = s.assert_claim("the office is on via roma")
    c2, a2 = s.assert_claim("the dentist appointment is friday")
    assert a1 == "independent" and a2 == "independent"
    assert len(s.all()) == 2 and len(s.active()) == 2


def test_reinforce_adds_evidence_and_confidence():
    s = _store()
    c, _ = s.assert_claim("the office is on via roma", evidence=["e1"])
    c2, action = s.assert_claim("the office is on via roma", evidence=["e2"])
    assert action == "reinforced"
    assert c2.id == c.id
    assert set(c2.evidence) == {"e1", "e2"}
    assert c2.confidence > 0.5
    assert len(s.active()) == 1


def test_supersede_keeps_old_as_evidence_bearing():
    s = _store()
    old, _ = s.assert_claim("the meeting is on monday at ten", evidence=["e1"])
    new, action = s.assert_claim("the meeting is on monday at eleven", evidence=["e2"])
    assert action == "superseded"
    assert new.id != old.id
    # old is superseded, not deleted: its evidence survives (Phase 2 gate)
    stored = {c.id: c for c in s.all()}
    assert stored[old.id].status == "superseded"
    assert stored[old.id].invalid_at is not None
    assert stored[old.id].evidence == ["e1"]
    assert stored[old.id].superseded_by == new.id
    assert stored[new.id].status == "active"
    assert len(s.active()) == 1


def test_contradict_without_replacement():
    s = _store()
    c, _ = s.assert_claim("the endpoint is live", evidence=["e1"])
    got = s.contradict(c.id, by_evidence="e2")
    assert got.status == "contradicted"
    assert got.invalid_at is not None
    assert got.confidence < 0.5
    assert "e2" in got.evidence
    assert s.active() == []
    assert s.contradict("nope") is None


def test_revisions_log_every_change():
    s = _store()
    s.assert_claim("a claim about the server")
    s.assert_claim("a claim about the server")  # reinforce
    s.assert_claim("a claim about the server down")  # supersede (one token added)
    revs = s.revisions()
    assert [r["reason"] for r in revs] == ["created", "reinforced", "superseded", "created"]
    # each revision names the hash before and after
    assert all(r["hash_before"] and r["hash_after"] for r in revs)


def test_structure_hash_is_identity_and_time_free():
    a = [Claim(statement="x is true", status="active", confidence=0.5,
               valid_at="2026-01-01", created_at="2026-01-01T00:00:00", id="aaa")]
    b = [Claim(statement="x is true", status="active", confidence=0.5,
               valid_at="2026-01-01", created_at="2030-09-09T09:09:09", id="zzz")]
    assert structure_hash(a) == structure_hash(b)  # ids/timestamps don't matter
    b[0].status = "contradicted"
    assert structure_hash(a) != structure_hash(b)  # structure does


def test_store_roundtrips_across_instances():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "claims.jsonl")
    rp = os.path.join(d, "revisions.jsonl")
    ClaimStore(p, rp).assert_claim("persisted claim", evidence=["e1"])
    again = ClaimStore(p, rp)
    got = again.all()
    assert len(got) == 1 and got[0].statement == "persisted claim"
    assert got[0].evidence == ["e1"]


def test_latest_supersede_and_resolution():
    s = _store()
    s.assert_claim("the meeting is moved to tuesday at ten")
    s.assert_claim("the meeting is moved to tuesday at eleven")
    got = s.latest_supersede()
    assert got is not None
    assert "ten" in got["old_statement"] and "eleven" in got["new_statement"]
    # keep the new one: state unchanged, supersede marked resolved
    s.resolve_supersede(got["old_id"], keep_new=True)
    assert s.latest_supersede() is None
    assert len(s.active()) == 1


def test_revert_reactivates_old_and_contradicts_new():
    s = _store()
    old, _ = s.assert_claim("the office is on via roma one")
    new, action = s.assert_claim("the office is on via roma two")
    assert action == "superseded"
    s.resolve_supersede(old.id, keep_new=False)
    by_id = {c.id: c for c in s.all()}
    assert by_id[old.id].status == "active"
    assert by_id[new.id].status == "contradicted"
    assert len(s.active()) == 1


def test_resolve_unknown_supersede_is_noop():
    s = _store()
    assert s.resolve_supersede("nope", keep_new=True) is None


def test_bridge_surfaces_and_resolves_w9():
    from brain.hud_bridge import HudBridge

    class Cap:
        def __init__(self):
            self.frames = []

        def write(self, b):
            self.frames.append(b)

    s = _store()
    b = HudBridge(Cap(), claims=s)
    assert b.note_claim("the meeting is moved to tuesday at ten")[0] == "independent"
    assert b.note_claim("the meeting is moved to tuesday at eleven")[0] == "superseded"
    assert b.last_banner  # the wrist line is set
    assert len(b.last_banner) <= 60
    got = b.resolve_contradiction(keep_new=False)
    assert got is not None and got.status == "active"
    assert b.last_banner.startswith("reverted:")
    # digest: top-confidence claim as one OLED DIGEST row (docs/42).
    row = b.push_digest()
    assert row and len(row) <= 22
    assert b.digest_lines(1) and b.digest_lines(1)[0][:22] in row or row
    # a cited digest row keeps the claim id on the wrist within the 22-col budget
    cited = b.push_digest("a1b2c3")
    assert "[a1b2c3]" in cited and len(cited) <= 22
    # no claims store -> W9 is a clean no-op
    plain = HudBridge(Cap())
    assert plain.note_claim("anything") == (None, None)
    assert plain.resolve_contradiction(True) is None
    assert plain.push_digest() == ""


class _Store:
    def __init__(self):
        self.notes = []

    def add(self, n):
        self.notes.append(n)
        return n

    def all(self):
        return list(self.notes)


class _Trans:
    def __init__(self, text):
        self._text = text

    def transcribe(self, *a, **k):
        return self._text


def _bridge(text=None, claims=None):
    from brain.hud_bridge import HudBridge

    class Cap:
        def __init__(self):
            self.frames = []

        def write(self, b):
            self.frames.append(b)

        def render_text(self, t):
            self.frames.append(("text", t))

    return HudBridge(Cap(), store=_Store(), transcriber=_Trans(text or ""),
                     claims=claims)


def test_voice_question_becomes_claim():
    s = _store()
    b = _bridge("is the front door locked?", claims=s)
    act, txt = b.dispatch(__import__("brain.hud_bridge", fromlist=["ACT_VOICE_NOTE"]).ACT_VOICE_NOTE)
    assert act == "voice_note"
    assert len(s.active()) == 1
    assert s.active()[0].statement == "is the front door locked?"
    assert s.active()[0].evidence  # transcript locator attached


def test_voice_statement_stays_note_only():
    s = _store()
    b = _bridge("buy milk tomorrow", claims=s)
    b.dispatch(__import__("brain.hud_bridge", fromlist=["ACT_VOICE_NOTE"]).ACT_VOICE_NOTE)
    assert s.active() == []


def test_digest_lists_top_confidence_claims():
    from brain.hud_bridge import HudBridge, ACT_NOTES

    s = _store()
    s.assert_claim("front door locked")
    s.assert_claim("ring battery low")
    b = _bridge(claims=s)
    act, lines = b.dispatch(ACT_NOTES, "digest")
    assert act == "digest"
    assert len(lines) == 2
    assert b.digest_lines() == lines
    assert b.digest_lines(1) == lines[:1]


def test_digest_empty_without_claims():
    b = _bridge()
    assert b.digest_lines() == []
