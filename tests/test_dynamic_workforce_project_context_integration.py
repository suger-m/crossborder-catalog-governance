from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from camel.societies.workforce.events import (
    TaskAssignedEvent,
    TaskCompletedEvent,
    TaskCreatedEvent,
    TaskDecomposedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
)
from camel.tasks import Task
from camel.tasks.task import TaskState
from fastapi.testclient import TestClient

from crossborder_cowork.app import create_api
from crossborder_cowork.export.verification import verify_listing_package
from crossborder_cowork.workforce.callback import CrossborderWorkforceCallback
from crossborder_cowork.workforce.worker import BusinessWorker


ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CROSSBORDER_DISABLE_LLM", "1")
    for name in ("configs", "examples", "migrations", "skills"):
        shutil.copytree(ROOT / name, tmp_path / name)
    return TestClient(create_api(tmp_path))


def _create_task_with_example(app: Any, project_id: str, objective: str) -> dict[str, Any]:
    material = app.materials.import_example(project_id)[0]
    task = app.tasks.create_task(project_id, objective)
    app.materials.bind_task(task["id"], project_id, [material["id"]])
    app.tasks.update_input(task["id"], {
        "material_ids": [material["id"]],
        "source_paths": app.materials.task_paths(task["id"]),
    })
    return app.tasks.get_task(task["id"])


def _run_graph(
    app: Any,
    platform_task: dict[str, Any],
    specs: list[tuple[str, Any, str, tuple[str, ...]]],
) -> dict[str, Task]:
    callback = CrossborderWorkforceCallback(app, platform_task["id"])
    camel_tasks = {
        step_id: Task(id=step_id, content=content)
        for step_id, _, content, _ in specs
    }
    for step_id, _, content, _ in specs:
        callback.log_task_created(TaskCreatedEvent(
            task_id=step_id,
            description=content,
            parent_task_id=platform_task["id"],
        ))
    callback.log_task_decomposed(TaskDecomposedEvent(
        parent_task_id=platform_task["id"],
        subtask_ids=[step_id for step_id, _, _, _ in specs],
    ))
    app.tasks.update_status(
        platform_task["id"], "running",
        {"summary": "Workforce 正在执行动态任务", "output_resource_ids": []},
    )

    for step_id, agent, _, dependency_ids in specs:
        dependencies = [camel_tasks[dependency_id] for dependency_id in dependency_ids]
        camel_task = camel_tasks[step_id]
        camel_task.dependencies = dependencies
        callback.log_task_assigned(TaskAssignedEvent(
            task_id=step_id,
            worker_id=agent.name,
            dependencies=list(dependency_ids),
        ))
        callback.log_task_started(TaskStartedEvent(task_id=step_id, worker_id=agent.name))
        state = asyncio.run(
            BusinessWorker(app, platform_task["id"], agent)._process_task(camel_task, dependencies)
        )
        camel_task.state = state
        if state == TaskState.FAILED:
            callback.log_task_failed(TaskFailedEvent(
                task_id=step_id,
                worker_id=agent.name,
                error_message=camel_task.result or "Agent execution failed",
            ))
        else:
            callback.log_task_completed(TaskCompletedEvent(
                task_id=step_id,
                worker_id=agent.name,
                parent_task_id=platform_task["id"],
                result_summary=camel_task.result,
            ))
    root = Task(id=platform_task["id"], content=platform_task["objective"], state=TaskState.DONE)
    app.workflow.runtime._finish(platform_task["id"], root)
    return camel_tasks


def _full_delivery(app: Any, task: dict[str, Any]) -> dict[str, Task]:
    prefix = task["id"]
    return _run_graph(app, task, [
        (f"{prefix}.catalog", app.catalog_steward, "建立规范商品与 SKU 事实", ()),
        (f"{prefix}.compliance", app.compliance_specialist, "检查美国女装合规和平台政策", (f"{prefix}.catalog",)),
        (f"{prefix}.shopify", app.listing_operations, "只生成 Shopify 美国站草稿", (f"{prefix}.catalog", f"{prefix}.compliance")),
        (f"{prefix}.ebay", app.listing_operations, "只生成 eBay 美国站草稿", (f"{prefix}.catalog", f"{prefix}.compliance")),
        (
            f"{prefix}.governance",
            app.governance_reviewer,
            "审核交付一致性并生成目录包",
            (f"{prefix}.compliance", f"{prefix}.shopify", f"{prefix}.ebay"),
        ),
    ])


def _payloads(app: Any, task_id: str, action: str) -> list[dict[str, Any]]:
    return [
        event["payload_json"]
        for event in app.product_events.list_after(task_id, limit=500)
        if event["action"] == action
    ]


def test_dynamic_workforce_resources_events_and_artifact_previews(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    app = client.app.state.crossborder_application
    project = app.tasks.create_project("美国女装目录治理")
    task = _create_task_with_example(
        app,
        project["id"],
        "治理女装目录并生成 Shopify 与 eBay 美国站交付包",
    )

    dynamic = _full_delivery(app, task)
    final = app.tasks.get_task(task["id"])
    assert final["status"] == "completed"
    assert [step["id"] for step in final["steps"]] == list(dynamic)
    assert all(step["status"] == "completed" for step in final["steps"])
    assert final["result"]["key_counts"]["agent_tasks"] == 5

    assignments = {item["task_id"]: item for item in _payloads(app, task["id"], "assign_task")}
    activations = {item["process_task_id"]: item for item in _payloads(app, task["id"], "activate_agent")}
    completions = {
        item["task_id"]: item
        for item in _payloads(app, task["id"], "task_state")
        if item.get("task_id") in dynamic and item.get("state") in {"DONE", "BLOCKED", "WAITING_APPROVAL"}
    }
    files = _payloads(app, task["id"], "write_file")
    tools = [
        *_payloads(app, task["id"], "activate_toolkit"),
        *_payloads(app, task["id"], "deactivate_toolkit"),
    ]
    assert set(assignments) == set(dynamic)
    assert set(activations) == set(dynamic)
    assert set(completions) == set(dynamic)
    assert files and tools
    assert all(item["process_task_id"] in dynamic for item in files)
    assert all(item["process_task_id"] in dynamic for item in tools)
    for process_task_id in dynamic:
        assert assignments[process_task_id]["task_id"] == process_task_id
        assert activations[process_task_id]["process_task_id"] == process_task_id
        assert completions[process_task_id]["task_id"] == process_task_id
    for item in tools:
        assert set(item).isdisjoint({
            "duration", "duration_ms", "arguments", "args", "result", "raw_result", "stack_trace",
        })
        assert item["status"] in {"running", "completed", "failed"}
        assert item["tool_call_id"]

    for step in final["steps"]:
        result = step["result"]
        assert set(result) == {"summary", "key_counts", "output_resource_ids", "status"}
        serialized = json.dumps(result, ensure_ascii=False)
        assert "fiber_content" not in serialized
        assert "itemSpecifics" not in serialized

    artifacts = app.artifacts.list_project(project["id"])
    markdown = [item for item in artifacts if item["mime_type"] == "text/markdown"]
    assert {item["artifact_type"] for item in markdown} >= {
        "us_compliance_report", "catalog_consistency_report",
    }
    previews = [client.get(f"/api/artifacts/{item['id']}/preview") for item in markdown]
    assert all(response.status_code == 200 for response in previews)
    preview_payloads = [response.json() for response in previews]
    assert {item["artifact"]["id"] for item in preview_payloads} == {item["id"] for item in markdown}
    assert len({item["content"] for item in preview_payloads}) == len(preview_payloads)

    package = next(item for item in artifacts if item["artifact_type"] == "listing_package")
    verified = verify_listing_package(Path(package["absolute_path"]))
    assert verified["member_count"] >= 6

    ebay_resource = next(
        item for item in app.resources.list(project["id"], resource_types=("listing_draft",), statuses=("active",))
        if item["logical_key"] == "ebay_us"
    )
    review_task = app.tasks.create_task(
        project["id"],
        "审核已有 eBay 草稿",
        input_data={"selected_resource_ids": [ebay_resource["id"]]},
    )
    _run_graph(app, review_task, [
        (
            f"{review_task['id']}.governance",
            app.governance_reviewer,
            "审核已有 eBay 草稿，不要执行 Shopify 或 eBay 自动发布。",
            (),
        ),
    ])
    review_final = app.tasks.get_task(review_task["id"])
    assert review_final["status"] == "completed"
    assert [step["worker_name"] for step in review_final["steps"]] == ["governance_reviewer_agent"]
    review_resources = app.resources.list(project["id"], source_task_id=review_task["id"])
    assert review_resources
    assert all(item["owner_worker_name"] == "governance_reviewer_agent" for item in review_resources)
    assert {item["resource_type"] for item in review_resources}.isdisjoint({"listing_package", "sku_matrix"})

    other_project = app.tasks.create_project("隔离项目")
    other_task = _create_task_with_example(app, other_project["id"], "建立同 SKU 的独立目录并生成草稿")
    _run_graph(app, other_task, [
        (f"{other_task['id']}.catalog", app.catalog_steward, "建立规范商品与 SKU 事实", ()),
        (
            f"{other_task['id']}.listing",
            app.listing_operations,
            "生成 Shopify 与 eBay 美国站草稿",
            (f"{other_task['id']}.catalog",),
        ),
    ])
    left_products = {item["id"] for item in app.graph.list_products(project_id=project["id"])}
    right_products = {item["id"] for item in app.graph.list_products(project_id=other_project["id"])}
    left_listings = {item["id"] for item in app.graph.list_listings(project["id"])}
    right_listings = {item["id"] for item in app.graph.list_listings(other_project["id"])}
    left_artifacts = {item["id"] for item in app.artifacts.list_project(project["id"])}
    right_artifacts = {item["id"] for item in app.artifacts.list_project(other_project["id"])}
    left_resources = {item["id"] for item in app.resources.list(project["id"])}
    right_resources = {item["id"] for item in app.resources.list(other_project["id"])}
    assert left_products.isdisjoint(right_products)
    assert left_listings.isdisjoint(right_listings)
    assert left_artifacts.isdisjoint(right_artifacts)
    assert left_resources.isdisjoint(right_resources)
    with pytest.raises(ValueError, match="does not belong"):
        app.artifacts.get(next(iter(left_artifacts)), other_project["id"])
