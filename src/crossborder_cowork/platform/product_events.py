from __future__ import annotations

from typing import Any, Iterable

from ..util import json_dumps, json_loads, new_id, utc_now
from .database import Database


PROTOCOL_NAME = "eigent"
PROTOCOL_VERSION = 1


def _worker_label(worker_name: str) -> str:
    return {
        "catalog_steward_agent": "商品目录专员",
        "compliance_specialist_agent": "合规专员",
        "listing_operations_agent": "商品刊登专员",
        "governance_reviewer_agent": "治理审核员",
    }.get(worker_name, worker_name.replace("_", " ").title())


def _worker_kind(worker_name: str) -> str:
    return {
        "catalog_steward_agent": "catalog_agent",
        "compliance_specialist_agent": "document_agent",
        "listing_operations_agent": "document_agent",
        "governance_reviewer_agent": "review_agent",
    }.get(worker_name, "worker_agent")


class ProductEventStore:
    """Authoritative, versioned UI product-event stream.

    Domain services publish durable platform events. This service projects
    those events into the Eigent workspace protocol on the backend so desktop
    clients never have to infer worker, file, approval, or task state from log
    strings.
    """

    def __init__(self, db: Database) -> None:
        self.db = db

    def append(
        self,
        task_id: str,
        action: str,
        payload: dict[str, Any],
        *,
        source_kind: str,
        source_event_id: str,
        source_ordinal: int = 0,
        run_id: str = "",
        created_at: str = "",
    ) -> dict[str, Any]:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """SELECT * FROM product_events
                   WHERE task_id=? AND source_kind=? AND source_event_id=?
                     AND source_ordinal=? AND action=?""",
                (task_id, source_kind, source_event_id, source_ordinal, action),
            ).fetchone()
            if existing:
                return self._decode(dict(existing))
            row = conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM product_events WHERE task_id=?",
                (task_id,),
            ).fetchone()
            sequence = int(row["sequence"] or 0) + 1
            event = {
                "id": new_id("pevt"),
                "task_id": task_id,
                "run_id": run_id or task_id,
                "sequence": sequence,
                "protocol_name": PROTOCOL_NAME,
                "protocol_version": PROTOCOL_VERSION,
                "action": action,
                "payload_json": payload,
                "source_kind": source_kind,
                "source_event_id": source_event_id,
                "source_ordinal": source_ordinal,
                "created_at": created_at or utc_now(),
            }
            conn.execute(
                """INSERT INTO product_events(
                       id,task_id,run_id,sequence,protocol_name,protocol_version,
                       action,payload_json,source_kind,source_event_id,source_ordinal,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event["id"], event["task_id"], event["run_id"], sequence,
                    PROTOCOL_NAME, PROTOCOL_VERSION, action, json_dumps(payload),
                    source_kind, source_event_id, source_ordinal, event["created_at"],
                ),
            )
            return event

    def append_many(
        self,
        task_id: str,
        drafts: Iterable[tuple[str, dict[str, Any]]],
        *,
        source_kind: str,
        source_event_id: str,
        created_at: str = "",
    ) -> list[dict[str, Any]]:
        return [
            self.append(
                task_id, action, payload, source_kind=source_kind,
                source_event_id=source_event_id, source_ordinal=ordinal,
                created_at=created_at,
            )
            for ordinal, (action, payload) in enumerate(drafts)
        ]

    def record_platform_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        task_id = str(event["task_id"])
        event_type = str(event["event_type"])
        source = str(event["source"])
        payload = dict(event.get("payload") or {})
        drafts: list[tuple[str, dict[str, Any]]] = []

        if event_type == "task.created":
            task = dict(payload.get("task") or {})
            drafts.append(("task_state", {"task_id": task_id, "state": "OPEN", "result": "", "task": task}))
        elif event_type == "workforce.task_decomposed":
            subtasks = payload.get("subtasks") if isinstance(payload.get("subtasks"), list) else []
            if not subtasks:
                subtasks = [
                    {
                        "id": str(step_id),
                        "title": str((self.db.fetchone("SELECT title FROM task_steps WHERE id=?", (str(step_id),)) or {}).get("title") or step_id),
                    }
                    for step_id in payload.get("subtask_ids", [])
                ]
            drafts.append(("to_sub_tasks", {
                "task_id": task_id,
                "summary_task": str(payload.get("objective") or "动态任务计划"),
                "sub_tasks": [
                    {
                        "id": str(item.get("id") or ""),
                        "content": str(item.get("title") or item.get("content") or ""),
                        "state": "OPEN",
                    }
                    for item in subtasks if isinstance(item, dict) and item.get("id")
                ],
            }))
        elif event_type == "workforce.task_assigned":
            step_id = str(payload.get("process_task_id") or payload.get("task_id") or "")
            worker_name = str(payload.get("worker_name") or payload.get("worker_id") or source)
            step = self.db.fetchone("SELECT title FROM task_steps WHERE id=?", (step_id,)) or {}
            common = {
                "agent_id": worker_name,
                "agent_name": _worker_label(worker_name),
                "worker_name": worker_name,
                "process_task_id": step_id,
                "content": str(payload.get("title") or payload.get("content") or step.get("title") or ""),
            }
            drafts.extend([
                ("create_agent", {**common, "agent_type": _worker_kind(worker_name), "tools": []}),
                ("assign_task", {
                    **common,
                    "task_id": step_id,
                    "state": "WAITING",
                    "failure_count": 0,
                    "dependencies": [str(item) for item in payload.get("dependencies", [])],
                }),
            ])
        elif event_type == "workforce.task_started":
            step_id = str(payload.get("process_task_id") or payload.get("task_id") or "")
            worker_name = str(payload.get("worker_name") or payload.get("worker_id") or source)
            step = self.db.fetchone("SELECT title FROM task_steps WHERE id=?", (step_id,)) or {}
            drafts.append(("activate_agent", {
                "agent_id": worker_name,
                "agent_name": _worker_label(worker_name),
                "worker_name": worker_name,
                "process_task_id": step_id,
                "state": "RUNNING",
                "message": str(payload.get("title") or payload.get("content") or step.get("title") or "任务已开始"),
            }))
        elif event_type in {"workforce.task_completed", "workforce.task_failed"}:
            failed = event_type.endswith("failed")
            step_id = str(payload.get("process_task_id") or payload.get("task_id") or "")
            worker_name = str(payload.get("worker_name") or payload.get("worker_id") or source)
            persisted = self.db.fetchone("SELECT result_json FROM task_steps WHERE id=?", (step_id,)) or {}
            persisted_result = json_loads(persisted.get("result_json"), {})
            summary = str(
                persisted_result.get("summary")
                or payload.get("summary")
                or payload.get("result_summary")
                or payload.get("error")
                or payload.get("error_message")
                or ("任务执行失败" if failed else "任务已完成")
            )
            output_resource_ids = persisted_result.get("output_resource_ids") or payload.get("output_resource_ids") or []
            persisted_status = str(persisted_result.get("status") or "").lower()
            state = "FAILED" if failed else {
                "blocked": "BLOCKED",
                "waiting_approval": "WAITING_APPROVAL",
                "needs_confirmation": "WAITING_APPROVAL",
            }.get(persisted_status, str(payload.get("state") or "DONE"))
            common = {
                "agent_id": worker_name,
                "agent_name": _worker_label(worker_name),
                "worker_name": worker_name,
                "process_task_id": step_id,
            }
            drafts.extend([
                ("task_state", {
                    **common,
                    "task_id": step_id,
                    "state": state,
                    "result": summary,
                    "summary": summary,
                    "failure_count": 1 if failed else 0,
                    "output_resource_ids": [str(item) for item in output_resource_ids],
                }),
                ("deactivate_agent", {**common, "state": state, "message": summary, "tokens": 0}),
            ])
        elif event_type == "agent.progress":
            step_id = str(payload.get("process_task_id") or "")
            worker_name = str(payload.get("worker_name") or source)
            drafts.append(("agent_progress", {
                "agent_id": worker_name,
                "agent_name": _worker_label(worker_name),
                "worker_name": worker_name,
                "process_task_id": step_id,
                "message": str(payload.get("message") or ""),
                "phase": str(payload.get("phase") or ""),
            }))
        elif event_type in {"tool_call.started", "tool_call.succeeded", "tool_call.failed"}:
            step_id = str(payload.get("process_task_id") or "")
            worker_name = str(payload.get("worker_name") or source)
            tool_call_id = str(payload.get("tool_call_id") or event["id"])
            tool_name = str(payload.get("tool_name") or "tool")
            tool_label = str(payload.get("tool_label") or tool_name)
            status = {
                "tool_call.started": "running",
                "tool_call.succeeded": "completed",
                "tool_call.failed": "failed",
            }[event_type]
            action = "activate_toolkit" if status == "running" else "deactivate_toolkit"
            drafts.append((action, {
                "agent_name": _worker_label(worker_name),
                "worker_name": worker_name,
                "process_task_id": step_id,
                "tool_call_id": tool_call_id,
                "toolkit_name": tool_label,
                "method_name": tool_name,
                "status": status,
                "message": tool_label,
            }))
        elif event_type == "task.step_changed":
            step_id = str(payload.get("step_id") or "")
            status = str(payload.get("status") or "queued")
            step = self.db.fetchone("SELECT * FROM task_steps WHERE id=?", (step_id,)) or {}
            worker_name = str(step.get("worker_name") or source)
            label = _worker_label(worker_name)
            common = {
                "agent_id": worker_name,
                "agent_name": label,
                "worker_name": worker_name,
                "process_task_id": step_id,
                "content": str(step.get("title") or ""),
            }
            if status == "running":
                drafts.extend([
                    ("create_agent", {**common, "agent_type": _worker_kind(worker_name), "tools": []}),
                    ("assign_task", {**common, "state": "WAITING", "failure_count": 0}),
                    ("activate_agent", {**common, "state": "RUNNING", "message": common["content"]}),
                ])
            else:
                state = {
                    "completed": "DONE", "failed": "FAILED", "blocked": "BLOCKED",
                    "waiting_approval": "WAITING_APPROVAL", "queued": "OPEN",
                }.get(status, status.upper())
                result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
                summary = str(result.get("summary") or step.get("title") or status)
                drafts.extend([
                    ("task_state", {**common, "task_id": step_id, "state": state, "result": summary, "summary": summary, "failure_count": 1 if status == "failed" else 0}),
                    ("deactivate_agent", {**common, "state": state, "message": summary, "tokens": 0}),
                ])
        elif event_type == "artifact.created":
            artifact = dict(payload.get("artifact") or {})
            drafts.append(("write_file", {
                "process_task_id": str(artifact.get("process_task_id") or artifact.get("metadata", {}).get("process_task_id") or artifact.get("metadata", {}).get("worker_task_id") or ""),
                "agent_name": _worker_label(str(artifact.get("worker_name") or source)),
                "worker_name": str(artifact.get("worker_name") or source),
                "artifact_id": str(artifact.get("id") or ""),
                "file_path": str(artifact.get("relative_path") or artifact.get("file_name") or ""),
                "file": artifact,
            }))
        elif event_type == "approval.requested":
            approval = dict(payload.get("approval") or {})
            drafts.append(("ask", {
                "question": str(approval.get("description") or approval.get("title") or "需要人工审批"),
                "agent": source,
                "approval": approval,
            }))
        elif event_type == "approval.decided":
            drafts.append(("human_response", {"approval": dict(payload.get("approval") or {})}))
        elif event_type in {"agent.model_completed", "agent.model_fallback"}:
            drafts.append(("activity", {
                "event_type": event_type,
                "worker_name": source,
                "process_task_id": str(payload.get("process_task_id") or ""),
                "message": "模型辅助处理已完成" if event_type.endswith("completed") else "模型辅助处理未采用，已使用确定性结果",
            }))
        elif event_type == "workflow.failed":
            drafts.append(("error", {"summary": str(payload.get("error") or "工作流执行失败"), "status": "failed"}))
        elif event_type == "task.status_changed":
            task = dict(payload.get("task") or {})
            status = str(task.get("status") or "")
            drafts.append(("task_state", {"task_id": task_id, "state": status.upper(), "result": "", "task": task}))
            if status in {"completed", "failed", "blocked", "cancelled"}:
                drafts.append(("error" if status == "failed" else "end", {"summary": str(task.get("error") or task.get("objective") or status), "status": status}))

        if not drafts:
            drafts.append(("activity", {
                "event_type": event_type,
                "worker_name": source,
                "process_task_id": str(payload.get("process_task_id") or ""),
                "message": str(payload.get("message") or payload.get("summary") or ""),
            }))
        return self.append_many(
            task_id, drafts, source_kind="platform_event",
            source_event_id=str(event["id"]), created_at=str(event.get("created_at") or ""),
        )

    def list_after(self, task_id: str, after: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.db.fetchall(
            """SELECT * FROM product_events WHERE task_id=? AND sequence>?
               ORDER BY sequence LIMIT ?""",
            (task_id, max(0, after), min(max(1, limit), 500)),
        )
        return [self._decode(row) for row in rows]

    def latest_sequence(self, task_id: str) -> int:
        row = self.db.fetchone(
            "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM product_events WHERE task_id=?",
            (task_id,),
        )
        return int((row or {}).get("sequence") or 0)

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        item["payload_json"] = json_loads(item.get("payload_json"), {})
        return item
