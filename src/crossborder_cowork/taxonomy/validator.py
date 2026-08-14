from __future__ import annotations

from ..catalog.models import TaxonomyAssignment
from .registry import TaxonomyRegistry


def validate_assignment(registry: TaxonomyRegistry, assignment: TaxonomyAssignment, evidence_text: str) -> None:
    registry.get_node(assignment.node_id, assignment.taxonomy_version)
    if not assignment.evidence_span.strip():
        raise ValueError("Taxonomy evidence_span is required")
    if assignment.evidence_span not in evidence_text:
        raise ValueError("Taxonomy evidence_span must occur in source evidence")
    if assignment.confidence < 0 or assignment.confidence > 1:
        raise ValueError("Taxonomy confidence must be between 0 and 1")
