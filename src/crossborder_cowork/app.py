from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .application import CrossborderApplication, build_application
from .util import json_dumps, sha256_file


class ProjectCreate(BaseModel):
    name: str


class TaskStepInput(BaseModel):
    title: str
    worker_name: str = "platform"


class TaskCreate(BaseModel):
    project_id: str
    objective: str
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
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/api/projects")
    def list_projects() -> dict[str, Any]:
        return {"items": application.tasks.list_projects()}

    @api.post("/api/projects", status_code=201)
    def create_project(payload: ProjectCreate) -> dict[str, Any]:
        return {"project": application.tasks.create_project(payload.name)}

    @api.get("/api/tasks")
    def list_tasks(project_id: str | None = None) -> dict[str, Any]:
        return {"items": application.tasks.list_tasks(project_id)}

    @api.post("/api/tasks", status_code=201)
    def create_task(payload: TaskCreate) -> dict[str, Any]:
        try:
            task = application.tasks.create_task(
                payload.project_id,
                payload.objective,
                payload.input,
                [step.model_dump() for step in payload.steps],
            )
        except KeyError as error:
            raise _not_found(error) from error
        return {"task": task}

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
                        yield f"id: {cursor}\nevent: {event['event_type']}\ndata: {json_dumps(event)}\n\n"
                else:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(
            generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
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
