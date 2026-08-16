from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from camel.toolkits.skill_toolkit import SkillToolkit as CamelSkillToolkit
from camel.toolkits import FunctionTool

from .events import EventStore
from .execution_context import current_execution_context


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path

    def load(self) -> str:
        return self.path.read_text(encoding="utf-8")


class ProjectSkillToolkit(CamelSkillToolkit):
    """CAMEL SkillToolkit with Eigent-compatible project and user roots."""

    def _skill_roots(self) -> list[tuple[str, Path]]:
        return [
            ("repo", self.working_directory / "skills"),
            ("repo", self.working_directory / ".agents" / "skills"),
            ("repo", self.working_directory / ".camel" / "skills"),
            ("user", Path.home() / ".agents" / "skills"),
            ("user", Path.home() / ".camel" / "skills"),
            ("user", Path.home() / ".config" / "camel" / "skills"),
            ("system", Path("/etc/camel/skills")),
        ]


class AgentSkillToolkit(ProjectSkillToolkit):
    """Project SkillToolkit with role scoping and Product Event auditing."""

    def __init__(
        self,
        *,
        working_directory: Path,
        allowed_skills: Iterable[str] | None,
        events: EventStore,
        worker_name: str,
    ) -> None:
        self.events = events
        self.worker_name = worker_name
        super().__init__(
            working_directory=str(Path(working_directory).resolve()),
            allowed_skills=set(allowed_skills) if allowed_skills is not None else None,
        )

    async def load_skill(self, name: str | list[str]) -> str:
        """Load one or more role-visible Skills into the Agent context.

        Args:
            name: One Skill name or a list of role-visible Skill names.
        """
        content = super().load_skill(name)
        context = current_execution_context(required=False)
        if context is not None:
            names = [name] if isinstance(name, str) else list(name)
            for skill_name in names:
                self.events.publish(context.task_id, "skill.activated", self.worker_name, {
                    "worker_name": self.worker_name,
                    "process_task_id": context.process_task_id,
                    "skill_name": str(skill_name),
                    "status": "completed",
                })
        return content

    async def read_skill_resource(
        self,
        name: str,
        relative_path: str,
        offset: int = 0,
        limit: int = 16_384,
    ) -> dict[str, Any]:
        """Read one text page from a file inside a role-visible Skill package.

        Args:
            name: Role-visible Skill name.
            relative_path: File path relative to the Skill package directory.
            offset: Character offset for paginated reads.
            limit: Maximum characters to return in this page.
        """
        skill = self._get_skills().get(str(name).strip())
        if not skill:
            raise KeyError(f"Skill not available to this Agent: {name}")
        skill_dir = Path(skill["path"]).resolve().parent
        target = (skill_dir / str(relative_path).strip()).resolve()
        try:
            target.relative_to(skill_dir)
        except ValueError as exc:
            raise ValueError("Skill resource path escapes the Skill package") from exc
        if not target.is_file():
            raise FileNotFoundError(f"Skill resource not found: {relative_path}")
        if target.suffix.lower() not in {".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".csv"}:
            raise ValueError("Skill resource is not an approved text format")
        offset = max(0, int(offset))
        limit = min(max(1, int(limit)), 65_536)
        content = target.read_text(encoding="utf-8")
        page = content[offset:offset + limit]
        next_offset = offset + len(page)
        context = current_execution_context(required=False)
        if context is not None:
            self.events.publish(context.task_id, "skill.resource_read", self.worker_name, {
                "worker_name": self.worker_name,
                "process_task_id": context.process_task_id,
                "skill_name": str(name),
                "relative_path": target.relative_to(skill_dir).as_posix(),
                "status": "completed",
            })
        return {
            "skill_name": str(name),
            "relative_path": target.relative_to(skill_dir).as_posix(),
            "content": page,
            "offset": offset,
            "next_offset": next_offset,
            "total_chars": len(content),
            "eof": next_offset >= len(content),
        }

    def get_tools(self) -> list[FunctionTool]:
        return [*super().get_tools(), FunctionTool(self.read_skill_resource)]


class SkillRegistry:
    """Catalog facade and factory for scoped CAMEL SkillToolkits."""

    def __init__(self, root: Path, events: EventStore | None = None) -> None:
        self.root = Path(root).resolve()
        self.working_directory = self.root.parent
        self.events = events

    def _catalog_toolkit(self) -> ProjectSkillToolkit:
        return ProjectSkillToolkit(working_directory=str(self.working_directory))

    def discover(self) -> list[Skill]:
        items = []
        for item in self._catalog_toolkit().list_skills():
            items.append(Skill(
                name=str(item["name"]),
                description=str(item["description"]),
                path=Path(str(item["path"])).resolve(),
            ))
        return sorted(items, key=lambda item: item.name)

    def get(self, name: str) -> Skill:
        for skill in self.discover():
            if skill.name == name or skill.path.parent.name == name:
                return skill
        raise KeyError(name)

    def toolkit(self, worker_name: str, allowed_skills: Iterable[str]) -> AgentSkillToolkit:
        if self.events is None:
            raise RuntimeError("SkillRegistry events are not configured")
        return AgentSkillToolkit(
            working_directory=self.working_directory,
            allowed_skills=allowed_skills,
            events=self.events,
            worker_name=worker_name,
        )
