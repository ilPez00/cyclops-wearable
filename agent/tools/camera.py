"""Tool: camera — capture a frame from a wearable/phone camera and (optionally)
analyze it with the vision model. Implements P0-B (OpenGlass / XIAO-Sense cam).

Pipeline:  capture JPEG  ->  base64  ->  vision(prompt)
The camera source is injectable (FakeCamera for tests, OpenGlassCamera/
PhoneCamera for real hardware). Offline stub returns what would happen.
"""

from __future__ import annotations

import base64
from typing import Optional

from device.camera import CameraSource, FakeCamera, OpenGlassCamera, PhoneCamera

from ..config import AgentConfig
from ..loop import Tool
from ..models import _urllib_session


def _default_source(config: AgentConfig, session) -> CameraSource:
    """Pick a camera source from config; falls back to a fake when offline."""
    if session is None:
        return FakeCamera()
    src = (config.camera_source or "openglass").lower()
    host = config.device_host
    port = config.device_port
    if src == "phone":
        return PhoneCamera(host, port, session)
    return OpenGlassCamera(host, port, session)  # openglass / xiao-sense


def make_camera_tool(
    config: AgentConfig, session=None, source: Optional[CameraSource] = None
) -> Tool:
    offline = session is None
    sess = session or _urllib_session()
    src = source or _default_source(config, session)

    def _vision(image_b64: str, prompt: str) -> str:
        if offline or sess is None:
            return f"offline: vision would analyze frame ({len(image_b64)} b64 chars)"
        # inline vision call (same endpoint logic as agent/tools/vision.py)
        local = config.local_mode
        if local:
            model = config.local_vision_model or "llava"
            base = config.effective_endpoint()
        else:
            prov = config.provider_for("vision")
            base = prov["endpoint"] or "https://api.openai.com/v1"
            model = config.vision_model or prov.get("model") or "gpt-4o-mini"
        import json

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 400,
        }
        try:
            body = json.dumps(payload).encode()
            resp = sess.post(
                base.rstrip("/") + "/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.api_key or ''}",
                },
                timeout=40,
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"error: vision failed ({e})"

    def run(args: dict) -> str:
        if not config.consent_mode:
            return (
                "error: consent OFF — camera capture refused (enable via consent tool)"
            )
        analyze = bool(args.get("analyze", False))
        prompt = args.get("prompt", "Describe this image concisely.")
        frame = src.capture()
        if frame is None:
            return "error: no camera frame (camera offline or unreachable)"
        b64 = base64.b64encode(frame).decode()
        if not analyze:
            return f"captured frame: {len(frame)} bytes (base64 {len(b64)} chars)"
        return _vision(b64, prompt)

    return Tool(
        name="camera",
        description="Capture a photo from the wearable/phone camera and optionally analyze it.",
        parameters={
            "type": "object",
            "properties": {
                "analyze": {
                    "type": "boolean",
                    "description": "run vision on the frame",
                },
                "prompt": {"type": "string", "description": "what to look for"},
            },
            "required": [],
        },
        run=run,
    )
