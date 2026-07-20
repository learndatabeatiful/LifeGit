from __future__ import annotations

import binascii
import json
import os
import re
import struct
from pathlib import Path
from typing import Any

try:
    from scripts.entry_definitions import get_entry
    from scripts.guided_session import load_session
    from scripts.local_security import (
        load_json_preserving_corrupt,
        require_identifier,
        resolve_within,
    )
except ModuleNotFoundError:
    from entry_definitions import get_entry
    from guided_session import load_session
    from local_security import load_json_preserving_corrupt, require_identifier, resolve_within


SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?")


def _write_json_atomically(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _projection_path(root: Path, session_id: str) -> Path:
    require_identifier(session_id, "session_id")
    return root / "outputs" / "cards" / f"{session_id}.card.json"


def _exact_candidates(session: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for question_id, answer in session["answers"].items():
        for match in SENTENCE_RE.findall(answer):
            text = match.strip()
            known = {item["text"] for item in candidates}
            if 6 <= len(text) <= 40 and text not in known:
                candidates.append(
                    {
                        "id": f"quote_{len(candidates) + 1}",
                        "text": text,
                        "source_type": "exact_quote",
                        "source_question_id": question_id,
                    }
                )
            if len(candidates) == 3:
                return candidates
    fallback = session["anchor"].strip()[:40]
    return candidates or [
        {
            "id": "quote_1",
            "text": fallback,
            "source_type": "exact_quote",
            "source_question_id": "anchor",
        }
    ]


def build_local_projection(root: Path, session_id: str, now: str) -> Path:
    session = load_session(root, session_id)
    if session["status"] != "completed":
        raise ValueError("session must be completed before projection")
    path = _projection_path(root, session_id)
    if path.exists():
        raise FileExistsError(f"projection already exists: {path}")
    entry = get_entry(session["entry_id"])
    candidates = _exact_candidates(session)
    stored_output = Path(session["output_path"])
    if stored_output.is_absolute():
        try:
            relative_output = stored_output.resolve().relative_to(root.resolve())
        except ValueError as error:
            raise ValueError("session output path escapes workspace") from error
    else:
        relative_output = stored_output
    fragment = resolve_within(root, relative_output).read_text(encoding="utf-8")
    value = {
        "session_id": session_id,
        "entry_id": session["entry_id"],
        "stage": "local_ready",
        "local_fragment_markdown": fragment,
        "core_candidates": candidates,
        "selected_candidate_id": candidates[0]["id"],
        "card_copy": {
            "theme_text": entry["anchor_prompt"],
            "core_text": candidates[0]["text"],
            "footer_text": "",
        },
        "pending_job_ids": [],
        "ai_job_ids": [],
        "exports": [],
        "updated_at": now,
    }
    _write_json_atomically(path, value)
    return path


def load_projection(root: Path, session_id: str) -> dict[str, Any]:
    return load_json_preserving_corrupt(_projection_path(root, session_id))


def mark_agent_pending(root: Path, session_id: str, job_id: str, now: str) -> Path:
    path = _projection_path(root, session_id)
    value = load_projection(root, session_id)
    if job_id not in value["pending_job_ids"]:
        value["pending_job_ids"].append(job_id)
    value["stage"] = "awaiting_agent"
    value["updated_at"] = now
    _write_json_atomically(path, value)
    return path


def apply_agent_result(
    root: Path,
    session_id: str,
    job_id: str,
    kind: str,
    result: dict[str, Any],
    now: str,
) -> Path:
    path = _projection_path(root, session_id)
    value = load_projection(root, session_id)
    if job_id in value["ai_job_ids"]:
        return path
    if kind == "text_enhancement":
        value["enhanced_fragment_markdown"] = result["fragment_markdown"]
        known = {item["text"] for item in value["core_candidates"]}
        for index, item in enumerate(result["core_candidates"], 1):
            if item["text"] not in known:
                value["core_candidates"].append(
                    {
                        "id": f"{job_id}_quote_{index}",
                        "text": item["text"],
                        "source_type": item["source_type"],
                        "source_question_id": None,
                        "origin_job_id": job_id,
                    }
                )
                known.add(item["text"])
    elif kind == "image_background":
        value["background_image"] = {
            "path": result["image_path"],
            "ai_generated": True,
            "origin_job_id": job_id,
        }
    else:
        raise ValueError(f"unknown result kind: {kind}")
    value["ai_job_ids"].append(job_id)
    value["pending_job_ids"] = [
        item for item in value["pending_job_ids"] if item != job_id
    ]
    value["stage"] = "exported" if value["exports"] else "ready"
    value["updated_at"] = now
    _write_json_atomically(path, value)
    return path


def mark_agent_failed(
    root: Path,
    session_id: str,
    job_id: str,
    retryable: bool,
    now: str,
) -> Path:
    path = _projection_path(root, session_id)
    value = load_projection(root, session_id)
    if not retryable:
        value["pending_job_ids"] = [
            item for item in value["pending_job_ids"] if item != job_id
        ]
    value["stage"] = (
        "awaiting_agent"
        if value["pending_job_ids"]
        else (
            "exported"
            if value["exports"]
            else ("ready" if value["ai_job_ids"] else "local_ready")
        )
    )
    value["updated_at"] = now
    _write_json_atomically(path, value)
    return path


def update_card_copy(
    root: Path,
    session_id: str,
    card_copy: dict[str, str],
    now: str,
) -> Path:
    if set(card_copy) != {"theme_text", "core_text", "footer_text"}:
        raise ValueError("card copy fields must be exact")
    if not all(isinstance(value, str) for value in card_copy.values()):
        raise ValueError("card copy fields must be strings")
    if not card_copy["core_text"].strip():
        raise ValueError("core_text must be non-empty")
    limits = {"theme_text": 60, "core_text": 48, "footer_text": 40}
    if any(len(card_copy[key].strip()) > limit for key, limit in limits.items()):
        raise ValueError("card copy exceeds layout limits")
    value = load_projection(root, session_id)
    value["card_copy"] = {key: text.strip() for key, text in card_copy.items()}
    value["updated_at"] = now
    path = _projection_path(root, session_id)
    _write_json_atomically(path, value)
    return path


def _png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("invalid PNG")
    offset, dimensions, saw_end = 8, None, False
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError("truncated PNG chunk")
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        expected = struct.unpack(">I", data[offset + 8 + length : end])[0]
        if (binascii.crc32(kind + payload) & 0xFFFFFFFF) != expected:
            raise ValueError("invalid PNG checksum")
        if kind == b"IHDR":
            if dimensions is not None or length != 13:
                raise ValueError("invalid IHDR")
            dimensions = struct.unpack(">II", payload[:8])
        if kind == b"IEND":
            saw_end = True
            offset = end
            break
        offset = end
    if dimensions is None or not saw_end or offset != len(data):
        raise ValueError("incomplete PNG")
    return dimensions


def save_card_png(root: Path, session_id: str, data: bytes, now: str) -> Path:
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("PNG exceeds 5 MiB")
    if _png_dimensions(data) != (1080, 1350):
        raise ValueError("card PNG must be 1080 x 1350")
    directory = root / "outputs" / "cards"
    version = 1
    while (directory / f"{session_id}-card-v{version}.png").exists():
        version += 1
    target = directory / f"{session_id}-card-v{version}.png"
    temporary = target.with_suffix(".png.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, target)
    value = load_projection(root, session_id)
    value["stage"] = "awaiting_agent" if value["pending_job_ids"] else "exported"
    value["exports"].append({"path": str(target), "created_at": now})
    value["updated_at"] = now
    _write_json_atomically(_projection_path(root, session_id), value)
    return target
