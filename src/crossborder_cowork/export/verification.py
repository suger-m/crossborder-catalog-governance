from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


def verify_listing_package(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Listing package does not exist: {path}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Listing package contains duplicate member paths")
        if "manifest.json" not in names:
            raise ValueError("Listing package manifest.json is missing")
        manifest = json.loads(archive.read("manifest.json"))
        files = manifest.get("files") or []
        if len(files) + 1 != len(names):
            raise ValueError("Listing package manifest member count does not match the archive")
        verified: list[dict[str, Any]] = []
        for member in files:
            member_path = str(member.get("path") or "")
            pure_path = PurePosixPath(member_path)
            if not member_path.startswith("artifacts/") or pure_path.is_absolute() or ".." in pure_path.parts:
                raise ValueError(f"Unsafe listing package member path: {member_path}")
            try:
                content = archive.read(member_path)
            except KeyError as exc:
                raise ValueError(f"Manifest member is missing from listing package: {member_path}") from exc
            digest = hashlib.sha256(content).hexdigest()
            if digest != member.get("sha256") or len(content) != member.get("size_bytes"):
                raise ValueError(f"Listing package member integrity mismatch: {member_path}")
            verified.append({"path": member_path, "sha256": digest, "size_bytes": len(content)})
    return {"manifest": manifest, "verified_files": verified, "member_count": len(verified)}
