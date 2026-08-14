from __future__ import annotations

import json
import runpy
import shutil
from pathlib import Path

from crossborder_cowork import build_application
from crossborder_cowork.export.verification import verify_listing_package
from crossborder_cowork.governance.import_validation import validate_ebay_draft, validate_shopify_draft
from crossborder_cowork.platforms.base import ListingDraft
from crossborder_cowork.util import sha256_file


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_BUILDER = ROOT / "tests" / "fixtures" / "womenswear-us-realistic" / "build_fixture.py"


def test_production_realistic_multifile_acceptance(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CROSSBORDER_DISABLE_LLM", "1")
    for name in ("configs", "migrations", "skills"):
        shutil.copytree(ROOT / name, tmp_path / name)
    build_fixture = runpy.run_path(str(FIXTURE_BUILDER))["build_fixture"]
    source_paths = build_fixture(tmp_path / "supplier-bundle")

    app = build_application(tmp_path)
    project = app.tasks.create_project("Public Womenswear US Acceptance")
    task = app.tasks.create_task(
        project["id"],
        "Validate public womenswear product data enriched with supplier files for US, Shopify, and eBay US.",
        {"source_paths": [str(path) for path in source_paths]},
        app.workflow.DEFAULT_STEPS,
    )

    first = app.workflow.run_task(task["id"])
    assert first["status"] == "blocked"
    approvals = app.approvals.list(task["id"])
    origin = next(
        item for item in approvals
        if item["approval_type"] == "catalog_conflict" and item["payload"]["field_name"] == "country_of_origin"
    )
    missing_fiber = next(
        item for item in approvals
        if item["approval_type"] == "missing_required_fact" and item["payload"]["field_name"] == "fiber_content"
    )
    assert set(origin["payload"]["values"]) == {"China", "Vietnam"}

    second = app.workflow.approve_and_rerun(origin["id"], {"selected_value": "China"})
    assert second["status"] == "blocked"
    final = app.workflow.approve_and_rerun(missing_fiber["id"], {"selected_value": "70% Wool, 30% Nylon"})
    assert final["status"] == "completed"
    assert final["result"]["governance"]["decision"]["ready_for_export"] is True

    products = {item["data"]["external_id"]: item["data"] for item in app.graph.list_products(task["id"])}
    assert set(products) == {"CC0-DRESS-100", "SUPPLIER-KNIT-200"}
    dress = products["CC0-DRESS-100"]
    jumper = products["SUPPLIER-KNIT-200"]
    assert len(dress["skus"]) == 6
    assert len(jumper["skus"]) == 4
    assert all("-NA-NA" not in sku["external_id"] for product in products.values() for sku in product["skus"])
    assert {sku["price"] for sku in dress["skus"]} == {"79.90"}
    assert {sku["inventory"] for sku in dress["skus"]} >= {1200}
    assert {sku["price"] for sku in jumper["skus"]} == {"49.50"}
    assert {sku["inventory"] for sku in jumper["skus"]} == {25}
    assert dress["country_of_origin"] == "China"
    assert jumper["country_of_origin"] == "Vietnam"
    assert jumper["fiber_content"] == "70% Wool, 30% Nylon"
    human_facts = [
        fact for fact in jumper["facts"]
        if fact["field_name"] == "fiber_content" and fact["evidence"]["source_document_id"].startswith("human_approval:")
    ]
    assert len(human_facts) == 1
    assert dress["version"] == 2 and jumper["version"] == 2

    artifacts = app.artifacts.list(task["id"])
    source_artifacts = [item for item in artifacts if item["artifact_type"] == "source_document"]
    assert len(source_artifacts) == 4
    expected_sources = {path.name: sha256_file(path) for path in source_paths}
    for artifact in source_artifacts:
        digest, size = expected_sources[artifact["title"]]
        assert artifact["sha256"] == digest
        assert artifact["size_bytes"] == size
    source_manifest_artifact = [item for item in artifacts if item["artifact_type"] == "source_manifest"][-1]
    source_manifest = json.loads(Path(source_manifest_artifact["absolute_path"]).read_text(encoding="utf-8"))
    assert {item["file_name"] for item in source_manifest["sources"]} == set(expected_sources)
    assert len(source_manifest["artifact_ids"]) == 4

    listing = final["result"]["listing"]
    shopify = [ListingDraft.model_validate(item) for item in listing["shopify"]]
    ebay = [ListingDraft.model_validate(item) for item in listing["ebay"]]
    assert not [issue for draft in shopify for issue in validate_shopify_draft(draft)]
    assert not [issue for draft in ebay for issue in validate_ebay_draft(draft)]
    for left, right in zip(shopify, ebay):
        shopify_rows = left.data["rows"]
        ebay_variations = right.data["variations"]
        assert {row["Variant SKU"] for row in shopify_rows} == {item["sku"] for item in ebay_variations}
        assert {row["Variant Price"] for row in shopify_rows} == {item["price"] for item in ebay_variations}
        assert {row["Option1 Value"] for row in shopify_rows} == {item["specifics"]["Size"] for item in ebay_variations}
        assert {row["Option2 Value"] for row in shopify_rows} == {item["specifics"]["Color"] for item in ebay_variations}

    package = Path(final["result"]["governance"]["package"]["absolute_path"])
    verified = verify_listing_package(package)
    assert verified["member_count"] >= 8
    exported_text = "\n".join(
        Path(item["absolute_path"]).read_text(encoding="utf-8", errors="ignore")
        for item in artifacts if item["mime_type"].startswith("text/") or item["mime_type"] == "application/json"
    ).casefold()
    for forbidden in ("api_key", "access_token", "client_secret", '"status":"published"'):
        assert forbidden not in exported_text
