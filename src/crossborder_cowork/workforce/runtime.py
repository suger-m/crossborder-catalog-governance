from __future__ import annotations

import json
from typing import Any

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.societies.workforce import FailureHandlingConfig, Workforce, WorkforceMode
from camel.societies.workforce.utils import RecoveryStrategy, TaskAnalysisResult
from camel.tasks import Task
from camel.tasks.task import TaskState

from ..util import utc_now
from .callback import CrossborderWorkforceCallback
from .worker import BusinessWorker


class CrossborderWorkforceRuntime:
    """Run a dynamic CAMEL task graph over the registered business roles."""

    def __init__(self, app: Any) -> None:
        self.app = app

    def run(self, task_id: str) -> dict[str, Any]:
        platform_task = self.app.tasks.get_task(task_id)
        self.app.tasks.update_status(task_id, "running", {"summary": "正在规划任务", "output_resource_ids": []})
        try:
            manifest = self.app.project_context.planner_manifest(task_id)
            planner_model = self.app.model_runtime.camel_model("planner")
            coordinator = ChatAgent(
                system_message=BaseMessage.make_assistant_message(
                    role_name="跨境目录 Workforce 协调器",
                    content=_COORDINATOR_PROMPT,
                ),
                model=planner_model,
            )
            task_agent = ChatAgent(
                system_message=BaseMessage.make_assistant_message(
                    role_name="跨境目录任务规划器",
                    content=_PLANNER_PROMPT,
                ),
                model=planner_model,
            )
            agents = (
                self.app.catalog_steward,
                self.app.compliance_specialist,
                self.app.listing_operations,
                self.app.governance_reviewer,
            )
            children = [BusinessWorker(self.app, task_id, agent) for agent in agents]
            callback = CrossborderWorkforceCallback(self.app, task_id)
            workforce = ResourceAwareWorkforce(
                app=self.app,
                platform_task_id=task_id,
                description=_workforce_description(agents),
                children=children,
                coordinator_agent=coordinator,
                task_agent=task_agent,
                default_model=planner_model,
                mode=WorkforceMode.AUTO_DECOMPOSE,
                callbacks=[callback],
                share_memory=False,
                failure_handling_config=FailureHandlingConfig(
                    max_retries=2,
                    enabled_strategies=["retry", "replan", "decompose", "reassign"],
                    halt_on_max_retries=True,
                ),
            )
            root = Task(
                id=task_id,
                content=_root_objective(platform_task["objective"], manifest),
                additional_info={
                    "project_id": platform_task["project_id"],
                    "selected_resource_ids": list(
                        (platform_task.get("input") or {}).get("selected_resource_ids")
                        or (platform_task.get("input") or {}).get("resource_ids")
                        or []
                    ),
                },
            )
            completed_root = workforce.process_task(root)
            return self._finish(task_id, completed_root)
        except Exception as exc:
            self.app.events.publish(task_id, "workforce.failed", "camel_workforce", {"error": str(exc)[:1000]})
            return self.app.tasks.update_status(
                task_id,
                "failed",
                {"summary": "Workforce 执行失败", "key_counts": {}, "output_resource_ids": []},
                str(exc),
            )

    def _finish(self, task_id: str, root: Task) -> dict[str, Any]:
        task = self.app.tasks.get_task(task_id)
        business_steps = [step for step in task["steps"] if step["worker_name"] != "workforce"]
        failed = [step for step in business_steps if step["status"] == "failed"]
        blocked = [step for step in business_steps if step["status"] == "blocked"]
        waiting = [step for step in business_steps if step["status"] == "waiting_approval"]
        resource_ids: list[str] = []
        for step in business_steps:
            for resource_id in (step.get("result") or {}).get("output_resource_ids", []):
                if resource_id not in resource_ids:
                    resource_ids.append(resource_id)
        if failed or root.state == TaskState.FAILED:
            status = "failed"
            summary = f"Workforce 执行失败，{len(failed)} 个 Agent 任务未完成"
        elif blocked:
            status = "blocked"
            summary = f"Workforce 已完成分析，{len(blocked)} 个 Agent 任务存在阻塞项"
        elif waiting:
            status = "waiting_approval"
            summary = f"Workforce 已完成分析，{len(waiting)} 个 Agent 任务等待人工确认"
        else:
            status = "completed"
            summary = f"Workforce 已完成 {len(business_steps)} 个 Agent 任务"
        result = {
            "summary": summary,
            "key_counts": {"agent_tasks": len(business_steps), "output_resources": len(resource_ids)},
            "output_resource_ids": resource_ids,
            "completed_at": utc_now(),
        }
        return self.app.tasks.update_status(task_id, status, result)


class ResourceAwareWorkforce(Workforce):
    """Evaluate compact Agent results through durable project resources."""

    def __init__(self, *, app: Any, platform_task_id: str, **kwargs: Any) -> None:
        self._app = app
        self._platform_task_id = platform_task_id
        super().__init__(**kwargs)

    def _analyze_task(
        self,
        task: Task,
        *,
        for_failure: bool,
        error_message: str | None = None,
    ) -> TaskAnalysisResult:
        if for_failure:
            return super()._analyze_task(
                task,
                for_failure=True,
                error_message=error_message,
            )
        try:
            self._validate_resource_result(task)
        except Exception as exc:
            return TaskAnalysisResult(
                reasoning="平台资源结果校验未通过。",
                recovery_strategy=RecoveryStrategy.RETRY,
                modified_task_content=task.content,
                quality_score=20,
                issues=[str(exc)[:500]],
            )
        return TaskAnalysisResult(
            reasoning="摘要、资源归属、步骤来源和持久化内容完整性均已通过平台校验。",
            quality_score=95,
        )

    def _validate_resource_result(self, task: Task) -> None:
        try:
            result = json.loads(task.result or "{}")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Agent 结果不是有效的紧凑 JSON") from exc
        if not isinstance(result, dict) or not str(result.get("summary") or "").strip():
            raise ValueError("Agent 结果缺少公开摘要")
        if result.get("status") not in {"completed", "waiting_approval", "blocked"}:
            raise ValueError("Agent 结果状态不可作为已完成资源结果")
        resource_ids = list(dict.fromkeys(
            str(item).strip()
            for item in result.get("output_resource_ids", [])
            if str(item).strip()
        ))
        if not resource_ids:
            raise ValueError("Agent 没有生成可验证的项目资源")
        platform_task = self._app.tasks.get_task(self._platform_task_id)
        for resource_id in resource_ids:
            resource = self._app.resources.get(resource_id, platform_task["project_id"])
            if resource["source_task_id"] != self._platform_task_id:
                raise ValueError(f"资源不属于当前 Workforce 任务: {resource_id}")
            if resource["source_step_id"] != task.id:
                raise ValueError(f"资源不属于当前 CAMEL 子任务: {resource_id}")
            if resource["storage_kind"] == "artifact":
                self._app.artifacts.validated_path(
                    str(resource["storage_ref"]),
                    platform_task["project_id"],
                )


def _root_objective(objective: str, manifest: dict[str, Any]) -> str:
    return (
        f"用户目标：\n{objective.strip()}\n\n"
        "项目资源清单（只含索引信息，Worker 必须按需通过项目上下文工具读取）：\n"
        f"{json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))}\n\n"
        "请仅创建完成目标所必需的 1 到 N 个子任务。已有资源足够时可只运行一个 Agent；"
        "不要固定运行全部 Agent，不要执行 Shopify 或 eBay 自动发布。"
    )


def _workforce_description(agents: tuple[Any, ...]) -> str:
    roles = "\n".join(f"- {agent.name}: {agent.description}" for agent in agents)
    return (
        "跨境女装商品目录治理 Workforce。仅可把任务分配给以下已注册业务 Agent，不得创建新 Worker：\n"
        f"{roles}\n"
        "根据目标和项目资源动态选择最少必要 Agent，并建立真实依赖；可以单 Agent 独立执行。"
    )


_COORDINATOR_PROMPT = """你负责协调跨境女装商品目录治理任务。只使用已注册的四个业务 Agent，
根据每个任务的职责和已有项目资源选择最少必要角色。允许单 Agent 任务。不得创建临时 Worker，
不得让 Agent 越权使用 Tool/Skill，不得自动发布 Shopify 或 eBay 商品。"""

_PLANNER_PROMPT = """把用户目标分解为动态的 1 到 N 个业务任务。已有项目资源可以跨任务复用，
不要为了形式固定生成四步流程。任务描述应说明业务结果和需要读取的资源类型，不要在任务文本中复制完整数据。
只有真实数据依赖才建立依赖边。第一版只生成草稿、审核和导出包，绝不创建自动发布任务。"""
