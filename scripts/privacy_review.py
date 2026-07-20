from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from scripts.local_security import load_json_preserving_corrupt, require_identifier
except ModuleNotFoundError:
    from local_security import load_json_preserving_corrupt, require_identifier


WARNING = "未列入脱敏清单的信息默认不会脱敏，确认后选中的文字将交给当前 Agent 使用的模型处理。"


def _path(root: Path, session_id: str, review_id: str) -> Path:
    require_identifier(session_id, "session_id")
    require_identifier(review_id, "review_id")
    return root / "sessions" / f"{session_id}.{review_id}.privacy.json"


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def create_privacy_review(
    root: Path,
    session_id: str,
    review_id: str,
    fields: dict[str, str],
    redactions: list[str],
    now: str,
) -> Path:
    path = _path(root, session_id, review_id)
    if path.exists():
        raise FileExistsError(f"privacy review exists: {review_id}")
    valid_fields = (
        isinstance(fields, dict)
        and bool(fields)
        and all(
            isinstance(key, str)
            and bool(key.strip())
            and isinstance(value, str)
            and bool(value.strip())
            for key, value in fields.items()
        )
    )
    valid_redactions = isinstance(redactions, list) and all(
        isinstance(item, str) for item in redactions
    )
    if not valid_fields or not valid_redactions:
        raise ValueError(
            "privacy fields and redactions must be non-empty text fields and a text list"
        )

    unique: list[str] = []
    for item in redactions:
        literal = item.strip()
        if literal and literal not in unique:
            unique.append(literal)
    literals = sorted(unique, key=len, reverse=True)
    replacements = {
        literal: f"[PRIVATE_{index}]" for index, literal in enumerate(literals, 1)
    }
    sanitized: dict[str, str] = {}
    for key, text in fields.items():
        sanitized[key] = text
        for literal, placeholder in replacements.items():
            sanitized[key] = sanitized[key].replace(literal, placeholder)
    _write(
        path,
        {
            "review_id": review_id,
            "session_id": session_id,
            "warning": WARNING,
            "sanitized_fields": sanitized,
            "privacy_map": {
                placeholder: literal for literal, placeholder in replacements.items()
            },
            "confirmed": False,
            "created_at": now,
            "confirmed_at": None,
        },
    )
    return path


def confirm_privacy_review(
    root: Path,
    session_id: str,
    review_id: str,
    now: str,
) -> Path:
    path = _path(root, session_id, review_id)
    value = load_json_preserving_corrupt(path)
    value["confirmed"] = True
    value["confirmed_at"] = now
    _write(path, value)
    return path


def load_confirmed_payload(
    root: Path,
    session_id: str,
    review_id: str,
) -> dict[str, str]:
    value = load_json_preserving_corrupt(_path(root, session_id, review_id))
    if not value["confirmed"]:
        raise ValueError("privacy review must be confirmed")
    return value["sanitized_fields"]


def restore_confirmed_text(
    root: Path,
    session_id: str,
    review_id: str,
    text: str,
) -> str:
    value = load_json_preserving_corrupt(_path(root, session_id, review_id))
    if not value["confirmed"]:
        raise ValueError("privacy review must be confirmed")
    restored = text
    for placeholder, literal in value["privacy_map"].items():
        restored = restored.replace(placeholder, literal)
    return restored
