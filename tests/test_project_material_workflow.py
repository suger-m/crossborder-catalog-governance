from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from crossborder_cowork.app import _sse_json, create_api


ROOT = Path(__file__).resolve().parents[1]


def test_sse_payload_is_single_line_json() -> None:
    payload = _sse_json({"action": "task_state", "payload_json": {"message": "第一行\n第二行"}})
    assert "\n" not in payload
    assert "第一行\\n第二行" in payload


def build_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("CROSSBORDER_DISABLE_LLM", "1")
    for name in ("configs", "examples", "migrations", "skills"):
        shutil.copytree(ROOT / name, tmp_path / name)
    return TestClient(create_api(tmp_path))


def test_project_materials_are_explicit_reusable_task_inputs(tmp_path: Path, monkeypatch) -> None:
    client = build_client(tmp_path, monkeypatch)
    project = client.post("/api/projects", json={"name": "美国女装目录"}).json()["project"]

    assert client.get(f"/api/tasks?project_id={project['id']}").json()["items"] == []
    assert client.get(f"/api/projects/{project['id']}/materials").json()["items"] == []

    first_import = client.post(f"/api/projects/{project['id']}/materials/import-example")
    assert first_import.status_code == 201
    material = first_import.json()["items"][0]
    second_import = client.post(f"/api/projects/{project['id']}/materials/import-example")
    assert second_import.status_code == 201
    assert second_import.json()["items"][0]["id"] == material["id"]
    assert len(client.get(f"/api/projects/{project['id']}/materials").json()["items"]) == 1

    other_project = client.post("/api/projects", json={"name": "另一个项目"}).json()["project"]
    cross_project = client.post(
        "/api/tasks",
        json={"project_id": other_project["id"], "objective": "错误绑定", "material_ids": [material["id"]]},
    )
    assert cross_project.status_code == 422

    created = client.post(
        "/api/tasks",
        json={"project_id": project["id"], "objective": "生成美国站目录治理包", "material_ids": [material["id"]]},
    )
    assert created.status_code == 201
    task = created.json()["task"]
    assert task["input"]["material_ids"] == [material["id"]]
    assert len(task["input"]["source_paths"]) == 1

    unbound_response = client.post(
        "/api/tasks",
        json={"project_id": other_project["id"], "objective": "审核已有项目资源", "material_ids": []},
    )
    assert unbound_response.status_code == 201
    unbound = unbound_response.json()["task"]
    assert unbound["steps"] == []

    application = client.app.state.crossborder_application
    rejected = client.post(f"/api/tasks/{unbound['id']}/run")
    assert rejected.status_code == 409
    assert application.tasks.get_task(unbound["id"])["status"] == "queued"


def test_uploaded_chinese_filename_is_preserved(tmp_path: Path, monkeypatch) -> None:
    client = build_client(tmp_path, monkeypatch)
    project = client.post("/api/projects", json={"name": "中文素材"}).json()["project"]
    content = (ROOT / "examples" / "womenswear-us" / "womenswear-catalog.csv").read_bytes()

    response = client.post(
        f"/api/projects/{project['id']}/materials",
        files=[("files", ("女装商品目录.csv", content, "text/csv"))],
    )

    assert response.status_code == 201
    material = response.json()["items"][0]
    assert material["file_name"] == "女装商品目录.csv"
    assert client.get(f"/api/project-materials/{material['id']}/download").content == content
