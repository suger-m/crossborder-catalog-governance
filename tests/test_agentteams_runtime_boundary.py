from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crossborder_cowork.app import create_api


ROOT = Path(__file__).resolve().parents[1]


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("CROSSBORDER_DISABLE_LLM", "1")
    monkeypatch.setenv("CROSSBORDER_AGENTTEAMS_MODE", "disabled")
    for name in ("configs", "examples", "migrations", "skills"):
        shutil.copytree(ROOT / name, tmp_path / name)
    return TestClient(create_api(tmp_path))


def test_web_api_keeps_agentteams_as_the_external_runtime_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(tmp_path, monkeypatch)
    app = client.app.state.crossborder_application

    health = client.get("/api/agentteams")
    assert health.status_code == 200
    payload = health.json()
    assert payload["runtime"] == "agentteams"
    assert payload["service"]["mode"] == "disabled"

    project = app.tasks.create_project("外部 AgentTeams 边界验证")
    material = app.materials.import_example(project["id"])[0]
    task = app.tasks.create_task(project["id"], "建立女装目录")
    app.materials.bind_task(task["id"], project["id"], [material["id"]])

    response = client.post(f"/api/tasks/{task['id']}/run")
    assert response.status_code == 503
    assert "agentteams" in response.json()["detail"].lower()
    assert app.tasks.get_task(task["id"])["status"] == "queued"
