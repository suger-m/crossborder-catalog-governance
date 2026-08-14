from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from crossborder_cowork import build_application


ROOT = Path(__file__).resolve().parents[1]


def test_complete_womenswear_catalog_to_listing_package(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CROSSBORDER_DISABLE_LLM", "1")
    for name in ("configs", "migrations", "skills"):
        shutil.copytree(ROOT / name, tmp_path / name)
    fixture = ROOT / "tests" / "fixtures" / "womenswear-us" / "catalog.csv"
    app = build_application(tmp_path)
    project = app.tasks.create_project("US Womenswear Launch")
    task = app.tasks.create_task(
        project["id"],
        "Govern the supplied womenswear catalog for the United States, Shopify, and eBay US.",
        {"source_paths": [str(fixture)]},
        app.workflow.DEFAULT_STEPS,
    )

    first = app.workflow.run_task(task["id"])
    assert first["status"] == "blocked"
    approvals = app.approvals.list(task["id"])
    conflict = next(item for item in approvals if item["approval_type"] == "catalog_conflict")
    missing_fiber = next(
        item for item in approvals
        if item["approval_type"] == "missing_required_fact" and item["payload"]["field_name"] == "fiber_content"
    )
    assert conflict["status"] == "pending"
    assert missing_fiber["status"] == "pending"

    second = app.workflow.approve_and_rerun(conflict["id"], {"selected_value": "China"})
    assert second["status"] == "blocked"
    final = app.workflow.approve_and_rerun(missing_fiber["id"], {"selected_value": "100% Cotton"})
    assert final["status"] == "completed"
    assert final["result"]["governance"]["decision"]["status"] == "approved"

    products = [item["data"] for item in app.graph.list_products()]
    assert len(products) == 2
    dress = next(item for item in products if item["external_id"] == "CB-DR-001")
    tshirt = next(item for item in products if item["external_id"] == "CB-TS-002")
    assert dress["country_of_origin"] == "China"
    assert tshirt["fiber_content"] == "100% Cotton"
    assert len(dress["skus"]) == 4
    assert len(tshirt["skus"]) == 4

    listing = final["result"]["listing"]
    for shopify, ebay in zip(listing["shopify"], listing["ebay"]):
        shopify_rows = shopify["data"]["rows"]
        ebay_data = ebay["data"]
        assert {row["Variant SKU"] for row in shopify_rows} == {item["sku"] for item in ebay_data["variations"]}
        assert {row["Option1 Value"] for row in shopify_rows} == {item["specifics"]["Size"] for item in ebay_data["variations"]}
        assert len({row["Metafield: custom.material [single_line_text_field]"] for row in shopify_rows}) == 1
        assert len({row["Metafield: custom.country_of_origin [single_line_text_field]"] for row in shopify_rows}) == 1
        assert next(iter({row["Metafield: custom.material [single_line_text_field]"] for row in shopify_rows})) == ebay_data["itemSpecifics"]["Material"]
        assert next(iter({row["Metafield: custom.country_of_origin [single_line_text_field]"] for row in shopify_rows})) == ebay_data["itemSpecifics"]["Country/Region of Manufacture"]

    package = final["result"]["governance"]["package"]
    package_path = Path(package["absolute_path"])
    assert package_path.is_file()
    with zipfile.ZipFile(package_path) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
    assert "manifest.json" in names
    assert any("canonical_product" in name for name in names)
    assert any("shopify_listing" in name for name in names)
    assert any("ebay_listing" in name for name in names)
    assert manifest["release_review"]["ready_for_export"] is True
