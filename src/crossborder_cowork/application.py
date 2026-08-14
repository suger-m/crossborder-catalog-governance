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
from .taxonomy.registry import TaxonomyRegistry
from .graph.service import CatalogGraphService
from .intake.service import IntakeService
from .compliance.us_apparel import UsApparelComplianceService
from .export.package import ExportPackageService
from .workers.catalog_steward import CatalogStewardAgent
from .workers.compliance_specialist import ComplianceSpecialistAgent
from .workers.listing_operations import ListingOperationsAgent
from .workers.governance_reviewer import GovernanceReviewerAgent
from .workflow import CatalogWorkflow
from .platform.model_runtime import AgentModelRuntime


class CrossborderApplication:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.settings = Settings(self.base_dir)
        self.database = Database(self.settings.db_path, self.base_dir / "migrations")
        self.events = EventStore(self.database)
        self.artifacts = ArtifactService(self.database, self.settings.artifact_dir, self.events)
        self.approvals = ApprovalService(self.database, self.events)
        self.tasks = TaskService(self.database, self.events)
        self.skills = SkillRegistry(self.settings.skills_dir)
        self.model_runtime = AgentModelRuntime(self.settings)
        self.workers = WorkerRegistry()
        self.tools = ToolRegistry()
        self.taxonomy = TaxonomyRegistry(self.settings.taxonomy_dir)
        self.graph = CatalogGraphService(self.database)
        self.intake = IntakeService(self.taxonomy)
        self.exporter = ExportPackageService(self.artifacts)
        self.catalog_steward = CatalogStewardAgent(self.intake, self.graph, self.artifacts, self.approvals, self.events, self.skills)
        self.compliance_specialist = ComplianceSpecialistAgent(UsApparelComplianceService(self.taxonomy), self.artifacts, self.events, self.skills, self.approvals)
        self.listing_operations = ListingOperationsAgent(self.database, self.artifacts, self.events, self.skills, self.model_runtime, self.graph)
        self.governance_reviewer = GovernanceReviewerAgent(self.artifacts, self.events, self.skills, self.exporter)
        self.workflow = CatalogWorkflow(self)
        for worker in (self.catalog_steward, self.compliance_specialist, self.listing_operations, self.governance_reviewer):
            self.workers.register(worker.name, worker.description)
        for tool_name, description in {
            "parse_product_sources": "Parse catalog files and create traceable product candidates",
            "check_product_compliance": "Run deterministic US and marketplace policy checks",
            "create_listing_package": "Create deterministic Shopify/eBay import package",
        }.items():
            self.tools.register(tool_name, description)


def build_application(base_dir: Path) -> CrossborderApplication:
    return CrossborderApplication(Path(base_dir))
