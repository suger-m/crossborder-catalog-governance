from __future__ import annotations

from pathlib import Path
import threading
from typing import Any

from .catalog.models import CanonicalProduct, ProductFact, SourceEvidence
from .platform.tasks import TaskService
from .util import utc_now
from .util import json_dumps, stable_id


class CatalogWorkflow:
    """Ordered Workforce execution for the four business Agents."""

    DEFAULT_STEPS = [
        {"title": "Build canonical Product/SKU catalog", "worker_name": "catalog_steward_agent"},
        {"title": "Evaluate US and marketplace compliance", "worker_name": "compliance_specialist_agent"},
        {"title": "Create localized Shopify and eBay drafts", "worker_name": "listing_operations_agent"},
        {"title": "Review consistency and export package", "worker_name": "governance_reviewer_agent"},
    ]

    def __init__(self, app: Any) -> None:
        self.app = app
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def run_task(self, task_id: str) -> dict[str, Any]:
        with self._locks_guard:
            lock = self._locks.setdefault(task_id, threading.Lock())
        if not lock.acquire(blocking=False):
            return self.app.tasks.get_task(task_id)
        try:
            return self._run_task_locked(task_id)
        finally:
            lock.release()

    def _run_task_locked(self, task_id: str) -> dict[str, Any]:
        task = self.app.tasks.get_task(task_id)
        self.app.tasks.ensure_default_steps(task_id, self.DEFAULT_STEPS)
        self.app.tasks.update_status(task_id, "running", {"started_at": utc_now()})
        try:
            input_data = task.get("input") or {}
            paths = [Path(path) for path in input_data.get("source_paths", [])]
            if not paths:
                raise ValueError("No source files supplied. Upload at least one catalog file before running.")
            steps = self.app.tasks.get_task(task_id)["steps"]
            catalog_step = steps[0]
            self.app.tasks.update_step(catalog_step["id"], "running")
            catalog = self.app.catalog_steward.run(task_id, paths)
            catalog = self._apply_saved_resolutions(task_id, catalog, input_data)
            self.app.tasks.update_step(catalog_step["id"], "completed", catalog)

            compliance_step = self.app.tasks.get_task(task_id)["steps"][1]
            self.app.tasks.update_step(compliance_step["id"], "running")
            compliance = self.app.compliance_specialist.run(
                task_id, catalog["products"], catalog["conflicts"], catalog["artifact_ids"],
            )
            self.app.tasks.update_step(compliance_step["id"], "completed", compliance)

            listing_step = self.app.tasks.get_task(task_id)["steps"][2]
            self.app.tasks.update_step(listing_step["id"], "running")
            listing = self.app.listing_operations.run(task_id, catalog["products"], compliance["artifact_ids"])
            self.app.tasks.update_step(listing_step["id"], "completed", listing)

            governance_step = self.app.tasks.get_task(task_id)["steps"][3]
            self.app.tasks.update_step(governance_step["id"], "running")
            approvals = self.app.approvals.list(task_id)
            review = self.app.governance_reviewer.run(
                task_id, catalog["products"], compliance["results"], listing["shopify"], listing["ebay"],
                sum(1 for item in approvals if item["status"] == "pending"),
                [*catalog["artifact_ids"], *compliance["artifact_ids"], *listing["artifact_ids"]],
            )
            governance_step_status = {
                "approved": "completed", "needs_confirmation": "waiting_approval", "blocked": "blocked",
            }[review["decision"]["status"]]
            self.app.tasks.update_step(governance_step["id"], governance_step_status, review)
            result = {"catalog": catalog, "compliance": compliance, "listing": listing, "governance": review, "completed_at": utc_now()}
            status = "completed" if review["decision"]["ready_for_export"] else ("waiting_approval" if review["decision"]["status"] == "needs_confirmation" else "blocked")
            return self.app.tasks.update_status(task_id, status, result)
        except Exception as exc:
            self.app.events.publish(task_id, "workflow.failed", "platform", {"error": str(exc)})
            return self.app.tasks.update_status(task_id, "failed", {}, str(exc))

    def approve_and_rerun(self, approval_id: str, decision: dict[str, Any]) -> dict[str, Any]:
        approval = self.app.approvals.decide(approval_id, "approved", decision)
        task = self.app.tasks.get_task(approval["task_id"])
        input_data = dict(task.get("input") or {})
        if approval["approval_type"] == "catalog_conflict":
            selected = decision.get("selected_value")
            if selected in (None, ""):
                raise ValueError("selected_value is required to resolve a catalog conflict")
            resolutions = dict(input_data.get("conflict_resolutions") or {})
            resolutions[approval["payload"]["id"]] = selected
            input_data["conflict_resolutions"] = resolutions
        elif approval["approval_type"] == "missing_required_fact":
            selected = decision.get("selected_value")
            if selected in (None, ""):
                raise ValueError("selected_value is required to provide a missing product fact")
            overrides = dict(input_data.get("fact_overrides") or {})
            payload = approval["payload"]
            overrides[f"{payload['product_id']}:{payload['field_name']}"] = {"value": selected, "approval_id": approval["id"]}
            input_data["fact_overrides"] = overrides
        self.app.database.execute("UPDATE tasks SET input_json=?,updated_at=? WHERE id=?", (json_dumps(input_data), utc_now(), task["id"]))
        return self.run_task(task["id"])

    def _apply_saved_resolutions(self, task_id: str, catalog: dict[str, Any], input_data: dict[str, Any]) -> dict[str, Any]:
        resolutions = dict(input_data.get("conflict_resolutions") or {})
        overrides = dict(input_data.get("fact_overrides") or {})
        if not resolutions and not overrides:
            return catalog
        resolved_ids: set[str] = set()
        for conflict in catalog.get("conflicts", []):
            selected = resolutions.get(conflict["id"])
            if selected in (None, ""):
                continue
            for raw in catalog.get("products", []):
                if raw.get("id") == conflict.get("product_id"):
                    raw[conflict["field_name"]] = selected
                    raw["version"] = int(raw.get("version") or 1) + 1
                    raw["status"] = "confirmed"
                    for fact in raw.get("facts", []):
                        if fact.get("field_name") == conflict["field_name"]:
                            fact["state"] = "confirmed" if str(fact.get("value")) == str(selected) else "rejected"
                    self.app.graph.upsert_candidate_graph([CanonicalProduct.model_validate(raw)], task_id)
            resolved_ids.add(conflict["id"])
            self.app.events.publish(task_id, "catalog.conflict_resolved", "human_approval", {"conflict_id": conflict["id"], "selected_value": selected})
        catalog["conflicts"] = [item for item in catalog.get("conflicts", []) if item["id"] not in resolved_ids]
        override_count = 0
        for raw in catalog.get("products", []):
            for key, override in overrides.items():
                product_id, field_name = key.split(":", 1)
                if raw.get("id") != product_id:
                    continue
                selected = override.get("value") if isinstance(override, dict) else override
                approval_id = override.get("approval_id", "") if isinstance(override, dict) else ""
                raw[field_name] = selected
                raw["version"] = int(raw.get("version") or 1) + 1
                raw["status"] = "confirmed"
                fact = ProductFact(
                    id=stable_id("fact", product_id, field_name, approval_id, selected),
                    field_name=field_name, value=selected, state="confirmed", confidence=1.0,
                    evidence=SourceEvidence(
                        source_document_id=f"human_approval:{approval_id}", file_name="Human Approval",
                        location=approval_id, text=str(selected),
                    ),
                ).model_dump()
                if not any(existing.get("id") == fact["id"] for existing in raw.setdefault("facts", [])):
                    raw["facts"].append(fact)
                override_count += 1
                self.app.events.publish(task_id, "catalog.fact_provided", "human_approval", {"product_id": product_id, "field_name": field_name})
            self.app.graph.upsert_candidate_graph([CanonicalProduct.model_validate(raw)], task_id)
        if resolved_ids or override_count:
            artifact = self.app.artifacts.create_text(
                task_id, "catalog_steward_agent", "canonical_product", "canonical_product_resolved",
                content=json_dumps({"products": catalog["products"], "conflicts": catalog["conflicts"]}),
                extension="json", mime_type="application/json", dependencies=catalog.get("artifact_ids", []),
            )
            catalog.setdefault("artifact_ids", []).append(artifact["id"])
        return catalog
