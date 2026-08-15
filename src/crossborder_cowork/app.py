from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, AsyncIterator

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .application import CrossborderApplication, build_application
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
    material_ids: list[str] = Field(min_length=1)
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
    api = FastAPI(title="Cross-border Catalog Cowork API", version="0.1.0")
    api.state.crossborder_application = application
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @api.exception_handler(ValueError)
    async def value_error(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @api.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "app_id": "crossborder-catalog-cowork",
            "app_version": "0.1.0",
            "protocol_name": PROTOCOL_NAME,
            "protocol_version": PROTOCOL_VERSION,
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
            materials = application.materials.validate_project_materials(payload.project_id, payload.material_ids)
            input_data = dict(payload.input)
            input_data.pop("source_paths", None)
            task = application.tasks.create_task(
                payload.project_id,
                payload.objective,
                input_data,
                [step.model_dump() for step in payload.steps] or application.workflow.DEFAULT_STEPS,
            )
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
    def run_task(task_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
        try:
            task = application.tasks.get_task(task_id)
        except KeyError as error:
            raise _not_found(error) from error
        try:
            paths = application.materials.task_paths(task_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if not paths:
            raise HTTPException(status_code=409, detail="Select at least one project material before running the task")
        input_data = dict(task.get("input") or {})
        input_data["source_paths"] = paths
        input_data["material_ids"] = [item["id"] for item in application.materials.task_materials(task_id)]
        application.tasks.update_input(task_id, input_data)
        background_tasks.add_task(application.workflow.run_task, task_id)
        return {"task_id": task_id, "status": "queued"}

    @api.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        try:
            return application.tasks.detail(task_id, application.artifacts, application.approvals)
        except KeyError as error:
            raise _not_found(error) from error

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
    def graph_summary() -> dict[str, Any]:
        return application.graph.store.summary()

    @api.get("/api/products")
    def list_products(task_id: str = "") -> dict[str, Any]:
        return {"items": application.graph.list_products(task_id)}

    @api.get("/api/products/{product_id}")
    def get_product(product_id: str) -> dict[str, Any]:
        product = application.graph.get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

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
        return {"items": [item.public_dict() for item in application.workers.list()]}

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
    api.add_api_route("/cowork/tasks/{task_id}/events", poll_events, methods=["GET"])
    api.add_api_route("/cowork/tasks/{task_id}/events/stream", stream_events, methods=["GET"])
    api.add_api_route("/cowork/artifacts/{artifact_id}/download", download_artifact, methods=["GET"])
    api.add_api_route("/cowork/skills", list_skills, methods=["GET"])
    api.add_api_route("/cowork/skills/{name}", get_skill, methods=["GET"])
    api.add_api_route("/cowork/workers", list_workers, methods=["GET"])
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
