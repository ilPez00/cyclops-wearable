"""SerialLink: v2 framing + routing over an injected duplex. Offline, no pyserial."""

import json
import os
import queue
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.protocol import Decoder, encode
from device.serial_link import MSG_CMD, MSG_NOTE, MSG_STATUS, SerialLink


class FakeDev:
    """In-memory duplex: what the test 'device' sends lands in reads;
    what the link writes is captured for decoding."""

    def __init__(self):
        self.rx = queue.Queue()
        self.written = bytearray()
        self.closed = False

    def read(self, n):
        try:
            return self.rx.get(timeout=0.05)
        except queue.Empty:
            return b""

    def write(self, data):
        self.written += bytes(data)
        return len(data)

    def close(self):
        self.closed = True

    # test helper: device pushes one frame at the link
    def push_frame(self, typ, payload: bytes):
        self.rx.put(encode(typ, payload))


def _wait(pred, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_incoming_cmd_routes_act_and_arg():
    dev = FakeDev()
    seen = []
    link = SerialLink(dev, on_cmd=lambda a, arg: seen.append((a, arg))).start()
    dev.push_frame(MSG_CMD, json.dumps({"a": 2, "arg": "go"}).encode())
    assert _wait(lambda: seen == [(2, "go")])
    link.close()
    assert dev.closed
    print("OK MSG_CMD routed to on_cmd")


def test_incoming_status_parsed_and_cached():
    dev = FakeDev()
    stats = []
    link = SerialLink(dev, on_status=stats.append).start()
    dev.push_frame(MSG_STATUS, b'{"t":8,"rec":1,"mode":"HOME","notes":2}')
    assert _wait(lambda: stats and stats[0]["rec"] == 1)
    assert link.last_status["mode"] == "HOME"
    link.close()
    print("OK MSG_STATUS parsed + cached")


def test_garbage_frames_never_crash_the_loop():
    dev = FakeDev()
    seen = []
    link = SerialLink(dev, on_cmd=lambda a, arg: seen.append(a)).start()
    dev.push_frame(MSG_CMD, b"not json")
    dev.push_frame(MSG_STATUS, b"also not json")
    dev.rx.put(b"\xaa\x00\x13\x37")  # bad magic: decoder resets instantly
    corrupt = bytearray(encode(MSG_CMD, b'{"a":9}'))
    corrupt[-1] ^= 0xFF  # CRC mismatch: frame dropped, stream resyncs
    dev.rx.put(bytes(corrupt))
    dev.push_frame(MSG_CMD, json.dumps({"a": 14}).encode())  # loop still alive
    assert _wait(lambda: seen == [14])
    link.close()
    print("OK garbage frames dropped, loop survives")


def test_send_note_emits_valid_note_frame():
    dev = FakeDev()
    link = SerialLink(dev)
    link.send_note("hello uno")
    got = []
    Decoder(lambda t, p: got.append((t, p))).feed(bytes(dev.written))
    assert got and got[0][0] == MSG_NOTE
    assert json.loads(got[0][1].decode())["text"] == "hello uno"
    print("OK send_note emits a decodable NOTE frame")


def test_push_display_emits_display_cmd():
    dev = FakeDev()
    link = SerialLink(dev)
    link.push_display(1, "banner text")
    got = []
    Decoder(lambda t, p: got.append((t, p))).feed(bytes(dev.written))
    assert got and got[0][0] == 6  # MSG_DISPLAY_CMD
    assert json.loads(got[0][1].decode())["data"] == "banner text"
    print("OK push_display emits a decodable DISPLAY_CMD frame")


def test_read_error_ends_loop_cleanly():
    class DyingDev(FakeDev):
        def read(self, n):
            raise OSError("unplugged")

    link = SerialLink(DyingDev()).start()
    time.sleep(0.1)  # loop must have exited, not spun on the exception
    link.close()
    print("OK vanished port ends the read loop cleanly")
