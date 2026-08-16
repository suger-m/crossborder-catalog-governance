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
from .platform.resources import ProjectResourceService
from .platform.project_context import ProjectContextService
from .platform.tool_executor import ToolExecutor


class CrossborderApplication:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.settings = Settings(self.base_dir)
        self.database = Database(self.settings.db_path, self.base_dir / "migrations")
        self.product_events = ProductEventStore(self.database)
        self.events = EventStore(self.database, self.product_events)
        self.resources = ProjectResourceService(self.database)
        self.artifacts = ArtifactService(
            self.database, self.settings.artifact_dir, self.events, self.resources,
        )
        self.approvals = ApprovalService(self.database, self.events)
        self.tasks = TaskService(self.database, self.events)
        self.materials = ProjectMaterialService(
            self.database, self.settings.project_material_dir, self.settings.example_dir,
        )
        self.skills = SkillRegistry(self.settings.skills_dir, self.events)
        self.model_runtime = AgentModelRuntime(self.settings)
        self.workers = WorkerRegistry()
        self.tools = ToolRegistry()
        self.taxonomy = TaxonomyRegistry(self.settings.taxonomy_dir)
        self.graph = CatalogGraphService(self.database)
        self.intake = IntakeService(self.taxonomy)
        self.exporter = ExportPackageService(self.artifacts)
        self.project_context = ProjectContextService(
            self.database, self.resources, self.artifacts, self.graph, self.approvals,
        )
        self.tool_executor = ToolExecutor(
            self.database, self.events, self.workers, self.tools,
        )
        for tool_name, label in {
            "list_project_resources": "查看项目资源",
            "inspect_task_materials": "查看任务素材",
            "summarize_canonical_products": "查看规范商品摘要",
            "summarize_listing_drafts": "查看平台草稿摘要",
            "read_artifact_text": "读取文件内容",
            "list_pending_approvals": "查看待审批事项",
            "build_canonical_catalog": "建立规范商品目录",
            "evaluate_us_apparel_compliance": "执行美国服装合规检查",
            "create_listing_drafts": "生成平台草稿",
            "review_catalog_release": "执行目录治理审核",
        }.items():
            kind = "project_context" if tool_name in {
                "list_project_resources", "inspect_task_materials",
                "summarize_canonical_products", "summarize_listing_drafts",
                "read_artifact_text", "list_pending_approvals",
            } else "business"
            self.tools.register(tool_name, label, {"label": label, "kind": kind})

        self.compliance_service = UsApparelComplianceService(self.taxonomy)
        self.catalog_steward = CatalogStewardAgent()
        self.compliance_specialist = ComplianceSpecialistAgent()
        self.listing_operations = ListingOperationsAgent()
        self.governance_reviewer = GovernanceReviewerAgent()
        worker_config = {
            "catalog_steward_agent": {
                "skills": ["product-catalog", "womenswear-classification"],
                "tools": ["list_project_resources", "inspect_task_materials", "build_canonical_catalog"],
            },
            "compliance_specialist_agent": {
                "skills": ["us-apparel-compliance", "shopify-product-policy", "ebay-us-fashion-policy"],
                "tools": ["list_project_resources", "summarize_canonical_products", "list_pending_approvals", "evaluate_us_apparel_compliance"],
            },
            "listing_operations_agent": {
                "skills": ["product-localization-en-us", "shopify-listing", "ebay-us-listing"],
                "tools": ["list_project_resources", "summarize_canonical_products", "create_listing_drafts"],
            },
            "governance_reviewer_agent": {
                "skills": ["catalog-governance"],
                "tools": ["list_project_resources", "summarize_canonical_products", "summarize_listing_drafts", "read_artifact_text", "list_pending_approvals", "review_catalog_release"],
            },
        }
        for worker in (
            self.catalog_steward, self.compliance_specialist,
            self.listing_operations, self.governance_reviewer,
        ):
            metadata = worker_config[worker.name]
            self.workers.register(worker.name, worker.description, metadata)
            self.workers.authorize_tools(worker.name, metadata["tools"])
        self.workflow = CatalogWorkflow(self)


def build_application(base_dir: Path) -> CrossborderApplication:
    return CrossborderApplication(Path(base_dir))
