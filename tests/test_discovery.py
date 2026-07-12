"""LAN discovery beacon: probe/reply over loopback UDP. Offline, no deps."""

import os
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.discovery import DiscoveryBeacon, discover, make_reply, parse_reply

TEST_PORT = 29871  # off the default so a live brain on this box can't interfere


def test_beacon_answers_probe():
    b = DiscoveryBeacon(http_port=8080, listen_port=TEST_PORT)
    assert b.start()
    try:
        found = discover(timeout=2.0, port=TEST_PORT)
        assert found is not None, "beacon did not answer"
        assert found["service"] == "cyclops-brain" and found["port"] == 8080
        assert found["ip"]
    finally:
        b.stop()
    print("OK beacon answers a broadcast probe with service+port")


def test_beacon_ignores_garbage():
    b = DiscoveryBeacon(http_port=8080, listen_port=TEST_PORT)
    assert b.start()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.sendto(b"totally not the probe", ("127.0.0.1", TEST_PORT))
        try:
            s.recvfrom(256)
            assert False, "garbage must not be answered"
        except socket.timeout:
            pass
        finally:
            s.close()
    finally:
        b.stop()
    print("OK garbage probes are ignored")


def test_parse_reply_strict():
    assert parse_reply(make_reply(8080))["port"] == 8080
    assert parse_reply(b"not json") is None
    assert parse_reply(b'{"service":"other","port":1}') is None
    assert parse_reply(b'{"service":"cyclops-brain","port":"nope"}') is None
    print("OK reply parser rejects non-beacon payloads")


def test_port_conflict_is_soft():
    a = DiscoveryBeacon(http_port=8080, listen_port=TEST_PORT)
    assert a.start()
    try:
        b = DiscoveryBeacon(http_port=9090, listen_port=TEST_PORT)
        started = b.start()
        # SO_REUSEADDR semantics differ per platform; what matters is that a
        # conflict NEVER raises — it must degrade to False or coexist.
        assert started in (True, False)
        b.stop()
    finally:
        a.stop()
    print("OK port conflict degrades softly (no exception)")


def test_stop_is_idempotent():
    b = DiscoveryBeacon(http_port=8080, listen_port=TEST_PORT)
    assert b.start()
    b.stop()
    b.stop()  # second stop must not raise
    assert not b.running
    print("OK stop() is idempotent")


def test_discover_times_out_cleanly():
    assert discover(timeout=0.3, port=TEST_PORT + 1) is None
    print("OK discover() returns None when nothing answers")
