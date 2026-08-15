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

    def contains(self, name: str) -> bool:
        return name in self._items

    def update_metadata(self, name: str, **metadata: Any) -> RegistryItem:
        current = self.get(name)
        merged = {**current.metadata, **metadata}
        item = RegistryItem(current.name, current.description, merged)
        self._items[name] = item
        return item


class WorkerRegistry(NamedRegistry):
    def authorize_tools(self, worker_name: str, tool_names: list[str] | tuple[str, ...] | set[str]) -> RegistryItem:
        authorized = sorted({str(name).strip() for name in tool_names if str(name).strip()})
        return self.update_metadata(worker_name, authorized_tools=authorized)

    def is_tool_authorized(self, worker_name: str, tool_name: str) -> bool:
        item = self.get(worker_name)
        return tool_name in set(item.metadata.get("authorized_tools") or [])


class ToolRegistry(NamedRegistry):
    def label(self, tool_name: str) -> str:
        item = self.get(tool_name)
        return str(item.metadata.get("label") or item.description or item.name)
