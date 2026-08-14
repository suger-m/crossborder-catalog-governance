from __future__ import annotations

from typing import Any

from ..platform.database import Database
from ..util import json_dumps, json_loads, utc_now


class GraphStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_node(self, node: dict[str, Any]) -> None:
        now = utc_now()
        self.db.execute(
            """INSERT INTO graph_nodes(id,node_type,state,version,data_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
               node_type=excluded.node_type,state=excluded.state,version=excluded.version,
               data_json=excluded.data_json,updated_at=excluded.updated_at""",
            (node["id"], node["node_type"], node["state"], node["version"], json_dumps(node.get("data", {})), now, now),
        )

    def upsert_edge(self, edge: dict[str, Any]) -> None:
        now = utc_now()
        self.db.execute(
            """INSERT INTO graph_edges(id,source_id,relation_type,target_id,state,version,data_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
               state=excluded.state,version=excluded.version,data_json=excluded.data_json,updated_at=excluded.updated_at""",
            (edge["id"], edge["source_id"], edge["relation_type"], edge["target_id"], edge["state"], edge["version"], json_dumps(edge.get("data", {})), now, now),
        )

    def summary(self) -> dict[str, Any]:
        nodes = self.db.fetchall("SELECT node_type, state, COUNT(*) AS count FROM graph_nodes GROUP BY node_type,state")
        edges = self.db.fetchall("SELECT relation_type, state, COUNT(*) AS count FROM graph_edges GROUP BY relation_type,state")
        return {"nodes": nodes, "edges": edges}

    def product_graph(self, product_id: str) -> dict[str, Any]:
        node_ids = {product_id}
        edges = self.db.fetchall("SELECT * FROM graph_edges WHERE source_id=? OR target_id=?", (product_id, product_id))
        for edge in edges:
            node_ids.add(edge["source_id"])
            node_ids.add(edge["target_id"])
            edge["data"] = json_loads(edge.pop("data_json"), {})
        if not node_ids:
            return {"nodes": [], "edges": []}
        placeholders = ",".join("?" for _ in node_ids)
        nodes = self.db.fetchall(f"SELECT * FROM graph_nodes WHERE id IN ({placeholders})", tuple(node_ids))
        for node in nodes:
            node["data"] = json_loads(node.pop("data_json"), {})
        return {"nodes": nodes, "edges": edges}
