from __future__ import annotations

"""Small stateless MCP HTTP bridge for the real AgentTeams Workers.

The bridge is a platform capability, not another Worker runtime.  AgentTeams
Workers call the role-scoped endpoint; each call is bound to a persisted
cross-border task context before an existing deterministic toolkit runs.
"""

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from ..agent.toolkits import (
    CatalogToolkit,
    ComplianceToolkit,
    GovernanceToolkit,
    ListingToolkit,
    ProjectContextToolkit,
)
from ..platform.execution_context import ExecutionContext, use_execution_context


ROLE_SKILLS: dict[str, tuple[str, ...]] = {
    "catalog_steward_agent": ("product-catalog", "womenswear-classification"),
    "compliance_specialist_agent": ("us-apparel-compliance", "shopify-product-policy", "ebay-us-fashion-policy"),
    "listing_operations_agent": ("product-localization-en-us", "shopify-listing", "ebay-us-listing"),
    "governance_reviewer_agent": ("catalog-governance",),
}


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Awaitable[Any]]

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "inputSchema": self.input_schema}


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


def _task_properties() -> dict[str, Any]:
    return {
        "task_id": {"type": "string", "description": "本项目任务 ID。"},
        "process_task_id": {"type": "string", "description": "AgentTeams 当前子任务 ID；没有子任务时使用 task_id。"},
    }


def _context(application: Any, role: str, args: dict[str, Any]) -> ExecutionContext:
    task_id = str(args.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("task_id is required")
    task = application.tasks.get_task(task_id)
    external_process_task_id = str(args.get("process_task_id") or task_id).strip()
    process_task_id = task_id
    if external_process_task_id != task_id:
        existing = application.tasks.get_step_by_external_id(task_id, external_process_task_id)
        if existing is None:
            existing = application.tasks.assign_workforce_step(task_id, external_process_task_id, role)
        if str(existing.get("worker_name") or "") != role:
            raise ValueError("process_task_id is assigned to another business role")
    return ExecutionContext(
        task_id=task_id,
        project_id=str(task["project_id"]),
        process_task_id=process_task_id,
        worker_name=role,
    )


def _with_context(application: Any, role: str, fn: Callable[..., Awaitable[Any]]) -> Callable[[dict[str, Any]], Awaitable[Any]]:
    async def call(args: dict[str, Any]) -> Any:
        context = _context(application, role, args)
        payload = dict(args)
        payload.pop("task_id", None)
        payload.pop("process_task_id", None)
        with use_execution_context(context):
            return await fn(context, payload)
    return call


def _tools_for(application: Any, role: str) -> list[MCPTool]:
    project = ProjectContextToolkit(application, role)
    skill_toolkit = application.skills.toolkit(role, ROLE_SKILLS.get(role, ()))

    async def get_context(args: dict[str, Any]) -> Any:
        external_process_task_id = str(args.get("process_task_id") or "")
        local_process_task_id = ""
        if external_process_task_id:
            local_process_task_id = application.tasks.resolve_step_id(args["task_id"], external_process_task_id) or ""
        return application.task_contexts.snapshot_for_task(
            args["task_id"],
            worker_id=role,
            process_task_id=local_process_task_id,
            external_process_task_id=external_process_task_id,
        )

    async def list_skills(args: dict[str, Any]) -> Any:
        del args
        allowed = set(ROLE_SKILLS.get(role, ()))
        return [item.__dict__ for item in application.skills.discover() if item.name in allowed or item.path.parent.name in allowed]

    async def load_skill(args: dict[str, Any]) -> Any:
        return await skill_toolkit.load_skill(str(args.get("name") or ""))

    async def read_skill_resource(args: dict[str, Any]) -> Any:
        return await skill_toolkit.read_skill_resource(
            str(args.get("name") or ""),
            str(args.get("relative_path") or "SKILL.md"),
            int(args.get("offset") or 0),
            int(args.get("limit") or 16_384),
        )

    async def project_resources(context: Any, args: dict[str, Any]) -> Any:
        return await project.list_project_resources(
            resource_types=args.get("resource_types"), statuses=args.get("statuses"), limit=int(args.get("limit") or 200),
        )

    async def inspect_materials(context: Any, args: dict[str, Any]) -> Any:
        del context, args
        return await project.inspect_task_materials()

    async def summarize_products(context: Any, args: dict[str, Any]) -> Any:
        del context
        return await project.summarize_canonical_products(args.get("resource_ids"), int(args.get("limit") or 100))

    async def summarize_listings(context: Any, args: dict[str, Any]) -> Any:
        del context
        return await project.summarize_listing_drafts(args.get("platforms"), args.get("resource_ids"), int(args.get("limit") or 100))

    async def read_artifact(context: Any, args: dict[str, Any]) -> Any:
        del context
        return await project.read_artifact_text(
            str(args.get("artifact_id") or ""), str(args.get("resource_id") or ""), int(args.get("offset") or 0), int(args.get("limit") or 16_384),
        )

    async def pending_approvals(context: Any, args: dict[str, Any]) -> Any:
        del context, args
        return await project.list_pending_approvals()

    async def catalog(context: Any, args: dict[str, Any]) -> Any:
        del context, args
        return await CatalogToolkit(application, role).build_canonical_catalog()

    async def compliance(context: Any, args: dict[str, Any]) -> Any:
        del context
        return await ComplianceToolkit(application, role).evaluate_us_apparel_compliance(args.get("product_resource_ids"))

    async def listings(context: Any, args: dict[str, Any]) -> Any:
        del context
        return await ListingToolkit(application, role).create_listing_drafts(args.get("platforms") or ["shopify", "ebay_us"], args.get("product_resource_ids"))

    async def governance(context: Any, args: dict[str, Any]) -> Any:
        del context
        return await GovernanceToolkit(application, role).review_catalog_release(
            bool(args.get("create_export_package")),
            args.get("product_resource_ids"), args.get("compliance_resource_ids"), args.get("listing_resource_ids"),
        )

    tools: list[MCPTool] = [
        MCPTool("get_task_context", "读取当前任务的持久化上下文、依赖和 Artifact 清单。", _schema(_task_properties(), ["task_id"]), get_context),
        MCPTool("list_skills", "列出当前业务角色允许发现的 Skill。", _schema(_task_properties(), ["task_id"]), _with_context(application, role, lambda context, args: list_skills({"task_id": context.task_id, **args}))),
        MCPTool("load_skill", "按需加载一个允许的 Skill。", _schema({**_task_properties(), "name": {"type": "string"}}, ["task_id", "name"]), _with_context(application, role, lambda context, args: load_skill({"task_id": context.task_id, **args}))),
        MCPTool("read_skill_resource", "分页读取当前 Skill 包内的文本资源。", _schema({**_task_properties(), "name": {"type": "string"}, "relative_path": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 65536}}, ["task_id", "name", "relative_path"]), _with_context(application, role, lambda context, args: read_skill_resource({"task_id": context.task_id, **args}))),
        MCPTool("list_project_resources", "查看项目资源摘要，不读取大文件正文。", _schema({**_task_properties(), "resource_types": {"type": "array", "items": {"type": "string"}}, "statuses": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer", "minimum": 1, "maximum": 200}}, ["task_id"]), _with_context(application, role, project_resources)),
        MCPTool("inspect_task_materials", "查看当前任务绑定素材的元数据。", _schema(_task_properties(), ["task_id"]), _with_context(application, role, inspect_materials)),
        MCPTool("summarize_canonical_products", "读取规范商品和 SKU 的紧凑摘要。", _schema({**_task_properties(), "resource_ids": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer", "minimum": 1, "maximum": 200}}, ["task_id"]), _with_context(application, role, summarize_products)),
        MCPTool("summarize_listing_drafts", "读取 Shopify/eBay 草稿摘要。", _schema({**_task_properties(), "platforms": {"type": "array", "items": {"type": "string"}}, "resource_ids": {"type": "array", "items": {"type": "string"}}, "limit": {"type": "integer", "minimum": 1, "maximum": 200}}, ["task_id"]), _with_context(application, role, summarize_listings)),
        MCPTool("read_artifact_text", "分页读取已校验的文本 Artifact。", _schema({**_task_properties(), "artifact_id": {"type": "string"}, "resource_id": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 65536}}, ["task_id"]), _with_context(application, role, read_artifact)),
        MCPTool("list_pending_approvals", "查看当前任务待处理的人工审批。", _schema(_task_properties(), ["task_id"]), _with_context(application, role, pending_approvals)),
    ]
    if role == "catalog_steward_agent":
        tools.append(MCPTool("build_canonical_catalog", "解析素材并建立规范 Product/SKU 事实。", _schema(_task_properties(), ["task_id"]), _with_context(application, role, catalog)))
    if role == "compliance_specialist_agent":
        tools.append(MCPTool("evaluate_us_apparel_compliance", "执行美国服装、Shopify 和 eBay US 合规检查。", _schema({**_task_properties(), "product_resource_ids": {"type": "array", "items": {"type": "string"}}}, ["task_id"]), _with_context(application, role, compliance)))
    if role == "listing_operations_agent":
        tools.append(MCPTool("create_listing_drafts", "基于规范事实生成 Shopify/eBay US 草稿，不发布商品。", _schema({**_task_properties(), "platforms": {"type": "array", "items": {"type": "string"}}, "product_resource_ids": {"type": "array", "items": {"type": "string"}}}, ["task_id", "platforms"]), _with_context(application, role, listings)))
    if role == "governance_reviewer_agent":
        tools.append(MCPTool("review_catalog_release", "审核事实、合规、草稿、审批和导出就绪状态。", _schema({**_task_properties(), "create_export_package": {"type": "boolean"}, "product_resource_ids": {"type": "array", "items": {"type": "string"}}, "compliance_resource_ids": {"type": "array", "items": {"type": "string"}}, "listing_resource_ids": {"type": "array", "items": {"type": "string"}}}, ["task_id"]), _with_context(application, role, governance)))
    return tools


def mount_crossborder_mcp(api: FastAPI, application: Any) -> None:
    tools_by_role = {role: _tools_for(application, role) for role in ROLE_SKILLS}

    @api.post("/mcp/{role}")
    async def mcp_endpoint(role: str, request: Request) -> Response:
        tools = tools_by_role.get(role)
        if tools is None:
            return JSONResponse({"error": "unknown_agent_role"}, status_code=404)
        payload = await request.json()
        requests = payload if isinstance(payload, list) else [payload]
        responses: list[dict[str, Any]] = []
        for item in requests:
            if not isinstance(item, dict):
                continue
            method = str(item.get("method") or "")
            request_id = item.get("id")
            if method.startswith("notifications/"):
                continue
            if method == "initialize":
                result = {
                    "protocolVersion": str((item.get("params") or {}).get("protocolVersion") or "2025-03-26"),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "crossborder-catalog-governance", "version": "0.1.0"},
                }
            elif method == "tools/list":
                result = {"tools": [tool.schema() for tool in tools]}
            elif method == "tools/call":
                params = item.get("params") or {}
                name = str(params.get("name") or "")
                tool = next((candidate for candidate in tools if candidate.name == name), None)
                if tool is None:
                    result = {"content": [{"type": "text", "text": json.dumps({"error": "unknown_tool", "tool": name}, ensure_ascii=False)}], "isError": True}
                else:
                    try:
                        value = await tool.handler(dict(params.get("arguments") or {}))
                        result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}], "isError": False}
                    except Exception as error:
                        result = {"content": [{"type": "text", "text": json.dumps({"error": str(error)[:1000]}, ensure_ascii=False)}], "isError": True}
            else:
                result = {"error": {"code": -32601, "message": f"Method not found: {method}"}}
            responses.append({"jsonrpc": "2.0", "id": request_id, "result": result})
        if isinstance(payload, list):
            return JSONResponse(responses)
        return JSONResponse(responses[0] if responses else {})
