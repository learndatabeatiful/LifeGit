from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from scripts.local_security import load_json_preserving_corrupt, require_identifier
    from scripts.semantic_records import validate_semantic_record_graph
except ModuleNotFoundError:
    from local_security import load_json_preserving_corrupt, require_identifier
    from semantic_records import validate_semantic_record_graph


def _write_json_atomically(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load_json(path: Path) -> Any:
    return load_json_preserving_corrupt(path)


def _manifest_path(root: Path) -> Path:
    return root / "manifest.json"


def _record_path(root: Path, record_id: str) -> Path:
    require_identifier(record_id, "record_id")
    return root / "records" / f"{record_id}.json"


def _trash_path(root: Path, record_id: str) -> Path:
    require_identifier(record_id, "record_id")
    return root / ".trash" / "records" / f"{record_id}.json"


def _validate_manifest_record_ids(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"workspace manifest {label} must be a list")
    for record_id in value:
        require_identifier(record_id, label)
    if len(value) != len(set(value)):
        raise ValueError(f"workspace manifest {label} must not contain duplicates")
    return value


def validate_workspace_manifest(root: Path) -> dict[str, Any]:
    """Read and validate a workspace manifest without modifying the filesystem."""
    manifest_path = _manifest_path(root)
    if not manifest_path.exists() and not manifest_path.is_symlink():
        raise FileNotFoundError(f"workspace manifest not found: {manifest_path}")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError(f"workspace manifest must be a regular file: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid workspace manifest: {manifest_path}") from error
    if not isinstance(manifest, dict):
        raise ValueError("workspace manifest must be an object")
    if manifest.get("format_version") != "1.0":
        raise ValueError("unsupported workspace manifest format_version")
    require_identifier(manifest.get("workspace_id"), "workspace_id")
    if not isinstance(manifest.get("created_at"), str) or not manifest["created_at"]:
        raise ValueError("workspace manifest created_at must be a non-empty string")
    record_ids = _validate_manifest_record_ids(manifest.get("record_ids"), "record_ids")
    deleted_record_ids = _validate_manifest_record_ids(
        manifest.get("deleted_record_ids"), "deleted_record_ids"
    )
    if set(record_ids) & set(deleted_record_ids):
        raise ValueError("workspace manifest record ids must not overlap")
    return manifest


def ensure_workspace_layout(root: Path) -> Path:
    """Create additive runtime directories for an existing LifeGit workspace."""
    manifest_path = _manifest_path(root)
    validate_workspace_manifest(root)
    for relative in (
        "records",
        ".trash/records",
        "exports",
        "sessions",
        "jobs",
        "outputs",
        "outputs/cards",
        "outputs/images",
        "runtime",
        "branches",
        "branches/.pending",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    return manifest_path


def initialize_workspace(root: Path, workspace_id: str, created_at: str) -> Path:
    manifest_path = _manifest_path(root)
    if manifest_path.exists():
        raise FileExistsError(f"workspace already exists: {root}")
    if root.exists():
        if not root.is_dir() or any(root.iterdir()):
            raise FileExistsError(f"workspace destination is not empty: {root}")
    else:
        root.mkdir(parents=True, exist_ok=False)
    (root / "records").mkdir()
    (root / ".trash" / "records").mkdir(parents=True)
    (root / "exports").mkdir()
    _write_json_atomically(
        manifest_path,
        {
            "format_version": "1.0",
            "workspace_id": workspace_id,
            "created_at": created_at,
            "record_ids": [],
            "deleted_record_ids": [],
        },
    )
    ensure_workspace_layout(root)
    return manifest_path


def save_record(root: Path, record: dict[str, Any]) -> Path:
    manifest = _load_json(_manifest_path(root))
    existing = [_load_json(path) for path in sorted((root / "records").glob("rec_*.json"))]
    errors = validate_semantic_record_graph(existing + [record])
    if errors:
        raise ValueError("; ".join(errors))
    path = _record_path(root, record["id"])
    if path.exists() or _trash_path(root, record["id"]).exists():
        raise FileExistsError(f"record already exists: {record['id']}")
    _write_json_atomically(path, record)
    manifest["record_ids"].append(record["id"])
    _write_json_atomically(_manifest_path(root), manifest)
    return path


def inspect_delete_impact(root: Path, record_id: str) -> list[str]:
    impacts: list[str] = []
    for path in sorted((root / "records").glob("rec_*.json")):
        record = _load_json(path)
        if record_id in record.get("base_record_ids", []) or record.get("simulation_origin_id") == record_id:
            impacts.append(record["id"])
    return impacts


def trash_record(root: Path, record_id: str, deleted_at: str) -> Path:
    source = _record_path(root, record_id)
    target = _trash_path(root, record_id)
    if not source.exists():
        raise FileNotFoundError(f"active record not found: {record_id}")
    if target.exists():
        raise FileExistsError(f"trash record already exists: {record_id}")
    record = _load_json(source)
    record["deleted_at"] = deleted_at
    _write_json_atomically(target, record)
    source.unlink()
    manifest = _load_json(_manifest_path(root))
    manifest["record_ids"].remove(record_id)
    manifest["deleted_record_ids"].append(record_id)
    _write_json_atomically(_manifest_path(root), manifest)
    return target


def restore_record(root: Path, record_id: str) -> Path:
    source = _trash_path(root, record_id)
    target = _record_path(root, record_id)
    if not source.exists():
        raise FileNotFoundError(f"trash record not found: {record_id}")
    if target.exists():
        raise FileExistsError(f"active record already exists: {record_id}")
    record = _load_json(source)
    record.pop("deleted_at", None)
    _write_json_atomically(target, record)
    source.unlink()
    manifest = _load_json(_manifest_path(root))
    manifest["deleted_record_ids"].remove(record_id)
    manifest["record_ids"].append(record_id)
    _write_json_atomically(_manifest_path(root), manifest)
    return target


def export_record(root: Path, record_id: str, destination: Path) -> Path:
    source = _record_path(root, record_id)
    if not source.exists():
        raise FileNotFoundError(f"active record not found: {record_id}")
    if destination.exists():
        raise FileExistsError(f"export destination exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomically(destination, _load_json(source))
    return destination
