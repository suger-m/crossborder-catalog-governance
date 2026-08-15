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
from .tools.project_context import ProjectContextTools, register_project_context_tools


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
        self.skills = SkillRegistry(self.settings.skills_dir)
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
        register_project_context_tools(self.tools)
        for tool_name, label in {
            "import_product_materials": "导入商品素材",
            "parse_product_sources": "解析商品素材",
            "write_product_graph": "写入商品图谱",
            "create_catalog_approvals": "创建事实确认",
            "check_product_compliance": "检查美国服装合规",
            "generate_listing_drafts": "生成平台草稿",
            "write_listing_graph": "写入 Listing 图谱",
            "review_catalog_governance": "审核交付一致性",
            "create_sku_matrix": "生成 SKU 矩阵",
            "create_listing_package": "生成商品目录导出包",
        }.items():
            self.tools.register(tool_name, label, {"label": label, "kind": "business"})

        self.catalog_steward = CatalogStewardAgent(
            self.intake, self.graph, self.artifacts, self.approvals, self.events, self.skills,
            self.materials, self.resources, self.tool_executor,
        )
        self.compliance_specialist = ComplianceSpecialistAgent(
            UsApparelComplianceService(self.taxonomy), self.artifacts, self.events,
            self.skills, self.approvals, self.project_context, self.resources, self.tool_executor,
        )
        self.listing_operations = ListingOperationsAgent(
            self.database, self.artifacts, self.events, self.skills, self.model_runtime,
            self.graph, self.project_context, self.resources, self.tool_executor,
        )
        self.governance_reviewer = GovernanceReviewerAgent(
            self.artifacts, self.events, self.skills, self.exporter,
            self.project_context, self.resources, self.tool_executor,
        )
        worker_config = {
            "catalog_steward_agent": {
                "skills": ["product-catalog", "womenswear-classification"],
                "tools": ["import_product_materials", "parse_product_sources", "write_product_graph", "create_catalog_approvals"],
            },
            "compliance_specialist_agent": {
                "skills": ["us-apparel-compliance", "shopify-product-policy", "ebay-us-fashion-policy"],
                "tools": ["get_canonical_products", "get_pending_approvals", "check_product_compliance"],
            },
            "listing_operations_agent": {
                "skills": ["product-localization-en-us", "shopify-listing", "ebay-us-listing"],
                "tools": ["get_canonical_products", "generate_listing_drafts", "write_listing_graph"],
            },
            "governance_reviewer_agent": {
                "skills": ["catalog-governance"],
                "tools": ["get_canonical_products", "get_listing_drafts", "read_artifact_text", "get_pending_approvals", "review_catalog_governance", "create_sku_matrix", "create_listing_package"],
            },
        }
        for worker in (
            self.catalog_steward, self.compliance_specialist,
            self.listing_operations, self.governance_reviewer,
        ):
            metadata = worker_config[worker.name]
            self.workers.register(worker.name, worker.description, metadata)
            self.workers.authorize_tools(worker.name, metadata["tools"])
        self.project_context_tools = ProjectContextTools(self.project_context, self.tool_executor)
        self.workflow = CatalogWorkflow(self)


def build_application(base_dir: Path) -> CrossborderApplication:
    return CrossborderApplication(Path(base_dir))
