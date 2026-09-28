"""Jev oracle tests — offline, key-absent, and shape-mismatch paths."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.jev import JevOracle, SCORE_THRESHOLD, AUTO_ROUTE_CONFIDENCE


class _Keys:
    def __init__(self, key):
        self._key = key

    def get_key(self, name):
        return self._key


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def json(self):
        return self._payload


class _Session:
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append((url, json.loads(data.decode()), headers))
        return _Resp(self._payload, self._status)


def _oracle(payload, status=200, key="ts_test"):
    return JevOracle(keys=_Keys(key), session=_Session(payload, status))


def test_key_absent_returns_none_everywhere():
    o = JevOracle(keys=_Keys(None), session=_Session({}))
    assert o.available is False
    assert o.noul("s", "i", "t", "f") is None
    assert o.choice("s", "i", {"a": "x"}) is None
    assert o.score("s", "i", ["low", "high"]) is None
    assert o.score_claim("stmt", ["ev"]) is None


def test_noul_reads_probability():
    o = _oracle({"answers": {"q": {"type": "noul", "noul": 0.97}}})
    assert o.noul("ticket", "review?", "money", "routine") == 0.97


def test_choice_reads_pick_and_confidence():
    o = _oracle({"answers": {"q": {"type": "choice", "choice": "billing",
                                   "confidence": 0.98,
                                   "probabilities": {"billing": 0.98}}}})
    assert o.choice("ticket", "route?", {"billing": "pay"}) == ("billing", 0.98)


def test_score_reads_position():
    o = _oracle({"answers": {"q": {"type": "score", "score": 1.6,
                                   "confidence": 0.62}}})
    assert o.score("ticket", "urgent?", ["low", "medium", "high"]) == 1.6


def test_score_claim_wraps_noul():
    o = _oracle({"answers": {"q": {"type": "noul", "noul": 0.93}}})
    assert o.score_claim("ring shows elevated RHR", ["hr:72"]) == 0.93


def test_http_error_returns_none():
    o = _oracle({}, status=401)
    assert o.noul("s", "i", "t", "f") is None


def test_malformed_body_returns_none():
    o = _oracle({"answers": {"q": {"nope": 1}}})
    assert o.noul("s", "i", "t", "f") is None
    o2 = _oracle({"no answers at all": True})
    assert o2.choice("s", "i", {"a": "x"}) is None


def test_transport_error_returns_none():
    class _Boom:
        def post(self, *a, **k):
            raise TimeoutError("down")

    o = JevOracle(keys=_Keys("ts_x"), session=_Boom())
    assert o.score("s", "i", ["a", "b"]) is None


def test_request_shape_and_auth():
    s = _Session({"answers": {"q": {"type": "noul", "noul": 0.5}}})
    o = JevOracle(keys=_Keys("ts_secret"), session=s)
    o.noul("state-1", "rev?", "yes", "no")
    url, body, headers = s.calls[0]
    assert url == "https://api.typesafe.ai/v1/systemone"
    assert body["model"] == "jev-latest"
    assert body["state"] == "state-1"
    assert body["questions"]["q"]["type"] == "noul"
    assert headers["Authorization"] == "Bearer ts_secret"


def test_thresholds_sane():
    assert 0.0 < AUTO_ROUTE_CONFIDENCE <= 1.0
    assert 0.0 < SCORE_THRESHOLD <= 1.0
    assert SCORE_THRESHOLD >= AUTO_ROUTE_CONFIDENCE


def test_aikeys_typesafe_alias():
    from brain.aikeys import AiKeys

    k = AiKeys(ai_api_txt="/nonexistent-ai-api.txt",
               env_paths=("/nonexistent-env",), oauth_store=_NullOAuth())
    assert k.get_key("typesafe") is None  # absent -> None, no crash

    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
        f.write("TYPESAFE_API_KEY=ts_abc123\n")
        path = f.name
    try:
        k2 = AiKeys(ai_api_txt="/nonexistent-ai-api.txt",
                    env_paths=(path,), oauth_store=_NullOAuth())
        assert k2.get_key("typesafe") == "ts_abc123"
        assert k2.get_key("jev") == "ts_abc123"
    finally:
        os.unlink(path)


class _NullOAuth:
    def get_valid_key(self, *a, **k):
        return None

    def available_providers(self):
        return set()
