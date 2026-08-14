from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TaxonomyRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._documents: dict[tuple[str, str], dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        self._documents.clear()
        if not self.root.exists():
            return
        for path in sorted(self.root.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            self._documents[(document["taxonomy_id"], document["version"])] = document

    def list(self) -> list[dict[str, Any]]:
        return [{"taxonomy_id": key[0], "version": key[1], "domain": value.get("domain", ""), "node_count": len(value.get("nodes", []))} for key, value in self._documents.items()]

    def get_document(self, taxonomy_id: str, version: str = "v1") -> dict[str, Any]:
        try:
            return self._documents[(taxonomy_id, version)]
        except KeyError as exc:
            raise KeyError(f"Unknown taxonomy {taxonomy_id}@{version}") from exc

    def get_node(self, node_id: str, version: str = "v1") -> dict[str, Any]:
        for (taxonomy_id, taxonomy_version), document in self._documents.items():
            if taxonomy_version != version:
                continue
            for node in document.get("nodes", []):
                if node.get("id") == node_id:
                    return {**node, "taxonomy_id": taxonomy_id, "version": version}
        raise KeyError(f"Unknown taxonomy node {node_id}@{version}")

    def match(self, taxonomy_id: str, text: str, version: str = "v1") -> list[dict[str, Any]]:
        normalized = text.casefold()
        matches: list[dict[str, Any]] = []
        for node in self.get_document(taxonomy_id, version).get("nodes", []):
            terms = [node.get("label", ""), *node.get("synonyms", [])]
            for term in terms:
                if term and str(term).casefold() in normalized:
                    matches.append({**node, "matched_text": term, "confidence": 1.0})
                    break
        return matches
