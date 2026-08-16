from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, List, Optional

from camel.agents import ChatAgent
from camel.agents.chat_agent import ChatAgentResponse
from camel.societies.workforce.single_agent_worker import SingleAgentWorker
from camel.tasks import Task
from camel.tasks.task import TaskState

from ..platform.execution_context import ExecutionContext, use_execution_context


class BusinessAgentWorker(SingleAgentWorker):
    """Eigent-style ChatAgent worker with project execution identity."""

    def __init__(
        self,
        app: Any,
        platform_task_id: str,
        worker_name: str,
        description: str,
        worker: ChatAgent,
    ) -> None:
        super().__init__(
            description=description,
            worker=worker,
            use_agent_pool=False,
            use_structured_output_handler=True,
        )
        self.app = app
        self.platform_task_id = platform_task_id
        self.worker_name = worker_name

    async def _process_task(
        self,
        task: Task,
        dependencies: List[Task],
        stream_callback: Optional[
            Callable[[ChatAgentResponse], Optional[Awaitable[None]]]
        ] = None,
    ) -> TaskState:
        platform_task = self.app.tasks.get_task(self.platform_task_id)
        context = ExecutionContext(
            task_id=self.platform_task_id,
            project_id=platform_task["project_id"],
            process_task_id=task.id,
            worker_name=self.worker_name,
        )
        with use_execution_context(context):
            state = await super()._process_task(task, dependencies, stream_callback)
        if state == TaskState.FAILED:
            compact = {
                "summary": str(task.result or "Agent 执行失败")[:1000],
                "key_counts": {}, "output_resource_ids": [], "status": "failed",
            }
        else:
            try:
                compact = self._parse_compact(task.result)
                self._validate_resources(compact, context)
            except Exception as exc:
                compact = {
                    "summary": f"业务 Agent 结果校验失败：{str(exc)[:800]}",
                    "key_counts": {},
                    "output_resource_ids": [],
                    "status": "failed",
                }
        task.result = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        self.app.tasks.update_step(task.id, compact["status"], compact, emit_event=False)
        return TaskState.FAILED if compact["status"] == "failed" else TaskState.DONE

    @staticmethod
    def _parse_compact(raw: Any) -> dict[str, Any]:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = text.strip("`").removeprefix("json").strip()
        payload = json.loads(text)
        if not isinstance(payload, dict) or not str(payload.get("summary") or "").strip():
            raise ValueError("业务 Agent 未返回有效紧凑结果")
        status = str(payload.get("status") or "completed").lower()
        if status not in {"completed", "waiting_approval", "blocked", "failed"}:
            raise ValueError(f"无效业务 Agent 状态: {status}")
        return {
            "summary": str(payload["summary"])[:1000],
            "key_counts": payload.get("key_counts") if isinstance(payload.get("key_counts"), dict) else {},
            "output_resource_ids": list(dict.fromkeys(
                str(item) for item in payload.get("output_resource_ids", []) if str(item).strip()
            )),
            "status": status,
        }

    def _validate_resources(self, compact: dict[str, Any], context: ExecutionContext) -> None:
        if not compact["output_resource_ids"]:
            raise ValueError("业务 Agent 没有生成项目资源")
        for resource_id in compact["output_resource_ids"]:
            resource = self.app.resources.get(resource_id, context.project_id)
            if resource["source_task_id"] != context.task_id:
                raise ValueError("业务 Agent 资源不属于当前任务")
            if resource["source_step_id"] != context.process_task_id:
                raise ValueError("业务 Agent 资源不属于当前 CAMEL 子任务")
