"""Persist explicitly privacy-confirmed P1 text branch inputs."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

try:
    from scripts.local_security import load_json_preserving_corrupt, require_identifier
    from scripts.text_branch_package import scan_obvious_privacy_leaks
    from scripts.workspace_store import ensure_workspace_layout
except ModuleNotFoundError:
    from local_security import load_json_preserving_corrupt, require_identifier
    from text_branch_package import scan_obvious_privacy_leaks
    from workspace_store import ensure_workspace_layout


PRIVATE_PATH_REFERENCE_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9_])runs/"),
    re.compile(r"(?<![A-Za-z0-9_])sessions/[a-z0-9_]{1,80}(?![A-Za-z0-9_])"),
)


def _session_path(root: Path, session_id: str) -> Path:
    require_identifier(session_id, "session_id")
    return root / "sessions" / f"{session_id}.text-branch.json"


def _reject_private_path_references(values: list[str | None]) -> None:
    for value in values:
        if value and any(pattern.search(value) for pattern in PRIVATE_PATH_REFERENCE_PATTERNS):
            raise ValueError("private path reference is not allowed in confirmed input")


def save_confirmed_input(
    root: Path,
    session_id: str,
    sanitized_turning_point: str,
    alternative_choice: str,
    reality_state: str | None,
    unchanged_constraints: list[str],
    desired_today_change: str | None,
    privacy_mode: str,
    user_redaction_list: list[str],
    privacy_confirmed: bool,
    sensitive_fact_rewrite_attempted: bool | None,
    confirmed_at: str,
) -> Path:
    ensure_workspace_layout(root)
    if privacy_confirmed is not True:
        raise ValueError("explicit privacy confirmation is required")
    if sensitive_fact_rewrite_attempted is not False:
        raise ValueError("sensitive fact rewrite decision must be explicitly safe")
    if privacy_mode not in {"manual", "light", "medium", "heavy"}:
        raise ValueError("invalid privacy_mode")
    if not sanitized_turning_point.strip() or not alternative_choice.strip():
        raise ValueError("turning point and alternative choice are required")
    _reject_private_path_references([
        sanitized_turning_point,
        alternative_choice,
        reality_state,
        *unchanged_constraints,
        desired_today_change,
    ])
    payload = {
        "session_id": session_id,
        "sanitized_turning_point": sanitized_turning_point,
        "alternative_choice": alternative_choice,
        "reality_state": reality_state,
        "unchanged_constraints": unchanged_constraints,
        "desired_today_change": desired_today_change,
        "question_count": sum(
            bool(value)
            for value in (reality_state, unchanged_constraints, desired_today_change)
        ),
        "privacy_mode": privacy_mode,
        "redaction_count": len(user_redaction_list),
        "privacy_confirmed": privacy_confirmed,
        "sensitive_fact_rewrite_attempted": sensitive_fact_rewrite_attempted,
        "confirmed_at": confirmed_at,
        "generation_status": "ready",
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    for literal in user_redaction_list:
        if literal and literal in serialized:
            raise ValueError("declared redaction literal remains in sanitized input")
    scan_obvious_privacy_leaks(serialized)
    path = _session_path(root, session_id)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"confirmed branch input already exists: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    return path


def load_confirmed_input(root: Path, session_id: str) -> dict[str, object]:
    value = load_json_preserving_corrupt(_session_path(root, session_id))
    if value.get("privacy_confirmed") is not True:
        raise ValueError("branch input is not privacy confirmed")
    if value.get("sensitive_fact_rewrite_attempted") is not False:
        raise ValueError("branch input sensitive fact rewrite decision is not safe")
    return value
