from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join(str(part).strip().lower() for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def safe_name(value: str, fallback: str = "artifact") -> str:
    value = re.sub(r'[^A-Za-z0-9._-]+', "-", value.strip()).strip("-._")
    return value[:96] or fallback


def json_dumps(value: Any) -> str:
    def default(item: Any) -> Any:
        if isinstance(item, Path):
            return str(item)
        if is_dataclass(item):
            return asdict(item)
        if hasattr(item, "model_dump"):
            return item.model_dump(mode="json")
        if isinstance(item, set):
            return sorted(item)
        raise TypeError(f"Value is not JSON serializable: {type(item).__name__}")

    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=default)


def json_loads(value: str | bytes | None, default: Any = None) -> Any:
    if value in (None, ""):
        return default
    return json.loads(value)
