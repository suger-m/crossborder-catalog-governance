from __future__ import annotations

from ..catalog.models import CanonicalProduct, CatalogConflict
from ..compliance.us_apparel import ComplianceResult, UsApparelComplianceService


def check_product_compliance(product: CanonicalProduct, conflicts: list[CatalogConflict], service: UsApparelComplianceService) -> ComplianceResult:
    return service.evaluate(product, conflicts)
