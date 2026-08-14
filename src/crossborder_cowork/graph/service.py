from __future__ import annotations

from typing import Iterable

from ..catalog.models import CanonicalProduct
from ..platform.database import Database
from ..util import json_dumps, stable_id, utc_now
from .models import ALLOWED_NODE_TYPES, ALLOWED_RELATIONS, GraphEdge, GraphNode
from .store import GraphStore


class CatalogGraphService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.store = GraphStore(db)

    def upsert_candidate_graph(self, products: Iterable[CanonicalProduct], task_id: str = "") -> dict:
        product_list = list(products)
        now = utc_now()
        for product in product_list:
            if task_id:
                self.db.execute(
                    "INSERT OR IGNORE INTO task_products(task_id,product_id,created_at) VALUES(?,?,?)",
                    (task_id, product.id, now),
                )
            self.db.execute(
                """INSERT INTO products(id,external_id,title,version,status,data_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,
                   version=excluded.version,status=excluded.status,data_json=excluded.data_json,updated_at=excluded.updated_at""",
                (product.id, product.external_id, product.title, product.version, product.status, json_dumps(product.model_dump()), now, now),
            )
            self.add_node(GraphNode(id=product.id, node_type="Product", state=product.status if product.status in {"candidate","confirmed","rejected","superseded"} else "candidate", version=product.version, data={"title": product.title, "external_id": product.external_id}))
            for sku in product.skus:
                self.db.execute(
                    """INSERT INTO skus(id,product_id,external_id,data_json,created_at,updated_at)
                       VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET data_json=excluded.data_json,updated_at=excluded.updated_at""",
                    (sku.id, product.id, sku.external_id, json_dumps(sku.model_dump()), now, now),
                )
                self.add_node(GraphNode(id=sku.id, node_type="SKU", data={"external_id": sku.external_id, "size": sku.size, "color": sku.color}))
                self.add_edge(GraphEdge(id=stable_id("edge", product.id, "HAS_SKU", sku.id), source_id=product.id, relation_type="HAS_SKU", target_id=sku.id))
            for material in product.materials:
                material_id = stable_id("mat", material)
                self.add_node(GraphNode(id=material_id, node_type="Material", state="confirmed", data={"name": material}))
                self.add_edge(GraphEdge(id=stable_id("edge", product.id, "USES_MATERIAL", material_id), source_id=product.id, relation_type="USES_MATERIAL", target_id=material_id))
            category = product.garment_type or product.category
            if category:
                category_id = stable_id("cat", category)
                self.add_node(GraphNode(id=category_id, node_type="Category", state="confirmed", data={"name": category}))
                self.add_edge(GraphEdge(id=stable_id("edge", product.id, "BELONGS_TO", category_id), source_id=product.id, relation_type="BELONGS_TO", target_id=category_id))
            for claim in product.claims:
                claim_id = stable_id("claim", claim)
                self.add_node(GraphNode(id=claim_id, node_type="Claim", data={"text": claim}))
                self.add_edge(GraphEdge(id=stable_id("edge", product.id, "MAKES_CLAIM", claim_id), source_id=product.id, relation_type="MAKES_CLAIM", target_id=claim_id))
            for certification in product.certifications:
                certification_id = stable_id("cert", certification)
                self.add_node(GraphNode(id=certification_id, node_type="Certification", data={"name": certification}))
                self.add_edge(GraphEdge(id=stable_id("edge", product.id, "REQUIRES", certification_id), source_id=product.id, relation_type="REQUIRES", target_id=certification_id))
            market_id = "market_us"
            self.add_node(GraphNode(id=market_id, node_type="Market", state="confirmed", data={"name": "United States"}))
            self.add_edge(GraphEdge(id=stable_id("edge", product.id, "TARGETS", market_id), source_id=product.id, relation_type="TARGETS", target_id=market_id))
            for fact in product.facts:
                taxonomy_node_id = fact.taxonomy.node_id if fact.taxonomy else ""
                taxonomy_version = fact.taxonomy.taxonomy_version if fact.taxonomy else ""
                self.db.execute(
                    """INSERT INTO product_facts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET value_json=excluded.value_json,state=excluded.state,
                       confidence=excluded.confidence,updated_at=excluded.updated_at""",
                    (fact.id, product.id, fact.field_name, json_dumps(fact.value), fact.state, fact.confidence,
                     fact.evidence.source_document_id, fact.evidence.text, fact.evidence.location,
                     taxonomy_node_id, taxonomy_version, now, now),
                )
                source_id = fact.evidence.source_document_id
                self.add_node(GraphNode(id=source_id, node_type="SourceDocument", state="confirmed", data={"file_name": fact.evidence.file_name}))
                self.add_edge(GraphEdge(id=stable_id("edge", product.id, "SUPPORTED_BY", source_id), source_id=product.id, relation_type="SUPPORTED_BY", target_id=source_id, state="confirmed"))
                self.db.execute(
                    "INSERT OR REPLACE INTO graph_evidence(id,subject_id,source_document_id,evidence_text,evidence_location,created_at) VALUES(?,?,?,?,?,?)",
                    (stable_id("gevd", fact.id), fact.id, source_id, fact.evidence.text, fact.evidence.location, now),
                )
            self.db.execute(
                "INSERT OR REPLACE INTO graph_versions(id,product_id,version,snapshot_json,created_at) VALUES(?,?,?,?,?)",
                (stable_id("gver", product.id, product.version), product.id, product.version, json_dumps(product.model_dump()), now),
            )
        return self.store.summary()

    def add_node(self, node: GraphNode) -> None:
        if node.node_type not in ALLOWED_NODE_TYPES:
            raise ValueError(f"Unknown graph node type: {node.node_type}")
        self.store.upsert_node(node.model_dump())

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.relation_type not in ALLOWED_RELATIONS:
            raise ValueError(f"Unknown graph relation: {edge.relation_type}")
        self.store.upsert_edge(edge.model_dump())

    def list_products(self, task_id: str = "") -> list[dict]:
        if task_id:
            rows = self.db.fetchall(
                """SELECT p.id,p.external_id,p.title,p.version,p.status,p.data_json
                   FROM products p JOIN task_products tp ON tp.product_id=p.id
                   WHERE tp.task_id=? ORDER BY p.title""", (task_id,),
            )
        else:
            rows = self.db.fetchall("SELECT id,external_id,title,version,status,data_json FROM products ORDER BY title")
        from ..util import json_loads
        for row in rows:
            row["data"] = json_loads(row.pop("data_json"), {})
        return rows

    def get_product(self, product_id: str) -> dict | None:
        row = self.db.fetchone("SELECT * FROM products WHERE id=?", (product_id,))
        if not row:
            return None
        from ..util import json_loads
        row["data"] = json_loads(row.pop("data_json"), {})
        row["graph"] = self.store.product_graph(product_id)
        return row
