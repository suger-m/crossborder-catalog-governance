from __future__ import annotations

from pathlib import Path

from ..catalog.models import CatalogBatch
from ..intake.service import IntakeService


def parse_product_sources(paths: list[str], service: IntakeService) -> CatalogBatch:
    return service.parse([Path(path) for path in paths])
