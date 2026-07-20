from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable


IGNORED_PARTS = {".git", "__pycache__", ".DS_Store"}


def package_files(root: Path) -> Iterable[Path]:
    return (
        path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part in IGNORED_PARTS for part in path.relative_to(root).parts)
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_public_manifest(output_root: Path) -> Path:
    version = (output_root / "VERSION").read_text(encoding="utf-8").strip()
    files = {
        path.relative_to(output_root).as_posix(): _sha256(path)
        for path in package_files(output_root)
        if path != output_root / "PUBLIC_MANIFEST.json"
    }
    value = {"format_version": 1, "version": version, "files": files}
    path = output_root / "PUBLIC_MANIFEST.json"
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def verify_public_manifest(output_root: Path) -> dict:
    manifest_path = output_root / "PUBLIC_MANIFEST.json"
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if value.get("format_version") != 1:
        raise ValueError("unsupported public manifest format")
    if value.get("version") != (output_root / "VERSION").read_text(encoding="utf-8").strip():
        raise ValueError("VERSION does not match PUBLIC_MANIFEST.json")
    expected = set(value.get("files", {}))
    actual = {
        path.relative_to(output_root).as_posix()
        for path in package_files(output_root)
        if path != output_root / "PUBLIC_MANIFEST.json"
    }
    if expected != actual:
        raise ValueError("public manifest file set mismatch")
    for relative, expected_hash in value["files"].items():
        if _sha256(output_root / relative) != expected_hash:
            raise ValueError(f"hash mismatch: {relative}")
    return value
