"""Device transports: one interface, three ways to reach the wearable.

  WifiTransport     - HTTP to the brain server (notes/extract/chat/hud_cmd)
  BluetoothTransport- RFCOMM serial (real on Linux w/ rfcomm; file/serial stub
                      when BT stack absent so tests + headless still work)
  CableTransport    - ADB/serial forward to a TTY (real when `adb` present;
                      falls back to a serial-file stub)

Every transport implements `send_cmd(act, arg) -> str` and `push_hud(text) ->
str` and `request(path) -> dict`, so the agent's `device` tool and the HUD
bridge can target the wearable over *any* link. A `FakeTransport` lets tests
exercise the full routing with zero hardware/network.
"""

from __future__ import annotations

import json
import os


class Transport:
    """Uniform link to the wearable."""

    name = "base"

    def send_cmd(self, act: int, arg: str = "") -> str:
        raise NotImplementedError

    def push_hud(self, text: str) -> str:
        raise NotImplementedError

    def request(self, path: str) -> dict:
        raise NotImplementedError

    def close(self) -> None:
        pass


class FakeTransport(Transport):
    """In-memory transport for offline tests / headless."""

    name = "fake"

    def __init__(self):
        self.cmds = []  # (act, arg)
        self.huds = []  # text pushed
        self._notes = []

    def send_cmd(self, act: int, arg: str = "") -> str:
        self.cmds.append((act, arg))
        return f"fake: cmd {act} arg={arg!r}"

    def push_hud(self, text: str) -> str:
        self.huds.append(text)
        return f"fake: hud {text!r}"

    def request(self, path: str) -> dict:
        if path.startswith("/api/notes"):
            return [
                {"id": str(i), "type": "summary", "text": t}
                for i, t in enumerate(self._notes)
            ]
        return {"ok": True, "path": path}

    def add_note(self, t: str):
        self._notes.append(t)


class WifiTransport(Transport):
    """HTTP to the brain server. Real on the LAN; offline-safe when no session."""

    name = "wifi"

    def __init__(self, host: str, port: int, session=None):
        self.base = f"http://{host}:{port}"
        self.session = session

    def _get(self, path: str) -> dict:
        url = self.base + path
        if self.session is not None:
            resp = self.session.get(url, timeout=10)
            return resp.json() if hasattr(resp, "json") else {}
        import urllib.request

        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())

    def _post(self, path: str, payload: dict) -> dict:
        url = self.base + path
        body = json.dumps(payload).encode()
        if self.session is not None:
            resp = self.session.post(
                url, data=body, headers={"Content-Type": "application/json"}, timeout=10
            )
            return resp.json() if hasattr(resp, "json") else {}
        import urllib.request

        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def send_cmd(self, act: int, arg: str = "") -> str:
        self._post("/api/hud_cmd", {"a": act, "arg": arg})
        return f"wifi: cmd {act}"

    def push_hud(self, text: str) -> str:
        # the server fulfills ACT_AGENT(14) with the text and streams to glasses
        self._post("/api/hud_cmd", {"a": 14, "arg": text})
        return f"wifi: hud pushed ({len(text)} chars)"

    def request(self, path: str) -> dict:
        return self._get(path)


class BluetoothTransport(Transport):
    """RFCOMM serial to the wearable. Real when a rfcomm/serial device exists;
    otherwise operates on a captured serial file (so logic is testable)."""

    name = "bt"

    def __init__(self, mac: str = "", tty: str = "", serial_file: str = ""):
        self.mac = mac
        self.tty = tty or os.environ.get("CYCLOPS_BT_TTY", "")
        self.serial_file = serial_file  # offline capture path
        self._fh = None
        if self.serial_file:
            self._fh = open(self.serial_file, "a", encoding="utf-8")
        elif self.tty and os.path.exists(self.tty):
            self._fh = open(self.tty, "w", encoding="utf-8", errors="replace")

    def _write_frame(self, act: int, arg: str) -> str:
        line = json.dumps({"a": act, "arg": arg}) + "\n"
        if self._fh is not None:
            self._fh.write(line)
            self._fh.flush()
            return f"bt: wrote frame to {'file' if self.serial_file else 'tty'}"
        # No link available: report (does not crash headless)
        return f"bt: no link (mac={self.mac or '?'}); queued {line.strip()}"

    def send_cmd(self, act: int, arg: str = "") -> str:
        return self._write_frame(act, arg)

    def push_hud(self, text: str) -> str:
        return self._write_frame(14, text)

    def request(self, path: str) -> dict:
        # BT is a serial push link; reads would stream back frames. Best-effort.
        return {
            "ok": True,
            "transport": "bt",
            "note": "streaming link; use wifi for REST",
        }

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None


class CableTransport(Transport):
    """ADB/serial forward to a TTY (e.g. `adb forward tcp:8080 tcp:8080` or a
    real /dev/ttyUSBn). Real when `adb` exists; stub otherwise."""

    name = "cable"

    def __init__(self, tty: str = "", adb: bool = False):
        self.tty = tty or os.environ.get("CYCLOPS_CABLE_TTY", "")
        self.adb = adb
        self._fh = None
        if self.tty and os.path.exists(self.tty):
            self._fh = open(self.tty, "w", encoding="utf-8", errors="replace")

    def _write(self, act: int, arg: str) -> str:
        line = json.dumps({"a": act, "arg": arg}) + "\n"
        if self._fh is not None:
            self._fh.write(line)
            self._fh.flush()
            return "cable: wrote frame to tty"
        if self.adb:
            import subprocess

            try:
                subprocess.run(
                    ["adb", "shell", "echo", line.strip()],
                    capture_output=True,
                    timeout=10,
                )
                return "cable: adb forwarded"
            except Exception as e:
                return f"cable: adb failed {e}"
        return f"cable: no link; queued {line.strip()}"

    def send_cmd(self, act: int, arg: str = "") -> str:
        return self._write(act, arg)

    def push_hud(self, text: str) -> str:
        return self._write(14, text)

    def request(self, path: str) -> dict:
        return {"ok": True, "transport": "cable"}

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None


class SerialFrameReader:
    """Reads newline-delimited JSON frames from any text stream (serial/BT/cable
    simulator) and dispatches them through a HudBridge. This closes the loop on
    the PC side: the wearable (or `simulator.py`) emits `{"a":<act>,"arg":"..."}`
    lines; this pumps them into the brain's bridge, which fulfills them locally
    (transcribe/translate/health/...) and returns display frames.

    Offline-testable: feed it a StringIO of captured frames.
    """

    def __init__(self, bridge):
        self.bridge = bridge
        self._buf = ""

    def feed(self, chunk: str):
        self._buf += chunk
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                import json as _j

                d = _j.loads(line)
            except Exception:
                continue
            act = int(d.get("a", d.get("act", 0)) or 0)
            arg = str(d.get("arg", d.get("text", "")) or "")
            self.bridge.handle_cmd(json.dumps({"a": act, "arg": arg}).encode())

    def feed_bytes(self, data: bytes):
        self.feed(data.decode("utf-8", "replace"))


def build_transport(kind: str, config=None, session=None, **kw) -> Transport:
    """Factory: pick a transport by name. `config` is an AgentConfig for wifi."""
    if kind == "wifi":
        if config is None:
            raise ValueError("wifi transport needs a config")
        return WifiTransport(config.device_host, config.device_port, session=session)
    if kind == "bt":
        return BluetoothTransport(
            mac=kw.get("mac", ""), serial_file=kw.get("serial_file", "")
        )
    if kind == "ble":
        from .ble import BleTransport

        return BleTransport(
            bridge=kw.get("bridge"),
            backend=kw.get("backend"),
            srvc=kw.get("srvc", ""),
            note=kw.get("note", ""),
            name=kw.get("name", ""),
        )
    if kind == "cable":
        return CableTransport(tty=kw.get("tty", ""), adb=kw.get("adb", False))
    if kind == "g2":
        from .g2 import G2Transport

        return G2Transport(backend=kw.get("backend"))
    if kind == "fake":
        return FakeTransport()
    raise ValueError(f"unknown transport {kind!r}")
