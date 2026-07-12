"""LAN discovery beacon — lets clients find the brain without typing an IP.

Zero-dep UDP responder: clients broadcast the probe string on UDP
DISCOVERY_PORT and the brain answers with a one-line JSON payload
(service name, HTTP port, host name). The companion app uses this to
prefill the server URL; nothing else depends on it and it never touches
the HTTP hot path.

Security posture: discovery only ANNOUNCES the existing HTTP endpoint to
the local broadcast domain — it exposes nothing the LAN could not already
find with a port scan, and it answers only exact probe matches.
"""

from __future__ import annotations

import json
import socket
import threading

DISCOVERY_PORT = 19871
PROBE = b"CYCLOPS_DISCOVER_V1"


def make_reply(http_port: int) -> bytes:
    return json.dumps(
        {
            "service": "cyclops-brain",
            "port": int(http_port),
            "host": socket.gethostname(),
        }
    ).encode("utf-8")


def parse_reply(data: bytes) -> dict | None:
    """Client-side helper: validate a beacon reply. None on garbage."""
    try:
        d = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if d.get("service") != "cyclops-brain" or not isinstance(d.get("port"), int):
        return None
    return d


class DiscoveryBeacon:
    """Background UDP responder. start() is idempotent; stop() unblocks it."""

    def __init__(self, http_port: int, listen_port: int = DISCOVERY_PORT):
        self.http_port = int(http_port)
        self.listen_port = int(listen_port)
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def running(self) -> bool:
        return self._running

    def start(self) -> bool:
        """Bind + serve on a daemon thread. False (not raise) if the port is
        taken — discovery is a convenience, never a startup blocker."""
        if self._running:
            return True
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.listen_port))
        except OSError:
            return False
        self._sock = sock
        self._running = True
        self._thread = threading.Thread(
            target=self._serve, name="cyclops-discovery", daemon=True
        )
        self._thread.start()
        return True

    def _serve(self) -> None:
        reply = make_reply(self.http_port)
        while self._running and self._sock is not None:
            try:
                data, addr = self._sock.recvfrom(64)
            except OSError:
                break  # socket closed by stop()
            if data.strip() == PROBE:
                try:
                    self._sock.sendto(reply, addr)
                except OSError:
                    pass  # transient send failure: next probe retries

    def stop(self) -> None:
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None


def discover(timeout: float = 2.0, port: int = DISCOVERY_PORT) -> dict | None:
    """Client-side one-shot: broadcast a probe, return the first valid reply
    as {"service","port","host","ip"} or None. Used by tests and the CLI."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(PROBE, ("255.255.255.255", port))
        sock.sendto(PROBE, ("127.0.0.1", port))  # same-host fallback
        while True:
            data, addr = sock.recvfrom(256)
            d = parse_reply(data)
            if d is not None:
                d["ip"] = addr[0]
                return d
    except socket.timeout:
        return None
    finally:
        sock.close()


__all__ = [
    "DiscoveryBeacon",
    "discover",
    "make_reply",
    "parse_reply",
    "DISCOVERY_PORT",
    "PROBE",
]
