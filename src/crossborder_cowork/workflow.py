from __future__ import annotations

import threading
from typing import Any

from .catalog.models import CanonicalProduct, ProductFact, SourceEvidence
from .util import json_dumps, stable_id
from .workforce import CrossborderWorkforceRuntime


class CatalogWorkflow:
    """Concurrency guard and approval entry point for native CAMEL Workforce."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.runtime = CrossborderWorkforceRuntime(app)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def run_task(self, task_id: str) -> dict[str, Any]:
        with self._locks_guard:
            lock = self._locks.setdefault(task_id, threading.Lock())
        if not lock.acquire(blocking=False):
            return self.app.tasks.get_task(task_id)
        try:
            return self.runtime.run(task_id)
        finally:
            lock.release()

    def approve_and_rerun(self, approval_id: str, decision: dict[str, Any]) -> dict[str, Any]:
        approval = self.app.approvals.decide(approval_id, "approved", decision)
        previous = self.app.tasks.get_task(approval["task_id"])
        input_data = dict(previous.get("input") or {})
        affected_ids = decision.get("resource_ids") or approval.get("payload", {}).get("resource_ids") or []
        input_data["approval_rerun_of"] = previous["id"]
        input_data["approval_id"] = approval["id"]
        rerun = self.app.tasks.create_task(previous["project_id"], previous["objective"], input_data=input_data)
        previous_materials = self.app.materials.task_materials(previous["id"])
        if previous_materials:
            self.app.materials.bind_task(
                rerun["id"], previous["project_id"],
                [item["id"] for item in previous_materials],
            )
        resolved_ids = self._apply_approval_decision(rerun, approval, decision)
        selected_ids = [
            *[str(item) for item in affected_ids if str(item).strip()],
            *resolved_ids,
        ]
        input_data["selected_resource_ids"] = list(dict.fromkeys(selected_ids))
        input_data["material_ids"] = [item["id"] for item in previous_materials]
        input_data["source_paths"] = self.app.materials.task_paths(rerun["id"])
        self.app.tasks.update_input(rerun["id"], input_data)
        return self.run_task(rerun["id"])

    def _apply_approval_decision(
        self,
        rerun: dict[str, Any],
        approval: dict[str, Any],
        decision: dict[str, Any],
    ) -> list[str]:
        if approval["approval_type"] not in {"catalog_conflict", "missing_required_fact"}:
            return []
        selected = decision.get("selected_value")
        if selected in (None, ""):
            raise ValueError("selected_value is required for this approval")
        payload = dict(approval.get("payload") or {})
        product_id = str(payload.get("product_id") or "")
        field_name = str(payload.get("field_name") or "")
        stored = self.app.graph.get_product(product_id, project_id=rerun["project_id"])
        if not stored or not field_name:
            raise ValueError("Approval does not reference an available product fact")
        raw = dict(stored["data"])
        raw[field_name] = selected
        raw["version"] = int(raw.get("version") or 1) + 1
        raw["status"] = "confirmed"
        facts = list(raw.get("facts") or [])
        if approval["approval_type"] == "catalog_conflict":
            for fact in facts:
                if fact.get("field_name") == field_name:
                    fact["state"] = "confirmed" if str(fact.get("value")) == str(selected) else "rejected"
        else:
            fact = ProductFact(
                id=stable_id("fact", rerun["project_id"], product_id, field_name, approval["id"], selected),
                field_name=field_name,
                value=selected,
                state="confirmed",
                confidence=1.0,
                evidence=SourceEvidence(
                    source_document_id=f"human_approval:{approval['id']}",
                    file_name="人工审批",
                    location=approval["id"],
                    text=str(selected),
                ),
            ).model_dump()
            facts.append(fact)
        raw["facts"] = facts
        product = CanonicalProduct.model_validate(raw)
        self.app.graph.upsert_candidate_graph(
            [product], task_id=rerun["id"], project_id=rerun["project_id"],
        )
        artifact = self.app.artifacts.create_text(
            rerun["id"], "catalog_steward_agent", "canonical_product",
            "canonical_product_approved", content=json_dumps({"products": [product.model_dump()]}),
            extension="json", mime_type="application/json",
            metadata={"logical_key": "canonical_product", "resource_status": "active"},
        )
        collection = self.app.resources.create(
            project_id=rerun["project_id"], resource_type="product_collection",
            logical_key="canonical-products", owner_worker_name="catalog_steward_agent",
            source_task_id=rerun["id"], storage_kind="database",
            storage_ref=rerun["project_id"], status="active",
            metadata={"product_ids": [product.id], "approval_id": approval["id"]},
        )
        return [artifact["resource_id"], collection["id"]]
