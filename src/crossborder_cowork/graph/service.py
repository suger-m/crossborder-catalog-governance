from __future__ import annotations

from typing import Iterable

from ..catalog.models import CanonicalProduct
from ..platform.database import Database
from ..platform.execution_context import current_execution_context
from ..util import json_dumps, stable_id, utc_now
from .models import ALLOWED_NODE_TYPES, ALLOWED_RELATIONS, GraphEdge, GraphNode
from .store import GraphStore


class CatalogGraphService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.store = GraphStore(db)

    def upsert_candidate_graph(self, products: Iterable[CanonicalProduct], task_id: str = "", project_id: str = "") -> dict:
        project_id = self._resolve_project_id(project_id=project_id, task_id=task_id)
        product_list = list(products)
        now = utc_now()
        for product in product_list:
            if task_id:
                self.db.execute(
                    "INSERT OR IGNORE INTO task_products(task_id,product_id,project_id,created_at) VALUES(?,?,?,?)",
                    (task_id, product.id, project_id, now),
                )
            self.db.execute(
                """INSERT INTO products(id,project_id,external_id,title,version,status,data_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET project_id=excluded.project_id,title=excluded.title,
                   version=excluded.version,status=excluded.status,data_json=excluded.data_json,updated_at=excluded.updated_at""",
                (product.id, project_id, product.external_id, product.title, product.version, product.status, json_dumps(product.model_dump()), now, now),
            )
            self.add_node(GraphNode(id=product.id, node_type="Product", state=product.status if product.status in {"candidate","confirmed","rejected","superseded"} else "candidate", version=product.version, data={"title": product.title, "external_id": product.external_id}), project_id)
            for sku in product.skus:
                self.db.execute(
                    """INSERT INTO skus(id,project_id,product_id,external_id,data_json,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET project_id=excluded.project_id,data_json=excluded.data_json,updated_at=excluded.updated_at""",
                    (sku.id, project_id, product.id, sku.external_id, json_dumps(sku.model_dump()), now, now),
                )
                self.add_node(GraphNode(id=sku.id, node_type="SKU", data={"external_id": sku.external_id, "size": sku.size, "color": sku.color}), project_id)
                self.add_edge(GraphEdge(id=stable_id("edge", project_id, product.id, "HAS_SKU", sku.id), source_id=product.id, relation_type="HAS_SKU", target_id=sku.id), project_id)
            for material in product.materials:
                material_id = stable_id("mat", project_id, material)
                self.add_node(GraphNode(id=material_id, node_type="Material", state="confirmed", data={"name": material}), project_id)
                self.add_edge(GraphEdge(id=stable_id("edge", project_id, product.id, "USES_MATERIAL", material_id), source_id=product.id, relation_type="USES_MATERIAL", target_id=material_id), project_id)
            category = product.garment_type or product.category
            if category:
                category_id = stable_id("cat", project_id, category)
                self.add_node(GraphNode(id=category_id, node_type="Category", state="confirmed", data={"name": category}), project_id)
                self.add_edge(GraphEdge(id=stable_id("edge", project_id, product.id, "BELONGS_TO", category_id), source_id=product.id, relation_type="BELONGS_TO", target_id=category_id), project_id)
            for claim in product.claims:
                claim_id = stable_id("claim", project_id, claim)
                self.add_node(GraphNode(id=claim_id, node_type="Claim", data={"text": claim}), project_id)
                self.add_edge(GraphEdge(id=stable_id("edge", project_id, product.id, "MAKES_CLAIM", claim_id), source_id=product.id, relation_type="MAKES_CLAIM", target_id=claim_id), project_id)
            for certification in product.certifications:
                certification_id = stable_id("cert", project_id, certification)
                self.add_node(GraphNode(id=certification_id, node_type="Certification", data={"name": certification}), project_id)
                self.add_edge(GraphEdge(id=stable_id("edge", project_id, product.id, "REQUIRES", certification_id), source_id=product.id, relation_type="REQUIRES", target_id=certification_id), project_id)
            market_id = stable_id("market", project_id, "us")
            self.add_node(GraphNode(id=market_id, node_type="Market", state="confirmed", data={"name": "United States"}), project_id)
            self.add_edge(GraphEdge(id=stable_id("edge", project_id, product.id, "TARGETS", market_id), source_id=product.id, relation_type="TARGETS", target_id=market_id), project_id)
            for fact in product.facts:
                taxonomy_node_id = fact.taxonomy.node_id if fact.taxonomy else ""
                taxonomy_version = fact.taxonomy.taxonomy_version if fact.taxonomy else ""
                self.db.execute(
                    """INSERT INTO product_facts(
                           id,project_id,product_id,field_name,value_json,state,confidence,
                           source_document_id,evidence_text,evidence_location,taxonomy_node_id,
                           taxonomy_version,created_at,updated_at
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET value_json=excluded.value_json,state=excluded.state,
                       confidence=excluded.confidence,project_id=excluded.project_id,updated_at=excluded.updated_at""",
                    (fact.id, project_id, product.id, fact.field_name, json_dumps(fact.value), fact.state, fact.confidence,
                     fact.evidence.source_document_id, fact.evidence.text, fact.evidence.location,
                     taxonomy_node_id, taxonomy_version, now, now),
                )
                source_id = fact.evidence.source_document_id
                self.add_node(GraphNode(id=source_id, node_type="SourceDocument", state="confirmed", data={"file_name": fact.evidence.file_name}), project_id)
                self.add_edge(GraphEdge(id=stable_id("edge", project_id, product.id, "SUPPORTED_BY", source_id), source_id=product.id, relation_type="SUPPORTED_BY", target_id=source_id, state="confirmed"), project_id)
                self.db.execute(
                    """INSERT OR REPLACE INTO graph_evidence(
                           id,project_id,subject_id,source_document_id,evidence_text,evidence_location,created_at
                       ) VALUES(?,?,?,?,?,?,?)""",
                    (stable_id("gevd", project_id, fact.id), project_id, fact.id, source_id, fact.evidence.text, fact.evidence.location, now),
                )
            self.db.execute(
                """INSERT OR REPLACE INTO graph_versions(
                       id,project_id,product_id,version,snapshot_json,created_at
                   ) VALUES(?,?,?,?,?,?)""",
                (stable_id("gver", project_id, product.id, product.version), project_id, product.id, product.version, json_dumps(product.model_dump()), now),
            )
        return self.store.summary(project_id)

    def add_node(self, node: GraphNode, project_id: str = "") -> None:
        if node.node_type not in ALLOWED_NODE_TYPES:
            raise ValueError(f"Unknown graph node type: {node.node_type}")
        self.store.upsert_node(node.model_dump(), self._resolve_project_id(project_id=project_id))

    def add_edge(self, edge: GraphEdge, project_id: str = "") -> None:
        if edge.relation_type not in ALLOWED_RELATIONS:
            raise ValueError(f"Unknown graph relation: {edge.relation_type}")
        self.store.upsert_edge(edge.model_dump(), self._resolve_project_id(project_id=project_id))

    def list_products(self, task_id: str = "", project_id: str = "") -> list[dict]:
        project_id = self._resolve_project_id(project_id=project_id, task_id=task_id)
        if task_id:
            rows = self.db.fetchall(
                """SELECT p.id,p.external_id,p.title,p.version,p.status,p.data_json
                   FROM products p JOIN task_products tp ON tp.product_id=p.id
                   WHERE tp.task_id=? AND tp.project_id=? AND p.project_id=? ORDER BY p.title""",
                (task_id, project_id, project_id),
            )
        else:
            rows = self.db.fetchall(
                "SELECT id,external_id,title,version,status,data_json FROM products WHERE project_id=? ORDER BY title",
                (project_id,),
            )
        from ..util import json_loads
        for row in rows:
            row["data"] = json_loads(row.pop("data_json"), {})
        return rows

    def get_product(self, product_id: str, project_id: str = "", task_id: str = "") -> dict | None:
        project_id = self._resolve_project_id(project_id=project_id, task_id=task_id)
        row = self.db.fetchone("SELECT * FROM products WHERE id=? AND project_id=?", (product_id, project_id))
        if not row:
            return None
        from ..util import json_loads
        row["data"] = json_loads(row.pop("data_json"), {})
        row["graph"] = self.store.product_graph(product_id, project_id)
        return row

    def list_product_facts(self, project_id: str, product_ids: Iterable[str] | None = None) -> list[dict]:
        ids = list(dict.fromkeys(str(item) for item in (product_ids or []) if str(item)))
        if ids:
            placeholders = ",".join("?" for _ in ids)
            rows = self.db.fetchall(
                f"SELECT * FROM product_facts WHERE project_id=? AND product_id IN ({placeholders}) ORDER BY product_id,field_name",
                (project_id, *ids),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM product_facts WHERE project_id=? ORDER BY product_id,field_name", (project_id,),
            )
        from ..util import json_loads
        for row in rows:
            row["value"] = json_loads(row.pop("value_json"), None)
        return rows

    def list_listings(self, project_id: str, platforms: Iterable[str] | None = None) -> list[dict]:
        values = list(dict.fromkeys(str(item) for item in (platforms or []) if str(item)))
        if values:
            placeholders = ",".join("?" for _ in values)
            rows = self.db.fetchall(
                f"SELECT * FROM listings WHERE project_id=? AND platform IN ({placeholders}) ORDER BY platform,product_id",
                (project_id, *values),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM listings WHERE project_id=? ORDER BY platform,product_id", (project_id,),
            )
        from ..util import json_loads
        for row in rows:
            row["data"] = json_loads(row.pop("data_json"), {})
        return rows

    def _resolve_project_id(self, *, project_id: str = "", task_id: str = "") -> str:
        if task_id:
            task = self.db.fetchone("SELECT project_id FROM tasks WHERE id=?", (task_id,))
            if not task:
                raise KeyError(f"Task not found: {task_id}")
            if project_id and project_id != task["project_id"]:
                raise ValueError("Task does not belong to this project")
            return str(task["project_id"])
        if project_id:
            return project_id
        execution = current_execution_context(required=False)
        if execution:
            return execution.project_id
        raise ValueError("project_id or task_id is required")
