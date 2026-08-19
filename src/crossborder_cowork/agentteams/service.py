from __future__ import annotations

import json
import os
import time
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote

import httpx

from .storage import AgentTeamsObjectStore


class AgentTeamsUnavailable(RuntimeError):
    """Raised when the external AgentTeams installation is not reachable."""


@dataclass(frozen=True, slots=True)
class AgentTeamsServiceState:
    status: str
    mode: str
    matrix_url: str
    controller_url: str
    manager_user: str
    last_error: str = ""
    last_probe_at: str = ""

    def public_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.status == "ready",
            "mode": self.mode,
            "matrix_url": self.matrix_url,
            "controller_url": self.controller_url,
            "manager_user": self.manager_user,
            "last_error": self.last_error,
            "last_probe_at": self.last_probe_at,
        }


class AgentTeamsMatrixClient:
    """Requester-side Matrix client for the real AgentTeams Manager."""

    def __init__(self, *, base_url: str, username: str, password: str, manager_user: str, domain: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.manager_user = manager_user
        self.domain = domain
        self._token = ""
        self._lock = Lock()

    def _request(self, method: str, path: str, *, token: str = "", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = httpx.request(method, f"{self.base_url}{path}", headers=headers, json=payload, timeout=15)
        if response.status_code < 200 or response.status_code >= 300:
            raise AgentTeamsUnavailable(f"matrix_http_{response.status_code}: {response.text[:300]}")
        data = response.json() if response.content else {}
        return data if isinstance(data, dict) else {}

    def login(self) -> str:
        with self._lock:
            if self._token:
                return self._token
            if not self.username or not self.password:
                raise AgentTeamsUnavailable("agentteams_matrix_credentials_missing")
            data = self._request(
                "POST", "/_matrix/client/v3/login",
                payload={
                    "type": "m.login.password",
                    "identifier": {"type": "m.id.user", "user": self.username},
                    "password": self.password,
                },
            )
            self._token = str(data.get("access_token") or "")
            if not self._token:
                raise AgentTeamsUnavailable("agentteams_matrix_login_missing_token")
            return self._token

    def probe(self) -> dict[str, Any]:
        return self._request("GET", "/_matrix/client/v3/account/whoami", token=self.login())

    def _room_members(self, room_id: str, token: str) -> list[str]:
        encoded = quote(room_id, safe="")
        data = self._request("GET", f"/_matrix/client/v3/rooms/{encoded}/members", token=token)
        return [str(item.get("state_key") or "") for item in data.get("chunk", []) if isinstance(item, dict)]

    def manager_room(self) -> str:
        token = self.login()
        manager_prefix = f"@{self.manager_user}:"
        rooms = self._request("GET", "/_matrix/client/v3/joined_rooms", token=token).get("joined_rooms", [])
        for room_id in rooms if isinstance(rooms, list) else []:
            members = self._room_members(str(room_id), token)
            if len(members) == 2 and any(member.startswith(manager_prefix) for member in members):
                return str(room_id)
        manager_id = f"@{self.manager_user}:{self.domain}"
        created = self._request(
            "POST", "/_matrix/client/v3/createRoom", token=token,
            payload={"is_direct": True, "invite": [manager_id], "preset": "trusted_private_chat"},
        )
        room_id = str(created.get("room_id") or "")
        if not room_id:
            raise AgentTeamsUnavailable("agentteams_manager_room_not_created")
        return room_id

    def messages(self, room_id: str, limit: int = 50) -> list[dict[str, Any]]:
        encoded = quote(room_id, safe="")
        data = self._request("GET", f"/_matrix/client/v3/rooms/{encoded}/messages?dir=b&limit={int(limit)}", token=self.login())
        return [item for item in data.get("chunk", []) if isinstance(item, dict)]

    def joined_rooms(self) -> list[str]:
        data = self._request("GET", "/_matrix/client/v3/joined_rooms", token=self.login())
        return [
            str(room_id)
            for room_id in data.get("joined_rooms", [])
            if str(room_id).strip()
        ]

    def send(self, room_id: str, body: str) -> str:
        encoded = quote(room_id, safe="")
        txn_id = f"crossborder-{time.time_ns()}"
        data = self._request(
            "PUT", f"/_matrix/client/v3/rooms/{encoded}/send/m.room.message/{txn_id}", token=self.login(),
            payload={"msgtype": "m.text", "body": body},
        )
        return str(data.get("event_id") or txn_id)


class AgentTeamsService:
    """Lifecycle and requester boundary for the actual AgentTeams services."""

    def __init__(self, application: Any, *, base_dir: Any) -> None:
        self.application = application
        self.base_dir = base_dir
        env_file = Path(os.getenv("AGENTTEAMS_ENV_FILE") or (Path.home() / "agentteams-manager.env")).expanduser()
        file_values: dict[str, str] = {}
        if env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                    raw = line.strip()
                    if not raw or raw.startswith("#") or "=" not in raw:
                        continue
                    key, value = raw.split("=", 1)
                    file_values[key.strip()] = value.strip().strip('"').strip("'")
            except OSError:
                file_values = {}

        def setting(name: str, default: str = "") -> str:
            return os.getenv(name, "").strip() or file_values.get(name, "").strip() or default

        self.mode = setting("CROSSBORDER_AGENTTEAMS_MODE", "external").lower() or "external"
        gateway_port = setting("AGENTTEAMS_PORT_GATEWAY", "18080")
        self.matrix_url = setting("AGENTTEAMS_MATRIX_URL", f"http://127.0.0.1:{gateway_port}").rstrip("/")
        # Embedded AgentTeams intentionally keeps :8090 internal.  An explicit
        # URL is required before this requester reads Controller resources.
        self.controller_url = (
            setting("AGENTTEAMS_CONTROLLER_PUBLIC_URL")
            or setting("AGENTTEAMS_CONTROLLER_API_URL")
            or setting("AGENTTEAMS_CONTROLLER_URL")
        ).rstrip("/")
        self.manager_user = setting("AGENTTEAMS_MANAGER_USER", "manager") or "manager"
        self.controller_token = setting("AGENTTEAMS_AUTH_TOKEN") or setting("AGENTTEAMS_CONTROLLER_TOKEN")
        workspace = setting("AGENTTEAMS_WORKSPACE_DIR")
        if workspace:
            self.workspace_dir = Path(workspace).expanduser().resolve()
        else:
            self.workspace_dir = (Path.home() / "agentteams-manager").resolve()
        shared_dir = setting("AGENTTEAMS_SHARED_DIR")
        self.shared_dir = Path(shared_dir).expanduser().resolve() if shared_dir else None
        token_file = os.getenv("AGENTTEAMS_AUTH_TOKEN_FILE", "").strip()
        if not self.controller_token and token_file:
            try:
                self.controller_token = open(token_file, encoding="utf-8").read().strip()
            except OSError:
                self.controller_token = ""
        self.matrix = AgentTeamsMatrixClient(
            base_url=self.matrix_url,
            username=setting("AGENTTEAMS_ADMIN_USER", "admin"),
            password=setting("AGENTTEAMS_ADMIN_PASSWORD"),
            manager_user=self.manager_user,
            domain=setting("AGENTTEAMS_MATRIX_DOMAIN", f"matrix-local.agentteams.io:{gateway_port}"),
        )
        storage_endpoint = (
            setting("AGENTTEAMS_FS_PUBLIC_URL")
            or setting("AGENTTEAMS_MINIO_PUBLIC_URL")
        )
        self.object_store = AgentTeamsObjectStore(
            endpoint=storage_endpoint,
            bucket=setting("AGENTTEAMS_FS_BUCKET", "agentteams-storage"),
            access_key=setting("AGENTTEAMS_FS_ACCESS_KEY", "default"),
            secret_key=setting("AGENTTEAMS_FS_SECRET_KEY") or setting("AGENTTEAMS_MINIO_PASSWORD"),
        )
        self._state = AgentTeamsServiceState("stopped", self.mode, self.matrix_url, self.controller_url, self.manager_user)
        self._room_by_task: dict[str, str] = {}
        self._manager_room_id = ""
        self._last_probe_monotonic = 0.0

    def start(self) -> AgentTeamsServiceState:
        self._last_probe_monotonic = time.monotonic()
        if self.mode in {"disabled", "off"}:
            self._state = AgentTeamsServiceState("disabled", self.mode, self.matrix_url, self.controller_url, self.manager_user)
            return self._state
        try:
            self.matrix.probe()
        except Exception as exc:
            self._state = AgentTeamsServiceState(
                "waiting_for_agentteams", self.mode, self.matrix_url, self.controller_url,
                self.manager_user, str(exc)[:1000], time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            return self._state
        self._state = AgentTeamsServiceState(
            "ready", self.mode, self.matrix_url, self.controller_url,
            self.manager_user, "", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        return self._state

    def refresh(self, *, min_interval_seconds: float = 3.0) -> AgentTeamsServiceState:
        """Re-probe an external installation without making the Web UI restart.

        The Web API can start before Docker/AgentTeams.  A single failed startup
        probe must therefore remain recoverable, while frequent browser polling
        must not create a request storm against Matrix.
        """
        if self._state.status in {"ready", "disabled"}:
            return self._state
        if time.monotonic() - self._last_probe_monotonic < min_interval_seconds:
            return self._state
        return self.start()

    def stop(self) -> AgentTeamsServiceState:
        self._state = AgentTeamsServiceState("stopped", self.mode, self.matrix_url, self.controller_url, self.manager_user)
        return self._state

    def state(self) -> AgentTeamsServiceState:
        return self._state

    def list_workers(self) -> list[dict[str, Any]]:
        if self._state.status != "ready":
            return []
        if not self.controller_url:
            return []
        headers = {"Authorization": f"Bearer {self.controller_token}"} if self.controller_token else {}
        response = httpx.get(f"{self.controller_url}/api/v1/workers", headers=headers, timeout=15)
        if response.status_code < 200 or response.status_code >= 300:
            raise AgentTeamsUnavailable(f"controller_http_{response.status_code}: {response.text[:300]}")
        payload = response.json() if response.content else {}
        items = payload.get("items") if isinstance(payload, dict) else payload
        if items is None and isinstance(payload, dict):
            # AgentTeams Controller's native ListWorkers response uses the
            # resource-shaped `workers` field; `items` is accepted only for
            # compatible Controller revisions.
            items = payload.get("workers")
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    def _controller_get(self, path: str, *, params: dict[str, str] | None = None) -> dict[str, Any] | None:
        """Read an official AgentTeams Controller resource when exposed.

        Some embedded AgentTeams images predate the project-inspection routes.
        A 404 is therefore a capability miss, not a task failure; the shared
        object-store snapshot below remains the authoritative fallback.
        """
        if not self.controller_url:
            return None
        headers = {"Authorization": f"Bearer {self.controller_token}"} if self.controller_token else {}
        response = httpx.get(
            f"{self.controller_url}{path}", headers=headers, params=params or {}, timeout=15,
        )
        if response.status_code == 404:
            return None
        if response.status_code < 200 or response.status_code >= 300:
            raise AgentTeamsUnavailable(f"controller_http_{response.status_code}: {response.text[:300]}")
        data = response.json() if response.content else {}
        return data if isinstance(data, dict) else {}

    def _storage_json(self, key: str) -> dict[str, Any] | None:
        try:
            raw = self.object_store.get(key)
        except (OSError, RuntimeError, httpx.HTTPError):
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _worker_id(value: str) -> str:
        normalized = str(value or "").strip().replace("-", "_")
        aliases = {
            "crossborder_catalog_steward": "catalog_steward_agent",
            "crossborder_compliance_specialist": "compliance_specialist_agent",
            "crossborder_listing_operations": "listing_operations_agent",
            "crossborder_governance_reviewer": "governance_reviewer_agent",
        }
        return aliases.get(normalized, normalized or "agentteams")

    @staticmethod
    def _step_status(value: str) -> str:
        normalized = str(value or "").strip().lower()
        return {
            "planned": "queued", "assigned": "queued", "pending": "queued",
            "delegated": "queued", "in_progress": "running", "in-progress": "running",
            "submitted": "running", "completed": "completed", "success": "completed",
            "succeeded": "completed", "blocked": "blocked", "cancelled": "blocked",
            "revision": "waiting_approval", "waiting_user": "waiting_approval",
        }.get(normalized, "queued")

    def _workflow_snapshot(self, task_id: str) -> dict[str, Any] | None:
        task = self.application.tasks.get_task(task_id)
        project_id = str(task.get("project_id") or "")
        controller = self._controller_get(
            f"/api/v1/projects/{quote(project_id, safe='')}/workflow",
            params={"includeTasks": "true"},
        )
        if controller:
            return controller

        # The embedded controller image used by local AgentTeams versions may
        # expose workers but not project-inspection routes. TeamHarness still
        # persists the exact same JSON protocol to object storage.
        project_meta = self._storage_json(f"shared/projects/{project_id}/meta.json") or {}
        task_meta = self._storage_json(f"shared/tasks/{task_id}/meta.json") or {}
        if not project_meta and not task_meta:
            return None
        phase_history = task_meta.get("phase_history") if isinstance(task_meta.get("phase_history"), list) else []
        phase_titles = project_meta.get("phases") if isinstance(project_meta.get("phases"), dict) else {}
        project_tasks = project_meta.get("tasks") if isinstance(project_meta.get("tasks"), list) else []
        task_by_id = {
            str(item.get("task_id") or ""): item
            for item in project_tasks if isinstance(item, dict) and item.get("task_id")
        }
        nodes: list[dict[str, Any]] = []
        tasks_detail: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in phase_history:
            if not isinstance(item, dict):
                continue
            phase = str(item.get("phase") or "").strip()
            if not phase or phase in seen:
                continue
            seen.add(phase)
            node = task_by_id.get(phase, {})
            summary = str(item.get("summary") or "")
            if not summary:
                if phase == "catalog":
                    summary = f"{int(item.get('products') or 0)} 个商品 / {int(item.get('skus') or 0)} SKU / {int(item.get('conflicts') or 0)} 项冲突"
                elif phase == "compliance":
                    summary = f"{int(item.get('blocked_findings') or 0)} 项阻塞 / {int(item.get('approvals_pending') or 0)} 项待审批"
                elif phase == "listings":
                    summary = f"{int(item.get('drafts_shopify') or 0)} Shopify + {int(item.get('drafts_ebay_us') or 0)} eBay US 草稿 / gaps={int(item.get('gaps') or 0)}"
                elif phase == "governance":
                    summary = f"审核 {str(item.get('review_status') or '未定')} / {int(item.get('findings') or 0)} 项发现 / {int(item.get('approvals_pending') or 0)} 项待审批"
            nodes.append({
                "id": phase,
                "name": str(phase_titles.get(phase) or node.get("title") or phase),
                "status": "completed" if str(item.get("status") or "").upper() in {"SUCCESS", "COMPLETED"} else str(item.get("status") or ""),
                "assignee": self._worker_id(str(item.get("worker") or node.get("assigned_to") or "")),
            })
            tasks_detail.append({
                "task_id": phase,
                "project_id": project_id,
                "status": "completed" if str(item.get("status") or "").upper() in {"SUCCESS", "COMPLETED"} else str(item.get("status") or ""),
                "assigned_to": self._worker_id(str(item.get("worker") or node.get("assigned_to") or "")),
                "summary": summary,
                "result_status": str(item.get("status") or ""),
            })
        for phase, node in task_by_id.items():
            if phase in seen:
                continue
            seen.add(phase)
            nodes.append({
                "id": phase,
                "name": str(phase_titles.get(phase) or node.get("title") or phase),
                "status": str(node.get("status") or "planned"),
                "assignee": self._worker_id(str(node.get("assigned_to") or "")),
            })
        task_detail = {
            "task_id": task_id,
            "project_id": project_id,
            "status": str(task_meta.get("status") or ""),
            "summary": str(task_meta.get("summary") or ""),
            "result_status": str(task_meta.get("result_status") or ""),
            "result_path": str(task_meta.get("result_path") or ""),
            "deliverables": list(task_meta.get("deliverables") or []),
        }
        return {
            "project_id": project_id,
            "title": str(project_meta.get("title") or ""),
            "status": str(project_meta.get("status") or ""),
            "nodes": nodes,
            "tasks_detail": tasks_detail,
            "task_meta": task_meta,
        }

    def _import_external_results(self, task_id: str, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        task = self.application.tasks.get_task(task_id)
        project_id = str(task.get("project_id") or "")
        task_meta = snapshot.get("task_meta") if isinstance(snapshot.get("task_meta"), dict) else {}
        paths = [str(task_meta.get("result_path") or "")]
        paths.extend(str(item) for item in task_meta.get("deliverables") or [] if str(item).strip())
        for node in snapshot.get("nodes") or []:
            phase = str((node or {}).get("id") or "")
            if phase:
                paths.append(f"shared/tasks/{task_id}/{phase}/result.md")
        imported: list[dict[str, Any]] = []
        seen: set[str] = set()
        existing = {
            str((item.get("metadata") or {}).get("external_path") or ""): item
            for item in self.application.artifacts.list(task_id)
            if (item.get("metadata") or {}).get("source") == "agentteams_object_storage"
        }
        for relative in paths:
            relative = relative.strip().replace("\\", "/")
            if not relative.startswith("shared/") or relative in seen or ".." in relative.split("/"):
                continue
            seen.add(relative)
            try:
                content = self.object_store.get(relative)
            except (OSError, RuntimeError, httpx.HTTPError):
                content = None
            if content is None:
                continue
            if relative in existing:
                item = existing[relative]
                imported.append({"artifact_id": item["id"], "external_path": relative, "file_name": item["file_name"], "sha256": item["sha256"], "size_bytes": item["size_bytes"]})
                continue
            phase = relative.split("/")[3] if relative.startswith(f"shared/tasks/{task_id}/") else ""
            process_task_id = task_id
            step = self.application.tasks.get_step_by_external_id(task_id, phase) if phase else None
            if step:
                process_task_id = str(step["id"])
            worker_name = self._worker_id(str((step or {}).get("worker_name") or "agentteams_manager"))
            artifact = self.application.artifacts.create_bytes(
                task_id, worker_name, "agentteams_result", Path(relative).stem or "AgentTeams 结果",
                content, Path(relative).suffix.lstrip(".") or "md",
                "text/markdown" if relative.lower().endswith((".md", ".markdown", ".txt")) else "application/octet-stream",
                metadata={"logical_key": f"agentteams:{relative}", "external_path": relative, "source": "agentteams_object_storage", "resource_status": "active"},
                process_task_id=process_task_id,
            )
            imported.append({"artifact_id": artifact["id"], "external_path": relative, "file_name": artifact["file_name"], "sha256": artifact["sha256"], "size_bytes": artifact["size_bytes"]})
        return imported

    def submit(self, task_id: str, *, project_id: str, objective: str, context: dict[str, Any]) -> dict[str, Any]:
        self.refresh()
        if self._state.status != "ready":
            raise AgentTeamsUnavailable("agentteams_service_not_ready")
        room_id = self._room_by_task.get(task_id) or self.matrix.manager_room()
        self._manager_room_id = self._manager_room_id or room_id
        request = {
            "source": "crossborder-catalog-cowork-web",
            "project_id": project_id,
            "task_id": task_id,
            "objective": objective,
            "context": context,
            "instructions": [
                "Use the AgentTeams TeamHarness projectflow/taskflow runtime for durable project and task state.",
                "Do not invent a second task protocol; keep the supplied project_id and task_id in the report.",
                "Write deliverables under shared/projects/{project_id}/ or shared/tasks/{task_id}/ and report exact paths.",
                "If the objective asks for a complete catalog delivery, listing package, export, or ready-to-use channel drafts, treat the final deliverable as more than a phase report: after the necessary Workers finish, involve governance_reviewer_agent to validate release readiness and call review_catalog_release with create_export_package=true when the deterministic checks pass. If the objective explicitly asks for analysis or a single intermediate check only, do not create an export package.",
            ],
        }
        body = "CROSSBORDER_PROJECT_REQUEST\n" + json.dumps(request, ensure_ascii=False, separators=(",", ":"))
        event_id = self.matrix.send(room_id, body)
        self._room_by_task[task_id] = room_id
        return {"task_id": task_id, "status": "delegated", "service": "agentteams", "room_id": room_id, "event_id": event_id}

    def messages_for_task(self, task_id: str) -> list[dict[str, Any]]:
        """Read the Manager DM and the durable AgentTeams task rooms.

        AgentTeams does not mirror Worker-room events into the requester DM.
        The Web projection therefore must read the Matrix rooms the admin has
        joined and select events carrying this task's stable ID.  This keeps
        AgentTeams/Matrix as the collaboration truth instead of manufacturing
        a second event stream in the FastAPI process.
        """
        task = self.application.tasks.get_task(task_id)
        project_id = str(task.get("project_id") or "")
        if not self._manager_room_id:
            try:
                self._manager_room_id = self.matrix.manager_room()
            except AgentTeamsUnavailable:
                # If Matrix is temporarily unavailable, the room association
                # remains conservative: no room is trusted without an
                # explicit task/project marker in its message body.
                self._manager_room_id = ""
        worker_rooms: set[str] = set()
        try:
            worker_rooms = {
                str(item.get("roomID") or item.get("room_id") or "")
                for item in self.list_workers()
                if str(item.get("roomID") or item.get("room_id") or "").strip()
            }
        except AgentTeamsUnavailable:
            worker_rooms = set()
        known_rooms: set[str] = set()
        room_id = self._room_by_task.get(task_id)
        if room_id and room_id != self._manager_room_id and room_id not in worker_rooms:
            known_rooms.add(room_id)
        result_room = str(((task.get("result") or {}).get("agentteams") or {}).get("room_id") or "")
        if result_room and result_room != self._manager_room_id and result_room not in worker_rooms:
            known_rooms.add(result_room)
            self._room_by_task[task_id] = result_room

        try:
            room_ids = set(self.matrix.joined_rooms()) | known_rooms
        except AgentTeamsUnavailable:
            room_ids = known_rooms

        events_by_id: dict[str, dict[str, Any]] = {}
        for candidate_room in room_ids:
            try:
                events = self.matrix.messages(candidate_room, limit=100)
            except AgentTeamsUnavailable:
                continue
            for event in events:
                event_id = str(event.get("event_id") or "")
                content = event.get("content") if isinstance(event.get("content"), dict) else {}
                body = str(content.get("body") or "")
                task_ids = set(re.findall(r"\btsk_[0-9a-f]+\b", body))
                project_ids = set(re.findall(r"\bprj_[0-9a-f]+\b", body))
                # A Manager/Worker message can summarize more than one run.
                # Do not project a mixed historical message into either run,
                # even when it happens to mention the current task as well.
                if task_ids and (task_id not in task_ids or task_ids != {task_id}):
                    continue
                if project_ids and (project_id not in project_ids or project_ids != {project_id}):
                    continue
                # A task-specific room can contain planning messages without
                # repeating IDs. The shared Manager DM and unrelated joined
                # rooms must explicitly identify this task or project.
                if candidate_room not in known_rooms and task_id not in body and (not project_id or project_id not in body):
                    continue
                if event_id:
                    events_by_id[event_id] = event

        return sorted(
            events_by_id.values(),
            key=lambda item: int(item.get("origin_server_ts") or 0),
            reverse=True,
        )

    def _shared_path(self, raw_path: str, task: dict[str, Any]) -> Path | None:
        """Resolve documented TeamHarness paths only when a shared mirror is mounted.

        AgentTeams' canonical shared files live in MinIO and the Manager's
        ``/root/agentteams-fs`` mirror is container-local.  The Web process
        must not silently treat ``AGENTTEAMS_WORKSPACE_DIR`` as that mirror;
        only an explicit ``AGENTTEAMS_SHARED_DIR`` mount is safe to read.
        """
        value = str(raw_path or "").strip().replace("\\", "/")
        if not value.startswith("shared/") or ".." in value.split("/"):
            return None
        root = self.shared_dir
        if root is None:
            return None
        project_id = str(task.get("project_id") or "")
        task_id = str(task.get("id") or "")
        allowed = (
            f"shared/tasks/{task_id}/",
            f"shared/projects/{project_id}/",
        )
        if not value.startswith(allowed):
            return None
        candidate = (root / value.removeprefix("shared/")).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def _project_shared_files(self, task_id: str, paths: list[str]) -> list[dict[str, Any]]:
        """Import available TeamHarness deliverables into the platform Artifact store."""
        task = self.application.tasks.get_task(task_id)
        imported: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw_path in paths:
            path = self._shared_path(raw_path, task)
            if path is None or str(path) in seen:
                continue
            seen.add(str(path))
            try:
                relative = f"shared/{path.relative_to(self.shared_dir).as_posix()}"
                artifact = self.application.artifacts.import_file(
                    task_id,
                    "agentteams_manager",
                    "agentteams_result",
                    path.stem or "AgentTeams 交付物",
                    path,
                    "text/markdown" if path.suffix.lower() in {".md", ".markdown"} else "application/octet-stream",
                    metadata={
                        "logical_key": f"agentteams:{relative}",
                        "external_path": relative,
                        "source": "agentteams_shared_workspace",
                        "resource_status": "active",
                    },
                )
            except (OSError, ValueError, KeyError):
                continue
            imported.append({
                "artifact_id": artifact["id"],
                "external_path": relative,
                "file_name": artifact["file_name"],
                "sha256": artifact["sha256"],
                "size_bytes": artifact["size_bytes"],
            })
        return imported

    def sync_task(self, task_id: str) -> dict[str, Any] | None:
        """Project AgentTeams' durable completion marker into platform task state.

        TeamHarness owns task state and result files. The platform only maps its
        documented Matrix completion contract to the local task projection.
        """
        task = self.application.tasks.get_task(task_id)
        current = str(task.get("status") or "")
        messages = self.messages_for_task(task_id)
        snapshot = self._workflow_snapshot(task_id)
        if snapshot:
            nodes = [item for item in snapshot.get("nodes") or [] if isinstance(item, dict)]
            details = {
                str(item.get("task_id") or ""): item
                for item in snapshot.get("tasks_detail") or []
                if isinstance(item, dict) and item.get("task_id")
            }
            # AgentTeams is allowed to add or reorder DAG nodes. Its IDs are
            # external identities scoped to this task; TaskService allocates
            # local primary keys and returns the mapping used by all stores.
            local_by_external: dict[str, str] = {}
            for node in nodes:
                external_id = str(node.get("id") or "").strip()
                if not external_id:
                    continue
                step = self.application.tasks.create_step_from_workforce(
                    task_id,
                    external_id,
                    str(node.get("name") or external_id),
                    worker_name=self._worker_id(str(node.get("assignee") or "agentteams")),
                )
                local_by_external[external_id] = str(step["id"])

            for node in nodes:
                external_id = str(node.get("id") or "").strip()
                local_step_id = local_by_external.get(external_id)
                if not local_step_id:
                    continue
                dependencies = [
                    local_by_external.get(str(edge.get("source") or ""), "")
                    for edge in snapshot.get("edges") or []
                    if isinstance(edge, dict) and str(edge.get("target") or "") == external_id and edge.get("source")
                ]
                dependencies = [item for item in dependencies if item]
                self.application.tasks.set_step_dependencies(task_id, local_step_id, dependencies)
                detail = details.get(external_id) or {}
                result = {
                    "summary": str(detail.get("summary") or ""),
                    "result_status": str(detail.get("result_status") or ""),
                    "result_path": str(detail.get("result_path") or ""),
                    "deliverables": list(detail.get("deliverables") or []),
                    "agentteams_status": str(node.get("status") or ""),
                }
                self.application.tasks.update_step(
                    local_step_id,
                    self._step_status(str(node.get("status") or detail.get("status") or "")),
                    result,
                )

            task_meta = snapshot.get("task_meta") if isinstance(snapshot.get("task_meta"), dict) else {}
            external_status = str(task_meta.get("status") or "").lower()
            external_result = str(task_meta.get("result_status") or "").upper()
            if external_status in {"completed", "success", "succeeded"} or external_result in {"SUCCESS", "COMPLETED"}:
                projected = self._import_external_results(task_id, snapshot)
                if current not in {"completed", "failed"}:
                    return self.application.tasks.update_status(
                        task_id,
                        "completed",
                        {
                            **(task.get("result") or {}),
                            "summary": str(task_meta.get("summary") or "AgentTeams Manager 已确认任务完成"),
                            "agentteams_result_path": str(task_meta.get("result_path") or ""),
                            "agentteams_artifacts": projected,
                            "agentteams_snapshot": snapshot,
                            "agentteams_messages": messages[-20:],
                        },
                    )
            elif external_status in {"blocked", "cancelled"}:
                if current not in {"completed", "failed", "blocked"}:
                    return self.application.tasks.update_status(
                        task_id,
                        "blocked",
                        {**(task.get("result") or {}), "summary": "AgentTeams 任务报告阻塞", "agentteams_snapshot": snapshot, "agentteams_messages": messages[-20:]},
                    )
            elif current == "queued":
                return self.application.tasks.update_status(
                    task_id,
                    "running",
                    {**(task.get("result") or {}), "summary": "AgentTeams Manager 正在执行", "agentteams_snapshot": snapshot, "agentteams_messages": messages[-20:]},
                )

        # Matrix is the documented fallback for older Controller images. A
        # phase-level TASK_COMPLETED must never complete the root task; only a
        # Manager message with the final task id is accepted here.
        for event in messages:
            content = event.get("content") if isinstance(event.get("content"), dict) else {}
            body = str(content.get("body") or "").strip()
            sender = str(event.get("sender") or "")
            if not body:
                continue
            if re.search(rf"TASK_BLOCKED:\s*{re.escape(task_id)}\b", body) and "manager" in sender.lower():
                if current not in {"completed", "failed", "blocked"}:
                    return self.application.tasks.update_status(task_id, "blocked", {**(task.get("result") or {}), "summary": "AgentTeams Manager 报告任务阻塞", "agentteams_messages": messages[-20:]})
            if re.search(rf"TASK_COMPLETED:\s*{re.escape(task_id)}\b", body) and "PHASE" not in body.upper() and "manager" in sender.lower():
                if current not in {"completed", "failed"}:
                    return self.application.tasks.update_status(task_id, "completed", {**(task.get("result") or {}), "summary": "AgentTeams Manager 已确认任务完成", "agentteams_messages": messages[-20:]})
        return None

    def public_dict(self) -> dict[str, Any]:
        state = self._state.public_dict()
        state["active_task_rooms"] = len(self._room_by_task)
        try:
            state["workers"] = self.list_workers()
        except AgentTeamsUnavailable as exc:
            state["workers"] = []
            state["workers_error"] = str(exc)
        return state
