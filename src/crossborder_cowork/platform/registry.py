from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RegistryItem:
    name: str
    description: str
    metadata: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


class NamedRegistry:
    """Small deterministic registry for platform-owned workers and tools."""

    def __init__(self) -> None:
        self._items: dict[str, RegistryItem] = {}

    def register(self, name: str, description: str, metadata: dict[str, Any] | None = None) -> RegistryItem:
        name = str(name).strip()
        if not name:
            raise ValueError("Registry item name is required")
        item = RegistryItem(name, str(description).strip(), dict(metadata or {}))
        self._items[name] = item
        return item

    def get(self, name: str) -> RegistryItem:
        try:
            return self._items[name]
        except KeyError as error:
            raise KeyError(f"Registry item not found: {name}") from error

    def list(self) -> list[RegistryItem]:
        return [self._items[name] for name in sorted(self._items)]


class WorkerRegistry(NamedRegistry):
    pass


class ToolRegistry(NamedRegistry):
    pass
