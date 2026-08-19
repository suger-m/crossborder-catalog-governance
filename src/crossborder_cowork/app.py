from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .application import BUSINESS_WORKER_IDS, CrossborderApplication, build_application
from .agentteams import AgentTeamsUnavailable
from .agentteams.mcp_bridge import mount_crossborder_mcp
from .util import json_dumps, sha256_file
from .platform.product_events import PROTOCOL_NAME, PROTOCOL_VERSION


def _sse_json(value: dict[str, Any]) -> str:
    """Serialize one complete SSE data field without physical line breaks."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class ProjectCreate(BaseModel):
    name: str


class TaskStepInput(BaseModel):
    title: str
    worker_name: str = "platform"


class TaskCreate(BaseModel):
    project_id: str
    objective: str
    material_ids: list[str] = Field(default_factory=list)
    input: dict[str, Any] = Field(default_factory=dict)
    steps: list[TaskStepInput] = Field(default_factory=list)


class TaskStatusUpdate(BaseModel):
    status: str
    result: dict[str, Any] | None = None
    error: str = ""


class ModelConfigPayload(BaseModel):
    source: str
    model_platform: str
    model_type: str
    api_key: str | None = None
    api_url: str = ""
    extra_params: dict[str, Any] = Field(default_factory=dict)


def _not_found(error: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


def create_api(base_dir: Path) -> FastAPI:
    application = build_application(base_dir)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        application.agentteams_service.start()
        try:
            yield
        finally:
            application.agentteams_service.stop()

    api = FastAPI(title="Cross-border Catalog Cowork API", version="0.1.0", lifespan=lifespan)
    api.state.crossborder_application = application
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    mount_crossborder_mcp(api, application)

    @api.exception_handler(ValueError)
    async def value_error(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @api.get("/health")
    def health() -> dict[str, Any]:
        application.agentteams_service.refresh()
        agentteams = application.agentteams_service.state().public_dict()
        return {
            "status": "ok" if agentteams["ready"] else "degraded",
            "app_id": "crossborder-catalog-cowork",
            "app_version": "0.1.0",
            "protocol_name": PROTOCOL_NAME,
            "protocol_version": PROTOCOL_VERSION,
            "agentteams": agentteams,
        }

    @api.get("/api/agentteams/health")
    def agentteams_health() -> dict[str, Any]:
        application.agentteams_service.refresh()
        return {
            "service": "agentteams",
            "runtime": application.agentteams_service.public_dict(),
            "service_state": application.agentteams_service.state().public_dict(),
        }

    @api.get("/api/projects")
    def list_projects() -> dict[str, Any]:
        return {"items": application.tasks.list_projects()}

    @api.post("/api/projects", status_code=201)
    def create_project(payload: ProjectCreate) -> dict[str, Any]:
        return {"project": application.tasks.create_project(payload.name)}

    @api.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, Any]:
        project = application.tasks.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        materials = application.materials.list(project_id)
        tasks = application.tasks.list_tasks(project_id)
        return {"project": project, "material_count": len(materials), "task_count": len(tasks)}

    @api.get("/api/projects/{project_id}/materials")
    def list_project_materials(project_id: str) -> dict[str, Any]:
        if not application.tasks.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        return {"items": application.materials.list(project_id)}

    @api.post("/api/projects/{project_id}/materials", status_code=201)
    async def upload_project_materials(project_id: str, files: list[UploadFile] = File(...)) -> dict[str, Any]:
        if not application.tasks.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        items = []
        for upload in files:
            items.append(application.materials.store_bytes(
                project_id,
                upload.filename or "material.bin",
                await upload.read(),
                origin="upload",
                mime_type=upload.content_type or "",
            ))
        return {"items": items}

    @api.post("/api/projects/{project_id}/materials/import-example", status_code=201)
    def import_example_materials(project_id: str) -> dict[str, Any]:
        if not application.tasks.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            return {"items": application.materials.import_example(project_id)}
        except FileNotFoundError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @api.get("/api/project-materials/{material_id}/download")
    def download_project_material(material_id: str) -> FileResponse:
        material = application.materials.get(material_id)
        if not material:
            raise HTTPException(status_code=404, detail="Project material not found")
        path = Path(material["absolute_path"]).resolve()
        try:
            path.relative_to(application.materials.root)
        except ValueError as error:
            raise HTTPException(status_code=409, detail="Project material path is invalid") from error
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Project material file is unavailable")
        digest, size = sha256_file(path)
        if digest != material["sha256"] or size != material["size_bytes"]:
            raise HTTPException(status_code=409, detail="Project material integrity check failed")
        return FileResponse(path, media_type=material["mime_type"], filename=material["file_name"])

    @api.get("/api/tasks")
    def list_tasks(project_id: str | None = None) -> dict[str, Any]:
        return {"items": application.tasks.list_tasks(project_id)}

    @api.post("/api/tasks", status_code=201)
    def create_task(payload: TaskCreate) -> dict[str, Any]:
        try:
            materials = (
                application.materials.validate_project_materials(payload.project_id, payload.material_ids)
                if payload.material_ids
                else []
            )
            input_data = dict(payload.input)
            input_data.pop("source_paths", None)
            task = application.tasks.create_task(
                payload.project_id,
                payload.objective,
                input_data,
                [step.model_dump() for step in payload.steps],
            )
            if materials:
                application.materials.bind_task(task["id"], payload.project_id, [item["id"] for item in materials])
            input_data["material_ids"] = [item["id"] for item in materials]
            input_data["source_paths"] = application.materials.task_paths(task["id"])
            task = application.tasks.update_input(task["id"], input_data)
        except KeyError as error:
            raise _not_found(error) from error
        return {"task": task}

    @api.post("/api/tasks/{task_id}/sources")
    async def upload_sources(task_id: str, files: list[UploadFile] = File(...)) -> dict[str, Any]:
        try:
            application.tasks.get_task(task_id)
        except KeyError as error:
            raise _not_found(error) from error
        task = application.tasks.get_task(task_id)
        material_ids: list[str] = []
        for upload in files:
            item = application.materials.store_bytes(
                task["project_id"], upload.filename or "material.bin", await upload.read(),
                origin="upload", mime_type=upload.content_type or "",
            )
            material_ids.append(item["id"])
        application.materials.bind_task(task_id, task["project_id"], material_ids, replace=False)
        paths = application.materials.task_paths(task_id)
        input_data = dict(task.get("input") or {})
        input_data["material_ids"] = [item["id"] for item in application.materials.task_materials(task_id)]
        input_data["source_paths"] = paths
        application.tasks.update_input(task_id, input_data)
        return {"task_id": task_id, "source_paths": paths}

    @api.post("/api/tasks/{task_id}/run")
    def run_task(task_id: str) -> dict[str, Any]:
        try:
            task = application.tasks.get_task(task_id)
        except KeyError as error:
            raise _not_found(error) from error
        try:
            paths = application.materials.task_paths(task_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        active_resources = application.resources.list(
            task["project_id"], statuses=("active",), limit=1,
        )
        selected_resources = list(dict.fromkeys(
            str(item)
            for item in (task.get("input") or {}).get("selected_resource_ids", [])
            if str(item).strip()
        ))
        if not paths and not active_resources and not selected_resources:
            raise HTTPException(
                status_code=409,
                detail="请先选择项目素材，或在项目中准备可复用的 active 资源",
            )
        input_data = dict(task.get("input") or {})
        input_data["source_paths"] = paths
        input_data["material_ids"] = [item["id"] for item in application.materials.task_materials(task_id)]
        application.tasks.update_input(task_id, input_data)
        try:
            delegation = application.agentteams_service.submit(
                task_id,
                project_id=str(task["project_id"]),
                objective=str(task["objective"]),
                context=application.task_contexts.snapshot_for_task(task_id),
            )
            application.tasks.update_status(
                task_id,
                "running",
                {"summary": "已提交给 AgentTeams Manager", "agentteams": delegation, "output_resource_ids": []},
            )
            return delegation
        except AgentTeamsUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @api.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        try:
            # Completed and failed tasks already have their durable local
            # projection. Reaching back into Matrix for every read makes the
            # Web workspace appear stuck even though the task is finished.
            # Live states still reconcile with AgentTeams so the workflow view
            # remains current while work is actually in progress.
            current = application.tasks.get_task(task_id)
            if str(current.get("status") or "") not in {"completed", "failed"}:
                try:
                    application.agentteams_service.sync_task(task_id)
                except AgentTeamsUnavailable:
                    pass
            return application.tasks.detail(
                task_id, application.artifacts, application.approvals, application.resources,
            )
        except KeyError as error:
            raise _not_found(error) from error

    @api.get("/api/tasks/{task_id}/context")
    def get_task_context(task_id: str, worker_id: str = "", process_task_id: str = "") -> dict[str, Any]:
        """Return the compact shared task-space manifest for AgentTeams Workers."""
        try:
            return application.task_contexts.snapshot_for_task(
                task_id, worker_id=worker_id,
                external_process_task_id=process_task_id,
            )
        except KeyError as error:
            raise _not_found(error) from error

    @api.get("/api/tasks/{task_id}/agentteams/messages")
    def agentteams_messages(task_id: str) -> dict[str, Any]:
        try:
            application.tasks.get_task(task_id)
            return {"items": application.agentteams_service.messages_for_task(task_id)}
        except KeyError as error:
            raise _not_found(error) from error

    @api.get("/api/agentteams")
    def agentteams_runtime() -> dict[str, Any]:
        return {
            "runtime": "agentteams",
            "service": application.agentteams_service.public_dict(),
            "local_context": "platform task context only",
        }

    @api.put("/api/tasks/{task_id}/status")
    def set_task_status(task_id: str, payload: TaskStatusUpdate) -> dict[str, Any]:
        try:
            return {"task": application.tasks.update_status(task_id, payload.status, payload.result, payload.error)}
        except KeyError as error:
            raise _not_found(error) from error

    @api.get("/api/approvals")
    def list_approvals(task_id: str) -> dict[str, Any]:
        try:
            application.tasks.get_task(task_id)
        except KeyError as error:
            raise _not_found(error) from error
        return {"items": application.approvals.list(task_id)}

    @api.post("/api/approvals/{approval_id}/approve")
    def approve(approval_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        approval = application.approvals.get(approval_id)
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        return {"task": application.workflow.approve_and_rerun(approval_id, payload or {})}

    @api.post("/api/approvals/{approval_id}/reject")
    def reject(approval_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        approval = application.approvals.decide(approval_id, "rejected", payload or {})
        return {"approval": approval}

    @api.get("/api/taxonomies")
    def list_taxonomies() -> dict[str, Any]:
        return {"items": application.taxonomy.list()}

    @api.get("/api/graph/summary")
    def graph_summary(project_id: str) -> dict[str, Any]:
        return application.graph.store.summary(project_id)

    @api.get("/api/products")
    def list_products(task_id: str = "", project_id: str = "") -> dict[str, Any]:
        if not task_id and not project_id:
            raise HTTPException(status_code=422, detail="task_id or project_id is required")
        return {"items": application.graph.list_products(task_id=task_id, project_id=project_id)}

    @api.get("/api/products/{product_id}")
    def get_product(product_id: str) -> dict[str, Any]:
        owner = application.database.fetchone("SELECT project_id FROM products WHERE id=?", (product_id,))
        product = application.graph.get_product(product_id, project_id=str((owner or {}).get("project_id") or "")) if owner else None
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

    @api.get("/api/projects/{project_id}/products")
    def list_project_products(project_id: str) -> dict[str, Any]:
        if not application.tasks.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        return {"items": application.graph.list_products(project_id=project_id)}

    @api.get("/api/projects/{project_id}/resources")
    def list_project_resources(
        project_id: str,
        resource_type: str = "",
        status: str = "",
    ) -> dict[str, Any]:
        if not application.tasks.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        return {"items": application.resources.list(
            project_id,
            resource_types=(resource_type,) if resource_type else None,
            statuses=(status,) if status else None,
        )}

    @api.get("/api/projects/{project_id}/listings")
    def list_project_listings(project_id: str, platform: str = "") -> dict[str, Any]:
        if not application.tasks.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        rows = application.graph.list_listings(project_id, (platform,) if platform else None)
        return {"items": [row.get("data", row) for row in rows]}

    @api.get("/api/projects/{project_id}/workspace/{worker_name}")
    def get_agent_workspace(project_id: str, worker_name: str) -> dict[str, Any]:
        if not application.tasks.get_project(project_id):
            raise HTTPException(status_code=404, detail="Project not found")
        if worker_name not in BUSINESS_WORKER_IDS:
            raise HTTPException(status_code=404, detail=f"Business worker role not found: {worker_name}")
        rows = application.database.fetchall(
            """SELECT step.id FROM task_steps step
               JOIN tasks task ON task.id=step.task_id
               WHERE task.project_id=? AND step.worker_name=?
               ORDER BY task.created_at,step.sequence""",
            (project_id, worker_name),
        )
        steps = [application.tasks.get_step(row["id"]) for row in rows]
        resources = application.resources.list(project_id, owner_worker_name=worker_name)
        artifacts = [
            item for item in application.artifacts.list_project(project_id)
            if item["worker_name"] == worker_name
        ]
        approvals = []
        if worker_name in {"compliance_specialist_agent", "governance_reviewer_agent"}:
            approval_rows = application.database.fetchall(
                """SELECT approval.* FROM approvals approval
                   JOIN tasks task ON task.id=approval.task_id
                   WHERE task.project_id=? ORDER BY approval.created_at""",
                (project_id,),
            )
            approvals = [application.approvals._decode(row) for row in approval_rows]
        products = application.graph.list_products(project_id=project_id) if worker_name == "catalog_steward_agent" else []
        listing_rows = application.graph.list_listings(project_id) if worker_name in {"listing_operations_agent", "governance_reviewer_agent"} else []
        listings = [row.get("data", row) for row in listing_rows]
        findings: list[dict[str, Any]] = []
        if worker_name in {"compliance_specialist_agent", "governance_reviewer_agent"}:
            artifact_types = {"compliance_result", "release_decision"}
            active_artifact_ids = {
                str(resource["storage_ref"])
                for resource in resources
                if resource.get("status") == "active" and resource.get("storage_kind") == "artifact"
            }
            for artifact in artifacts:
                if artifact["artifact_type"] not in artifact_types or artifact["id"] not in active_artifact_ids:
                    continue
                try:
                    parsed = json.loads(application.artifacts.read_text(
                        artifact["id"], project_id, offset=0, limit=65_536,
                    )["content"] or "{}")
                except (ValueError, OSError, json.JSONDecodeError):
                    continue
                if artifact["artifact_type"] == "compliance_result":
                    for result in parsed.get("results", []):
                        for key in ("legal", "shopify", "ebay"):
                            findings.extend(item for item in result.get(key, []) if isinstance(item, dict))
                else:
                    findings.extend(item for item in parsed.get("findings", []) if isinstance(item, dict))
        latest_status = str(steps[-1].get("status") or "") if steps else ""
        if not steps:
            state = "completed" if resources or artifacts else "not_started"
        elif any(str(step.get("status") or "") == "running" for step in steps):
            state = "running"
        elif latest_status in {"failed", "blocked"}:
            state = "failed"
        elif resources or artifacts or products or listings or findings:
            state = "completed"
        else:
            state = "empty"
        latest = steps[-1].get("result") if steps else {}
        return {
            "project_id": project_id,
            "worker_name": worker_name,
            "state": state,
            "steps": steps,
            "resources": resources,
            "artifacts": artifacts,
            "products": products,
            "listings": listings,
            "findings": findings,
            "approvals": approvals,
            "summary": str((latest or {}).get("summary") or ""),
            "error": "",
        }

    @api.get("/api/tasks/{task_id}/events")
    def poll_events(task_id: str, after: int = 0, limit: int = 200) -> dict[str, Any]:
        try:
            application.tasks.get_task(task_id)
        except KeyError as error:
            raise _not_found(error) from error
        return {"items": application.events.list_after(task_id, max(after, 0), min(max(limit, 1), 500))}

    @api.get("/api/tasks/{task_id}/events/stream")
    async def stream_events(request: Request, task_id: str, after: int = 0) -> StreamingResponse:
        try:
            application.tasks.get_task(task_id)
        except KeyError as error:
            raise _not_found(error) from error

        async def generate() -> AsyncIterator[str]:
            cursor = max(after, 0)
            while not await request.is_disconnected():
                events = application.events.list_after(task_id, cursor)
                if events:
                    for event in events:
                        cursor = event["sequence"]
                        yield f"id: {cursor}\nevent: {event['event_type']}\ndata: {_sse_json(event)}\n\n"
                else:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
        )

    @api.get("/api/tasks/{task_id}/product-events")
    def list_product_events(
        task_id: str, after_sequence: int = 0, limit: int = 200,
        protocol_version: int = PROTOCOL_VERSION,
    ) -> dict[str, Any]:
        try:
            application.tasks.get_task(task_id)
        except KeyError as error:
            raise _not_found(error) from error
        if protocol_version != PROTOCOL_VERSION:
            raise HTTPException(
                status_code=409,
                detail={"expected_protocol_version": PROTOCOL_VERSION, "received_protocol_version": protocol_version},
            )
        return {
            "items": application.product_events.list_after(task_id, after_sequence, limit),
            "latest_sequence": application.product_events.latest_sequence(task_id),
            "protocol_name": PROTOCOL_NAME,
            "protocol_version": PROTOCOL_VERSION,
        }

    @api.get("/api/tasks/{task_id}/product-events/stream")
    async def stream_product_events(
        request: Request, task_id: str, after_sequence: int = 0,
        protocol_version: int = PROTOCOL_VERSION,
    ) -> StreamingResponse:
        try:
            application.tasks.get_task(task_id)
        except KeyError as error:
            raise _not_found(error) from error
        if protocol_version != PROTOCOL_VERSION:
            raise HTTPException(
                status_code=409,
                detail={"expected_protocol_version": PROTOCOL_VERSION, "received_protocol_version": protocol_version},
            )

        async def generate_product_events() -> AsyncIterator[str]:
            cursor = max(after_sequence, 0)
            while not await request.is_disconnected():
                items = application.product_events.list_after(task_id, cursor)
                if items:
                    for item in items:
                        cursor = int(item["sequence"])
                        yield f"id: {cursor}\nevent: cowork_product_event\ndata: {_sse_json(item)}\n\n"
                else:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            generate_product_events(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @api.get("/api/artifacts/{artifact_id}/download")
    def download_artifact(artifact_id: str) -> FileResponse:
        artifact = application.artifacts.get(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        try:
            root = application.artifacts.root.resolve()
            path = Path(artifact["absolute_path"]).resolve()
            path.relative_to(root)
        except (OSError, ValueError):
            raise HTTPException(status_code=409, detail="Artifact path is invalid")
        if not path.is_file() or path.name != artifact["file_name"]:
            raise HTTPException(status_code=404, detail="Artifact file is unavailable")
        digest, size = sha256_file(path)
        if digest != artifact["sha256"] or size != artifact["size_bytes"]:
            raise HTTPException(status_code=409, detail="Artifact integrity check failed")
        return FileResponse(path, media_type=artifact["mime_type"], filename=artifact["file_name"])

    @api.get("/api/artifacts/{artifact_id}/preview")
    def preview_artifact(artifact_id: str, offset: int = 0, limit: int = 65_536) -> dict[str, Any]:
        artifact = application.artifacts.get(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        mime_type = str(artifact["mime_type"]).lower()
        text_like = mime_type.startswith("text/") or mime_type in {
            "application/json", "application/ld+json", "application/xml",
            "application/yaml", "application/x-yaml",
        }
        if not text_like:
            application.artifacts.validated_path(artifact_id, artifact["project_id"])
            return {
                "artifact": artifact,
                "content": None,
                "offset": 0,
                "next_offset": None,
                "truncated": False,
            }
        page = application.artifacts.read_text(
            artifact_id, artifact["project_id"], offset=offset, limit=limit,
        )
        return {
            "artifact": artifact,
            "content": page["content"],
            "offset": page["offset"],
            "next_offset": None if page["eof"] else page["next_offset"],
            "truncated": not page["eof"],
        }

    @api.get("/api/skills")
    def list_skills() -> dict[str, Any]:
        return {"items": [{"name": skill.name, "description": skill.description} for skill in application.skills.discover()]}

    @api.get("/api/skills/{name}")
    def get_skill(name: str) -> dict[str, str]:
        try:
            skill = application.skills.get(name)
        except KeyError as error:
            raise _not_found(error) from error
        return {"name": skill.name, "content": skill.load()}

    @api.get("/api/workers")
    def list_workers() -> dict[str, Any]:
        try:
            return {"items": application.agentteams_service.list_workers()}
        except AgentTeamsUnavailable as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @api.get("/api/tools")
    def list_tools() -> dict[str, Any]:
        return {"items": [item.public_dict() for item in application.tools.list()]}

    @api.get("/api/model-settings")
    def get_model_settings(role: str = "planner") -> dict[str, Any]:
        return application.settings.load_model(role).public_dict()

    @api.put("/api/model-settings")
    def put_model_settings(payload: ModelConfigPayload) -> dict[str, Any]:
        return application.settings.save_model(payload.model_dump()).public_dict()

    @api.get("/api/model-settings/readiness")
    def model_readiness() -> dict[str, Any]:
        return {role: application.model_runtime.readiness(role) for role in ("planner", "worker", "reviewer")}

    @api.post("/api/model-settings/smoke")
    def model_smoke() -> dict[str, Any]:
        return {role: application.model_runtime.smoke(role) for role in ("planner", "worker", "reviewer")}

    api.add_api_route("/model-config", get_model_settings, methods=["GET"])
    api.add_api_route("/model-config", put_model_settings, methods=["PUT"])
    api.add_api_route("/cowork/model-config", get_model_settings, methods=["GET"])
    api.add_api_route("/cowork/model-config", put_model_settings, methods=["PUT"])
    api.add_api_route("/cowork/projects", list_projects, methods=["GET"])
    api.add_api_route("/cowork/projects", create_project, methods=["POST"])
    api.add_api_route("/cowork/tasks", list_tasks, methods=["GET"])
    api.add_api_route("/cowork/tasks", create_task, methods=["POST"])
    api.add_api_route("/cowork/tasks/{task_id}", get_task, methods=["GET"])
    api.add_api_route("/cowork/tasks/{task_id}/context", get_task_context, methods=["GET"])
    api.add_api_route("/cowork/tasks/{task_id}/agentteams/messages", agentteams_messages, methods=["GET"])
    api.add_api_route("/cowork/tasks/{task_id}/events", poll_events, methods=["GET"])
    api.add_api_route("/cowork/tasks/{task_id}/events/stream", stream_events, methods=["GET"])
    api.add_api_route("/cowork/artifacts/{artifact_id}/download", download_artifact, methods=["GET"])
    api.add_api_route("/cowork/skills", list_skills, methods=["GET"])
    api.add_api_route("/cowork/skills/{name}", get_skill, methods=["GET"])
    api.add_api_route("/cowork/workers", list_workers, methods=["GET"])
    api.add_api_route("/cowork/agentteams", agentteams_runtime, methods=["GET"])
    api.add_api_route("/cowork/agentteams/health", agentteams_health, methods=["GET"])
    api.add_api_route("/cowork/tools", list_tools, methods=["GET"])
    return api


def main() -> None:
    base_dir = Path(os.getenv("CROSSBORDER_COWORK_BASE_DIR", Path.cwd()))
    uvicorn.run(
        create_api(base_dir),
        host=os.getenv("CROSSBORDER_COWORK_HOST", "127.0.0.1"),
        port=int(os.getenv("CROSSBORDER_COWORK_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
