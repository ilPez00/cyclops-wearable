"""Premortem P0 — the brain's HTTP API must not be open on the LAN.

POST /api/agent reaches an agent holding the terminal tool, so an
unauthenticated network caller is remote code execution. The gate keys off the
PEER, not the bind address: loopback stays frictionless (local dashboard,
tests, adb-reverse), anything off-host presents the shared secret.

These pin the decision function. No sockets — a Handler is built without one
and only the auth path is exercised.
"""

import importlib.util
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

REPO = os.path.dirname(os.path.dirname(__file__))
spec = importlib.util.spec_from_file_location(
    "appserver_auth", os.path.join(REPO, "app", "server.py")
)
appserver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(appserver)

SECRET = "t0ken-under-test"


def _h(peer="192.168.1.50", headers=None):
    h = appserver.H.__new__(appserver.H)
    h.client_address = (peer, 55555)
    h.headers = headers or {}
    return h


def _auth(handler, path):
    return handler._authorized(urlparse(path))


def _with_token(fn):
    """Run fn with the module's TOKEN set and insecure mode off."""
    old_tok, old_insecure = appserver.TOKEN, appserver.ALLOW_INSECURE_LAN
    appserver.TOKEN, appserver.ALLOW_INSECURE_LAN = SECRET, False
    try:
        return fn()
    finally:
        appserver.TOKEN, appserver.ALLOW_INSECURE_LAN = old_tok, old_insecure


def test_lan_peer_denied_without_token():
    def go():
        ok, _ = _auth(_h(), "/api/notes")
        assert not ok
        # the RCE path specifically
        ok, _ = _auth(_h(), "/api/agent")
        assert not ok
    _with_token(go)


def test_loopback_peer_exempt():
    def go():
        for peer in ("127.0.0.1", "::1"):
            ok, cookie = _auth(_h(peer=peer), "/api/agent")
            assert ok and not cookie
    _with_token(go)


def test_health_stays_open_for_discovery():
    """The companion's status pill polls /health before pairing."""
    def go():
        ok, _ = _auth(_h(), "/health")
        assert ok
    _with_token(go)


def test_header_token_accepted():
    def go():
        ok, cookie = _auth(_h(headers={"X-Cyclops-Token": SECRET}), "/api/notes")
        assert ok and not cookie
    _with_token(go)


def test_wrong_token_denied():
    def go():
        ok, _ = _auth(_h(headers={"X-Cyclops-Token": "guess"}), "/api/notes")
        assert not ok
    _with_token(go)


def test_query_token_accepted_and_sets_cookie():
    def go():
        ok, cookie = _auth(_h(), f"/?token={SECRET}")
        assert ok and cookie
    _with_token(go)


def test_cookie_token_accepted():
    def go():
        hdrs = {"Cookie": "theme=dark; cyclops_token=" + SECRET}
        ok, cookie = _auth(_h(headers=hdrs), "/api/notes")
        assert ok and not cookie
    _with_token(go)


def test_insecure_opt_out_disables_the_gate():
    """CYCLOPS_ALLOW_INSECURE_LAN=1 is an explicit, banner-warned choice."""
    old_tok, old_insecure = appserver.TOKEN, appserver.ALLOW_INSECURE_LAN
    appserver.TOKEN, appserver.ALLOW_INSECURE_LAN = SECRET, True
    try:
        ok, _ = _auth(_h(), "/api/agent")
        assert ok
    finally:
        appserver.TOKEN, appserver.ALLOW_INSECURE_LAN = old_tok, old_insecure


def test_empty_token_does_not_authorize_empty_presentation():
    """hmac.compare_digest("", "") is True — the gate must short-circuit.

    main() always loads a token before serving, so this state is unreachable
    in practice; the guard keeps a future refactor from making "no secret
    configured" mean "everyone is authenticated".
    """
    old_tok, old_insecure = appserver.TOKEN, appserver.ALLOW_INSECURE_LAN
    appserver.TOKEN, appserver.ALLOW_INSECURE_LAN = "", False
    try:
        ok, cookie = _auth(_h(), "/api/agent")
        assert ok and not cookie  # disabled, not "authenticated"
    finally:
        appserver.TOKEN, appserver.ALLOW_INSECURE_LAN = old_tok, old_insecure


def test_token_file_is_created_0600(tmp_path=None):
    import stat
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        old_path, old_env = appserver.TOKEN_PATH, os.environ.pop("CYCLOPS_TOKEN", None)
        appserver.TOKEN_PATH = os.path.join(d, "sub", "token")
        try:
            tok = appserver.load_or_create_token()
            assert len(tok) > 20
            mode = stat.S_IMODE(os.stat(appserver.TOKEN_PATH).st_mode)
            assert mode == 0o600, oct(mode)
            assert appserver.load_or_create_token() == tok  # stable across calls
        finally:
            appserver.TOKEN_PATH = old_path
            if old_env is not None:
                os.environ["CYCLOPS_TOKEN"] = old_env
