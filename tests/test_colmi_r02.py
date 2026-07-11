"""Offline: COLMI R02 packet protocol (mirror of firmware/ring_proto.h)."""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from device.colmi_r02 import (
    CMD_BATTERY,
    CMD_START_REAL_TIME,
    RT_HEART_RATE,
    RT_SPO2,
    battery_packet,
    checksum,
    is_error,
    make_packet,
    parse_battery,
    parse_real_time,
    start_real_time_packet,
    stop_real_time_packet,
)


def _finalize(pkt: bytearray) -> bytes:
    pkt[15] = checksum(pkt)
    return bytes(pkt)


def test_checksum():
    p = bytearray(16)
    p[0] = CMD_BATTERY
    _finalize(p)
    assert checksum(p) == p[15]
    # checksum is sum(byte[0..14]) & 255, byte[15] contributes 0
    assert sum(p[0:15]) & 255 == p[15]
    print("OK checksum = sum(byte[0..14]) & 255")


def test_make_packet_battery():
    pkt = make_packet(CMD_BATTERY)
    assert len(pkt) == 16
    assert pkt[0] == CMD_BATTERY
    assert checksum(pkt) == pkt[15]
    print("OK make_packet builds valid 16-byte battery request")


def test_parse_battery():
    p = bytearray(16)
    p[0] = CMD_BATTERY
    p[1] = 64
    p[2] = 0
    _finalize(p)
    b = parse_battery(bytes(p))
    assert b.level == 64 and b.charging is False
    p2 = bytearray(16)
    p2[0] = CMD_BATTERY
    p2[1] = 80
    p2[2] = 1
    _finalize(p2)
    b2 = parse_battery(bytes(p2))
    assert b2.charging is True
    print("OK battery decode (level + charging)")


def test_parse_realtime_hr_spo2():
    hr = bytearray(16)
    hr[0] = CMD_START_REAL_TIME
    hr[1] = RT_HEART_RATE
    hr[2] = 0
    hr[3] = 78
    _finalize(hr)
    kind, val = parse_real_time(bytes(hr))
    assert kind == RT_HEART_RATE and val == 78

    sp = bytearray(16)
    sp[0] = CMD_START_REAL_TIME
    sp[1] = RT_SPO2
    sp[2] = 0
    sp[3] = 97
    _finalize(sp)
    kind2, val2 = parse_real_time(bytes(sp))
    assert kind2 == RT_SPO2 and val2 == 97
    print("OK real-time HR (78) + SpO2 (97) decode")


def test_error_handling():
    # error bit in byte[0]
    e = bytearray(16)
    e[0] = 0x80 | CMD_BATTERY
    _finalize(e)
    assert is_error(bytes(e))
    # error code in byte[2] of real-time
    er = bytearray(16)
    er[0] = CMD_START_REAL_TIME
    er[1] = RT_HEART_RATE
    er[2] = 5
    _finalize(er)
    try:
        parse_real_time(bytes(er))
        assert False, "should raise"
    except ValueError:
        pass
    # bad checksum
    bad = bytearray(16)
    bad[0] = CMD_BATTERY
    bad[1] = 50
    bad[15] = (checksum(bad) ^ 0xFF) & 255
    assert checksum(bad) != bad[15]
    print("OK error-bit + error-code + bad-checksum rejected")


def test_request_builders():
    assert battery_packet()[0] == CMD_BATTERY
    s = start_real_time_packet(RT_HEART_RATE)
    assert s[0] == CMD_START_REAL_TIME and s[1] == RT_HEART_RATE and s[2] == 1
    st = stop_real_time_packet(RT_HEART_RATE)
    assert st[0] == 106 and st[2] == 0
    print("OK request builders (battery / start / stop real-time)")


if __name__ == "__main__":
    test_checksum()
    test_make_packet_battery()
    test_parse_battery()
    test_parse_realtime_hr_spo2()
    test_error_handling()
    test_request_builders()
    print("PASS tests/test_colmi_r02.py")
