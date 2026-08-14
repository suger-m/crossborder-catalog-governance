from __future__ import annotations

import json
import os
from typing import Any

import httpx

from ..config import Settings


class AgentModelRuntime:
    """OpenAI-compatible model access shared by the four business roles.

    Deterministic tools remain authoritative. Model output is optional and must be
    projected into validated business types by the calling Agent.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def readiness(self, role: str = "worker") -> dict[str, Any]:
        config = self.settings.load_model(role)
        return {
            **config.public_dict(),
            "role": role,
            "configured": bool(config.model_platform and config.model_type and config.api_url),
            "execution_enabled": os.getenv("CROSSBORDER_DISABLE_LLM", "").strip().lower() not in {"1", "true", "yes"},
        }

    def complete_json(self, role: str, system: str, user: str, timeout: float = 90) -> dict[str, Any]:
        config = self.settings.load_model(role)
        if os.getenv("CROSSBORDER_DISABLE_LLM", "").strip().lower() in {"1", "true", "yes"}:
            raise RuntimeError("LLM execution is disabled")
        if not config.model_type or not config.api_url:
            raise RuntimeError("LLM is not configured")
        url = config.api_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        payload = {
            "model": config.model_type,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": float((config.extra_params or {}).get("temperature", 0.1)),
            "response_format": {"type": "json_object"},
        }
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        content = body.get("choices", [{}])[0].get("message", {}).get("content", "{}")
        if isinstance(content, list):
            content = "".join(str(item.get("text") or "") if isinstance(item, dict) else str(item) for item in content)
        return json.loads(content or "{}")

    def smoke(self, role: str = "worker") -> dict[str, Any]:
        try:
            parsed = self.complete_json(role, "Return only JSON.", 'Return {"ok": true}.', timeout=30)
            return {"ok": bool(parsed.get("ok")), "role": role, "model": self.settings.load_model(role).model_type}
        except Exception as exc:
            return {"ok": False, "role": role, "error": str(exc)[:500]}
