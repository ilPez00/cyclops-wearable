"""Tool: vision — describe an image via a local or cloud VLM.

Local: Ollama (llava/llava-phi3) OpenAI-compatible /v1/chat/completions.
Cloud: any OpenAI-compatible vision endpoint. HTTP layer injectable for tests.
"""
from __future__ import annotations

import base64
import json
from typing import Optional

from ..config import AgentConfig
from ..loop import Tool
from ..models import _urllib_session


def make_vision_tool(config: AgentConfig, session=None) -> Tool:
    sess = session or _urllib_session()

    def run(args: dict) -> str:
        image = args.get("image", "")           # url or data: base64
        prompt = args.get("prompt", "Describe this image concisely.")
        if not image:
            return "error: image required"
        if session is None:
            return f"offline: vision would describe image ({len(image)} chars) with prompt: {prompt[:60]}"
        local = config.local_mode
        base = config.effective_endpoint()
        if local:
            model = config.local_vision_model or "llava"
        else:
            prov = config.provider_for("vision")
            base = prov["endpoint"] or "https://api.openai.com/v1"
            model = config.vision_model or prov.get("model") or "gpt-4o-mini"
        # build image_url (data uri if raw base64)
        if image.startswith(("http://", "https://", "data:")):
            img_url = image
        else:
            img_url = f"data:image/jpeg;base64,{image}"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": img_url}},
            ]}],
            "max_tokens": 400,
        }
        try:
            body = json.dumps(payload).encode()
            resp = sess.post(base.rstrip("/") + "/chat/completions", data=body,
                             headers={"Content-Type": "application/json",
                                      "Authorization": f"Bearer {config.api_key or ''}"},
                             timeout=40)
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"error: vision failed ({e})"

    return Tool(
        name="vision",
        description="Describe or analyze an image (photo/screenshot).",
        parameters={
            "type": "object",
            "properties": {
                "image": {"type": "string", "description": "url or base64 image"},
                "prompt": {"type": "string", "description": "what to look for"},
            },
            "required": ["image"],
        },
        run=run,
    )
