from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .util import utc_now


_SENSITIVE_KEY = re.compile(r"key|token|secret|password|credential", re.IGNORECASE)
_ROLE_PREFIXES = {"planner", "worker", "reviewer"}


def redact_url(value: str) -> str:
    """Remove credentials, query parameters, and fragments from a public URL."""
    raw = str(value or "")
    parts = urlsplit(raw.split("#", 1)[0].split("?", 1)[0])
    if not parts.netloc and "@" in raw:
        return raw.rsplit("@", 1)[-1].split("?", 1)[0].split("#", 1)[0]
    return urlunsplit((parts.scheme, parts.netloc.rsplit("@", 1)[-1], parts.path, "", ""))


def redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else redact_sensitive_values(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_values(item) for item in value)
    return value


@dataclass(frozen=True)
class ModelSettings:
    """A role-independent LLM configuration compatible with the legacy desktop payload."""

    source: str = "environment"
    model_platform: str = ""
    model_type: str = ""
    api_key: str = ""
    api_url: str = ""
    extra_params: dict[str, Any] | None = None
    version: int = 0
    updated_at: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "model_platform": self.model_platform,
            "model_type": self.model_type,
            "platform": self.model_platform,
            "model": self.model_type,
            "api_url": redact_url(self.api_url),
            "url": redact_url(self.api_url),
            "extra_params": redact_sensitive_values(deepcopy(self.extra_params or {})),
            "has_api_key": bool(self.api_key),
            "version": self.version,
            "updated_at": self.updated_at,
        }


class Settings:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.runtime_dir = Path(os.getenv("CROSSBORDER_COWORK_RUNTIME_DIR") or (self.base_dir / "runtime")).resolve()
        self.data_dir = self.runtime_dir / "data"
        self.artifact_dir = self.runtime_dir / "artifacts"
        self.upload_dir = self.runtime_dir / "uploads"
        self.settings_path = self.runtime_dir / "settings.json"
        self.db_path = self.data_dir / "crossborder.sqlite3"
        self.taxonomy_dir = self.base_dir / "configs" / "taxonomy"
        self.skills_dir = self.base_dir / "skills"
        for path in (self.data_dir, self.artifact_dir, self.upload_dir):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _env_first(*names: str) -> str:
        for name in names:
            value = os.getenv(name, "").strip()
            if value:
                return value
        return ""

    @staticmethod
    def _prefix(role: str) -> str:
        normalized = role.strip().lower()
        if normalized not in _ROLE_PREFIXES:
            raise ValueError(f"Unknown model role: {role}")
        return f"COWORK_{normalized.upper()}"

    def _stored_model(self) -> ModelSettings | None:
        if not self.settings_path.exists():
            return None
        try:
            raw = json.loads(self.settings_path.read_text(encoding="utf-8"))
            value = raw.get("model_config") or raw.get("model") or {}
            if not isinstance(value, dict):
                return None
            platform = str(value.get("model_platform") or value.get("provider") or "").strip()
            model = str(value.get("model_type") or value.get("model") or "").strip()
            if not platform or not model:
                return None
            return ModelSettings(
                source="desktop",
                model_platform=platform,
                model_type=model,
                api_key=str(value.get("api_key") or ""),
                api_url=str(value.get("api_url") or value.get("base_url") or ""),
                extra_params=dict(value.get("extra_params") or {}),
                version=int(value.get("version") or 1),
                updated_at=str(value.get("updated_at") or ""),
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def load_model(self, role: str = "planner") -> ModelSettings:
        """Prefer desktop-persisted settings, then exact legacy role/global env chains."""
        stored = self._stored_model()
        if stored is not None:
            return stored
        prefix = self._prefix(role)
        platform = self._env_first(
            f"{prefix}_MODEL_PLATFORM", "COWORK_LLM_MODEL_PLATFORM", "LLM_MODEL_PLATFORM"
        )
        model = self._env_first(f"{prefix}_MODEL", "COWORK_LLM_MODEL", "LLM_MODEL")
        api_key = self._env_first(f"{prefix}_API_KEY", "COWORK_LLM_API_KEY", "LLM_API_KEY")
        api_url = self._env_first(f"{prefix}_BASE_URL", "COWORK_LLM_BASE_URL", "LLM_BASE_URL")
        temperature = self._env_first(
            f"{prefix}_TEMPERATURE", "COWORK_LLM_TEMPERATURE", "LLM_TEMPERATURE"
        )
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
        extra_params: dict[str, Any] = {}
        if temperature:
            try:
                extra_params["temperature"] = float(temperature)
            except ValueError:
                pass
        if not platform and (model or api_key or api_url):
            platform = "openai"
        return ModelSettings(
            source="environment",
            model_platform=platform,
            model_type=model,
            api_key=api_key,
            api_url=api_url,
            extra_params=extra_params,
        )

    def save_model(self, payload: dict[str, Any]) -> ModelSettings:
        """Persist the legacy desktop payload. Omitted keys retain the existing desktop value."""
        current = self._stored_model()
        if payload.get("source") == "codex_subscription":
            raise ValueError("cowork_model_auth_unsupported")
        source = str(payload.get("source") or "custom").strip().lower()
        platform = str(payload.get("model_platform") or "").strip()
        model = str(payload.get("model_type") or "").strip()
        if source not in {"custom", "local", "cloud"} or not platform or not model:
            raise ValueError("source, model_platform and model_type are required")
        supplied_key = payload.get("api_key")
        api_key = current.api_key if supplied_key is None and current is not None else str(supplied_key or "")
        snapshot = ModelSettings(
            source="desktop",
            model_platform=platform,
            model_type=model,
            api_key=api_key,
            api_url=str(payload.get("api_url") or ""),
            extra_params=dict(payload.get("extra_params") or {}),
            version=(current.version + 1) if current else 1,
            updated_at=utc_now(),
        )
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps({"model_config": asdict(snapshot)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return snapshot
