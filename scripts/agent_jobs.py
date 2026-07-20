from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

try:
    from scripts.local_security import (
        load_json_preserving_corrupt,
        require_identifier,
        resolve_within,
    )
    from scripts.privacy_review import load_confirmed_payload, restore_confirmed_text
    from scripts.share_projection import (
        apply_agent_result,
        mark_agent_failed,
        mark_agent_pending,
    )
except ModuleNotFoundError:
    from local_security import load_json_preserving_corrupt, require_identifier, resolve_within
    from privacy_review import load_confirmed_payload, restore_confirmed_text
    from share_projection import apply_agent_result, mark_agent_failed, mark_agent_pending


JOB_CAPABILITY = {
    "text_enhancement": "text_ai",
    "image_background": "image_generation",
}


def _job_path(root: Path, job_id: str) -> Path:
    require_identifier(job_id, "job_id")
    return root / "jobs" / f"{job_id}.json"


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def register_capabilities(
    root: Path,
    capabilities: dict[str, Any],
    now: str,
) -> Path:
    if not isinstance(capabilities, dict):
        raise ValueError("capabilities must be an object")
    allowed = {"text_ai", "image_generation"}
    if set(capabilities) - allowed:
        raise ValueError("unknown capability")
    for name, config in capabilities.items():
        if not isinstance(config, dict) or not isinstance(config.get("available"), bool):
            raise ValueError(f"invalid capability: {name}")
        if name == "image_generation":
            for field in ["provider", "model_id"]:
                if config.get(field) is not None and not isinstance(config[field], str):
                    raise ValueError(f"invalid image capability field: {field}")
    path = root / "runtime" / "capabilities.json"
    _write(path, {"capabilities": capabilities, "updated_at": now})
    return path


def load_capabilities(root: Path) -> dict[str, Any]:
    path = root / "runtime" / "capabilities.json"
    if not path.exists():
        return {}
    return load_json_preserving_corrupt(path)["capabilities"]


def create_job(
    root: Path,
    job_id: str,
    session_id: str,
    kind: str,
    privacy_review_id: str,
    now: str,
) -> Path:
    require_identifier(session_id, "session_id")
    require_identifier(privacy_review_id, "privacy_review_id")
    capability = JOB_CAPABILITY.get(kind)
    if capability is None:
        raise ValueError(f"unknown job kind: {kind}")
    if not load_capabilities(root).get(capability, {}).get("available", False):
        raise ValueError(f"capability unavailable: {capability}")
    projection = root / "outputs" / "cards" / f"{session_id}.card.json"
    if not projection.exists():
        raise ValueError("local projection must exist before creating an AI job")
    payload = load_confirmed_payload(root, session_id, privacy_review_id)
    path = _job_path(root, job_id)
    if path.exists():
        raise FileExistsError(f"job exists: {job_id}")
    _write(
        path,
        {
            "job_id": job_id,
            "session_id": session_id,
            "kind": kind,
            "required_capability": capability,
            "status": "queued",
            "input": payload,
            "privacy_review_id": privacy_review_id,
            "worker_id": None,
            "claim_expires_at": None,
            "attempts": 0,
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        },
    )
    mark_agent_pending(root, session_id, job_id, now)
    return path


def get_job(root: Path, job_id: str) -> dict[str, Any]:
    return load_json_preserving_corrupt(_job_path(root, job_id))


def claim_next_job(
    root: Path,
    worker_id: str,
    now: str,
    claim_expires_at: str,
) -> dict[str, Any] | None:
    require_identifier(worker_id, "worker_id")
    for path in sorted((root / "jobs").glob("*.json")):
        value = load_json_preserving_corrupt(path)
        expired = (
            value["status"] == "claimed"
            and value["claim_expires_at"] is not None
            and value["claim_expires_at"] <= now
        )
        if value["status"] == "queued" or expired:
            value.update(
                {
                    "status": "claimed",
                    "worker_id": worker_id,
                    "claim_expires_at": claim_expires_at,
                    "attempts": value["attempts"] + 1,
                    "updated_at": now,
                }
            )
            _write(path, value)
            return value
    return None


def _validate_text_result(
    result: dict[str, Any],
    input_fields: dict[str, str],
) -> None:
    if not isinstance(result, dict):
        raise ValueError("text result must be an object")
    if not isinstance(result.get("fragment_markdown"), str) or not result[
        "fragment_markdown"
    ].strip():
        raise ValueError("fragment_markdown is required")
    candidates = result.get("core_candidates")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 3:
        raise ValueError("one to three core candidates are required")
    for item in candidates:
        if not isinstance(item, dict):
            raise ValueError("invalid core candidate")
        text = item.get("text", "").strip()
        if (
            item.get("source_type") not in {"exact_quote", "light_edit"}
            or not text
            or len(text) > 48
        ):
            raise ValueError("invalid core candidate")
        if item["source_type"] == "exact_quote" and text not in "\n".join(
            input_fields.values()
        ):
            raise ValueError("exact_quote must exist in sanitized input")


def _result_digest(result: dict[str, Any]) -> str:
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_image_header(source: Path, suffix: str) -> bool:
    header = source.read_bytes()[:12]
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if suffix == ".webp":
        return header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return False


def complete_job(
    root: Path,
    job_id: str,
    worker_id: str,
    result: dict[str, Any],
    now: str,
) -> Path:
    require_identifier(worker_id, "worker_id")
    path = _job_path(root, job_id)
    value = get_job(root, job_id)
    if value["kind"] == "text_enhancement":
        _validate_text_result(result, value["input"])
        review_id = value["privacy_review_id"]
        result = {
            "fragment_markdown": restore_confirmed_text(
                root,
                value["session_id"],
                review_id,
                result["fragment_markdown"],
            ),
            "core_candidates": [
                {
                    "text": restore_confirmed_text(
                        root,
                        value["session_id"],
                        review_id,
                        item["text"],
                    ),
                    "source_type": item["source_type"],
                }
                for item in result["core_candidates"]
            ],
        }
    elif value["kind"] == "image_background":
        if not isinstance(result, dict) or not isinstance(result.get("source_path"), str):
            raise ValueError("image source_path is required")
        source = Path(result["source_path"])
        if not source.is_file() or source.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("invalid image artifact")
        suffix = source.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"} or not _valid_image_header(
            source, suffix
        ):
            raise ValueError("unsupported image artifact")
        target = resolve_within(root, Path("outputs/images") / f"{job_id}{suffix}")
        if not target.exists():
            shutil.copy2(source, target)
        result = {"image_path": str(target), "ai_generated": True}
    else:
        raise ValueError(f"unknown job kind: {value['kind']}")

    digest = _result_digest(result)
    if value["status"] == "completed":
        if value["result_digest"] != digest:
            raise ValueError("conflicting completed result")
        apply_agent_result(
            root,
            value["session_id"],
            job_id,
            value["kind"],
            result,
            now,
        )
        return path
    if value["status"] != "claimed" or value["worker_id"] != worker_id:
        raise ValueError("job must be claimed by this worker")
    value.update(
        {
            "status": "completed",
            "result": result,
            "result_digest": digest,
            "claim_expires_at": None,
            "updated_at": now,
        }
    )
    _write(path, value)
    apply_agent_result(
        root,
        value["session_id"],
        job_id,
        value["kind"],
        result,
        now,
    )
    return path


def fail_job(
    root: Path,
    job_id: str,
    worker_id: str,
    code: str,
    message: str,
    retryable: bool,
    now: str,
) -> Path:
    require_identifier(worker_id, "worker_id")
    path = _job_path(root, job_id)
    value = get_job(root, job_id)
    if value["status"] != "claimed" or value["worker_id"] != worker_id:
        raise ValueError("job must be claimed by this worker")
    value.update(
        {
            "status": "queued" if retryable else "failed",
            "worker_id": None,
            "claim_expires_at": None,
            "error": {"code": code, "message": message, "retryable": retryable},
            "updated_at": now,
        }
    )
    _write(path, value)
    mark_agent_failed(root, value["session_id"], job_id, retryable, now)
    return path
