from __future__ import annotations

from pathlib import Path

from .config import Settings
from .platform.approvals import ApprovalService
from .platform.artifacts import ArtifactService
from .platform.database import Database
from .platform.events import EventStore
from .platform.registry import ToolRegistry, WorkerRegistry
from .platform.skills import SkillRegistry
from .platform.tasks import TaskService


class CrossborderApplication:
    def __init__(self, base_dir: Path) -> None:
        self.settings = Settings(base_dir)
        self.database = Database(self.settings.db_path)
        self.events = EventStore(self.database)
        self.artifacts = ArtifactService(self.database, self.settings.artifact_dir, self.events)
        self.approvals = ApprovalService(self.database, self.events)
        self.tasks = TaskService(self.database, self.events)
        self.skills = SkillRegistry(self.settings.skills_dir)
        self.workers = WorkerRegistry()
        self.tools = ToolRegistry()


def build_application(base_dir: Path) -> CrossborderApplication:
    return CrossborderApplication(Path(base_dir))
