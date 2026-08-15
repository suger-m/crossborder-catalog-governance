from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from ..catalog.models import CanonicalProduct
from ..platform.artifacts import ArtifactService
from ..util import json_dumps, sha256_file


class ExportPackageService:
    def __init__(self, artifacts: ArtifactService) -> None:
        self.artifacts = artifacts

    def create_sku_matrix(self, task_id: str, products: list[CanonicalProduct], dependencies: list[str]) -> dict:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "SKU Matrix"
        sheet.append(["Product ID", "Product Title", "SKU", "Color", "Size", "Fiber Content", "Country of Origin", "Price", "Inventory"])
        for product in products:
            for sku in product.skus:
                sheet.append([product.external_id, product.title, sku.external_id, sku.color, sku.size, product.fiber_content, product.country_of_origin, sku.price, sku.inventory])
        stream = io.BytesIO()
        workbook.save(stream)
        return self.artifacts.create_bytes(
            task_id, "governance_reviewer_agent", "sku_matrix", "sku_matrix", stream.getvalue(),
            "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", dependencies,
        )

    def create_package(self, task_id: str, artifact_ids: list[str], review: dict[str, Any]) -> dict:
        members: list[dict[str, Any]] = []
        selected_artifacts: list[dict[str, Any]] = []
        for artifact_id in dict.fromkeys(artifact_ids):
            artifact = self.artifacts.get(artifact_id)
            if artifact and Path(artifact["absolute_path"]).is_file():
                selected_artifacts.append(artifact)
        manifest = {
            "format": "crossborder-listing-package@v1",
            "task_id": task_id,
            "release_review": review,
            "files": [],
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for artifact in selected_artifacts:
                path = Path(artifact["absolute_path"])
                arcname = f"artifacts/{artifact['artifact_type']}-{artifact['id']}{path.suffix.lower()}"
                info = zipfile.ZipInfo(arcname, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
                member = {"artifact_id": artifact["id"], "path": arcname, "sha256": artifact["sha256"], "size_bytes": artifact["size_bytes"]}
                members.append(member)
            manifest["files"] = members
            info = zipfile.ZipInfo("manifest.json", date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, json_dumps(manifest).encode("utf-8"))
        return self.artifacts.create_bytes(
            task_id, "governance_reviewer_agent", "listing_package", "listing_package", stream.getvalue(),
            "zip", "application/zip", artifact_ids, {"member_count": len(members)},
        )
