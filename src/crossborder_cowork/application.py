from __future__ import annotations

from pathlib import Path

from .config import Settings
from .platform.approvals import ApprovalService
from .platform.artifacts import ArtifactService
from .platform.database import Database
from .platform.events import EventStore
from .platform.product_events import ProductEventStore
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
from .platform.materials import ProjectMaterialService


class CrossborderApplication:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.settings = Settings(self.base_dir)
        self.database = Database(self.settings.db_path, self.base_dir / "migrations")
        self.product_events = ProductEventStore(self.database)
        self.events = EventStore(self.database, self.product_events)
        self.artifacts = ArtifactService(self.database, self.settings.artifact_dir, self.events)
        self.approvals = ApprovalService(self.database, self.events)
        self.tasks = TaskService(self.database, self.events)
        self.materials = ProjectMaterialService(
            self.database, self.settings.project_material_dir, self.settings.example_dir,
        )
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
            "parse_product_sources": "解析商品目录文件并创建可追溯的商品候选",
            "check_product_compliance": "执行确定性的美国法规与平台政策检查",
            "create_listing_package": "创建确定性的 Shopify/eBay 导入包",
        }.items():
            self.tools.register(tool_name, description)


def build_application(base_dir: Path) -> CrossborderApplication:
    return CrossborderApplication(Path(base_dir))
