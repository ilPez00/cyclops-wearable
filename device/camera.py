"""Camera sources for Cyclops — capture a JPEG frame from a wearable camera.

Primary target: **OpenGlass** (BasedHardware) and the **XIAO ESP32-S3 Sense**
camera — the SAME MCU Cyclops already uses for the wearable. OpenGlass serves
frames over HTTP; we grab a single JPEG. A phone camera is a secondary source.

Offline-safe: `FakeCamera` returns canned bytes so the capture→vision pipeline
is fully testable without hardware (premortem D1). The HTTP layer is injectable.
"""

from __future__ import annotations

from typing import Optional


class CameraSource:
    """Returns raw JPEG bytes, or None if no frame is available."""

    def capture(self) -> Optional[bytes]:
        raise NotImplementedError


class FakeCamera(CameraSource):
    def __init__(self, data: bytes = b"\xff\xd8FAKEJPEG\xff\xd9"):
        self.data = data
        self.calls = 0

    def capture(self) -> Optional[bytes]:
        self.calls += 1
        return self.data


class OpenGlassCamera(CameraSource):
    """Grab one JPEG from an OpenGlass / XIAO-Sense HTTP camera endpoint.

    Defaults to OpenGlass's single-shot endpoint; pass `mjpeg=True` to pull a
    frame out of an MJPEG stream instead.
    """

    def __init__(
        self,
        host: str,
        port: int = 8080,
        session=None,
        path: str = "/capture",
        mjpeg: bool = False,
    ):
        self.url = f"http://{host}:{port}{path}"
        self.session = session
        self.mjpeg = mjpeg

    def capture(self) -> Optional[bytes]:
        if self.session is None:
            return None  # offline: no transport
        try:
            resp = self.session.get(self.url, timeout=10)
            body = resp.content if hasattr(resp, "content") else resp.read()
            if not self.mjpeg:
                return body or None
            # MJPEG: find first JPEG boundary (ffd8 .. ffd9)
            start = body.find(b"\xff\xd8")
            end = body.find(b"\xff\xd9", start)
            if start >= 0 and end > start:
                return body[start : end + 2]
            return body or None
        except Exception:
            return None


class PhoneCamera(CameraSource):
    """Fallback: ask the companion app to capture from the phone camera.

    The companion exposes POST /api/camera/capture -> {"jpeg": "<base64>"}.
    """

    def __init__(self, host: str, port: int = 8080, session=None):
        self.url = f"http://{host}:{port}/api/camera/capture"
        self.session = session

    def capture(self) -> Optional[bytes]:
        if self.session is None:
            return None
        try:
            import base64
            import json

            resp = self.session.post(self.url, timeout=10)
            obj = resp.json() if hasattr(resp, "json") else json.loads(resp.read())
            b64 = obj.get("jpeg") or obj.get("image") or ""
            return base64.b64decode(b64) if b64 else None
        except Exception:
            return None
