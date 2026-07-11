"""COLMI R02 smart ring — BLE protocol + offline-safe client.

Hardware (reverse-engineered, community-verified: tahnok/colmi_r02_client,
Puxtril/colmi-docs):
  - MCU: BlueX BlueMicro RF03-class nRF52, BLE 4.x (Nordic UART-style service)
  - Sensors: accelerometer (steps/sleep/gestures), PPG heart-rate + SpO2
  - Battery: ~17 mAh, magnetic pogo charger, ~5 days
  - No bond/pairing/auth: link is open (range is tiny)

Transport is the Nordic UART Service (NUS) clone:
  - SERVICE  6E40FFF0-B5A3-F393-E0A9-E50E24DCCA9E
  - RX (write)  6E400002-B5A3-F393-E0A9-E50E24DCCA9E
  - TX (notify) 6E400003-B5A3-F393-E0A9-E50E24DCCA9E

All packets are exactly 16 bytes:
  byte[0]   = command tag (>=127 means the ring returned an error)
  byte[1..14] = subdata / payload
  byte[15]  = checksum = sum(byte[0..14]) & 255

This module is import-safe with NO bluetooth dependency: the parser and
packet builder work fully offline. The BLE link uses `bleak` only when a
RingClient is actually constructed, so the brain/companion can read the ring
from a phone or laptop, and the firmware mirrors the same protocol over NimBLE.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Optional

# --- GATT identifiers -------------------------------------------------------
UART_SERVICE_UUID = "6E40FFF0-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
DEVICE_INFO_UUID = "0000180A-0000-1000-8000-00805F9B34FB"

# --- command tags -----------------------------------------------------------
CMD_BATTERY = 3
CMD_READ_HEART_RATE = 21          # 0x15 daily HR log (multi-packet)
CMD_REAL_TIME_HEART_RATE = 30     # legacy continue-packet alias
CMD_START_REAL_TIME = 105
CMD_STOP_REAL_TIME = 106

# real-time reading kinds (packet byte[1] on CMD_START_REAL_TIME responses)
RT_HEART_RATE = 1
RT_BLOOD_PRESSURE = 2
RT_SPO2 = 3
RT_FATIGUE = 4
RT_HEALTH_CHECK = 5
RT_ECG = 7
RT_HRV = 10

PACKET_LEN = 16
ERROR_BIT = 0x80  # byte[0] >= 127 => ring error response


def checksum(packet) -> int:
    """sum(byte[0..14]) & 255 — byte[15] is 0 while computing."""
    return sum(packet[0:15]) & 255


def make_packet(command: int, subdata: bytes = b"") -> bytes:
    """Build a valid 16-byte packet. subdata may be at most 14 bytes."""
    assert 0 <= command <= 255
    assert len(subdata) <= 14
    pkt = bytearray(PACKET_LEN)
    pkt[0] = command
    for i, b in enumerate(subdata):
        pkt[i + 1] = b
    pkt[15] = checksum(pkt)
    return bytes(pkt)


def is_error(packet: bytes) -> bool:
    return packet[0] >= ERROR_BIT


@dataclass
class RingSample:
    """Last decoded live reading from the ring."""
    hr: int = 0
    spo2: int = 0
    battery: int = 0
    charging: bool = False
    updated: float = 0.0


@dataclass
class BatteryInfo:
    level: int = 0
    charging: bool = False


def parse_battery(packet: bytes) -> BatteryInfo:
    """CMD_BATTERY response: byte[1]=level %, byte[2]=charging flag."""
    assert packet[0] == CMD_BATTERY
    return BatteryInfo(level=packet[1], charging=bool(packet[2]))


def parse_real_time(packet: bytes):
    """CMD_START_REAL_TIME response: byte[1]=kind, byte[2]=err, byte[3]=value.
    Returns (kind, value) or raises on error-code / error-bit."""
    assert packet[0] == CMD_START_REAL_TIME
    kind = packet[1]
    err = packet[2]
    if err != 0:
        raise ValueError(f"ring real-time error code {err} (kind={kind})")
    if is_error(packet):
        raise ValueError(f"ring returned error bit for real-time (kind={kind})")
    return kind, packet[3]


def start_real_time_packet(kind: int, action: int = 1) -> bytes:
    """action 1=START, 2=PAUSE, 3=CONTINUE, 4=STOP (STOP uses CMD_STOP_REAL_TIME)."""
    return make_packet(CMD_START_REAL_TIME, bytes([kind, action]))


def stop_real_time_packet(kind: int) -> bytes:
    return make_packet(CMD_STOP_REAL_TIME, bytes([kind, 0, 0]))


def battery_packet() -> bytes:
    return make_packet(CMD_BATTERY)


class RingClient:
    """Read HR/SpO2/battery from a COLMI R02 over BLE.

    Offline-safe: constructing the object does NOT import bleak. The link is
    only opened by `connect()`. If bleak is missing or no adapter is present,
    callers should catch the import/runtime error and fall back to a stub.
    """

    def __init__(self, address: str):
        self.address = address
        self._client = None
        self.last = RingSample()

    async def connect(self):
        from bleak import BleakClient  # imported only when actually connecting
        self._client = BleakClient(self.address)
        await self._client.connect()
        await self._client.start_notify(UART_TX_CHAR_UUID, self._on_tx)

    async def disconnect(self):
        if self._client:
            await self._client.disconnect()
            self._client = None

    def _on_tx(self, _char, data: bytearray):
        pkt = bytes(data)
        if len(pkt) != PACKET_LEN:
            return
        try:
            if pkt[0] == CMD_BATTERY:
                b = parse_battery(pkt)
                self.last.battery = b.level
                self.last.charging = b.charging
            elif pkt[0] == CMD_START_REAL_TIME:
                kind, val = parse_real_time(pkt)
                if kind == RT_HEART_RATE:
                    self.last.hr = val
                elif kind == RT_SPO2:
                    self.last.spo2 = val
        except ValueError:
            pass  # error response — ignore for live display

    async def read_battery(self) -> BatteryInfo:
        await self._client.write_gatt_char(
            UART_RX_CHAR_UUID, battery_packet(), response=False)
        # response arrives via _on_tx; brief yield so the notification lands
        import asyncio
        await asyncio.sleep(0.4)
        return BatteryInfo(level=self.last.battery, charging=self.last.charging)

    async def stream_real_time(self, kind: int = RT_HEART_RATE, seconds: int = 12):
        await self._client.write_gatt_char(
            UART_RX_CHAR_UUID, start_real_time_packet(kind), response=False)
        import asyncio
        await asyncio.sleep(seconds)
        await self._client.write_gatt_char(
            UART_RX_CHAR_UUID, stop_real_time_packet(kind), response=False)
        return self.last
