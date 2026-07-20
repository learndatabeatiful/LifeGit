from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from scripts.entry_definitions import get_entry
    from scripts.local_security import load_json_preserving_corrupt, require_identifier
    from scripts.semantic_records import next_revision
    from scripts.workspace_store import save_record
except ModuleNotFoundError:
    from entry_definitions import get_entry
    from local_security import load_json_preserving_corrupt, require_identifier
    from semantic_records import next_revision
    from workspace_store import save_record


def _session_path(root: Path, session_id: str) -> Path:
    require_identifier(session_id, "session_id")
    return root / "sessions" / f"{session_id}.json"


def _write_json_atomically(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load_session(root: Path, session_id: str) -> dict[str, Any]:
    path = _session_path(root, session_id)
    if not path.exists():
        raise FileNotFoundError(f"session not found: {session_id}")
    return load_json_preserving_corrupt(path)


def load_session(root: Path, session_id: str) -> dict[str, Any]:
    """Load a fresh, caller-owned session snapshot."""
    return _load_session(root, session_id)


def list_sessions(root: Path) -> list[dict[str, Any]]:
    sessions_root = root / "sessions"
    if not sessions_root.exists():
        return []
    sessions: list[dict[str, Any]] = []
    for path in sorted(sessions_root.glob("ses_*.json")):
        if path.name.endswith(".privacy.json"):
            continue
        value = load_json_preserving_corrupt(path)
        if isinstance(value, dict) and value.get("session_id"):
            sessions.append(value)
    return sessions


def _save_session(root: Path, session: dict[str, Any]) -> Path:
    path = _session_path(root, session["session_id"])
    _write_json_atomically(path, session)
    return path


def _question_ids(session: dict[str, Any]) -> set[str]:
    return {question["id"] for question in get_entry(session["entry_id"])["questions"]}


def start_session(root: Path, session_id: str, entry_id: str, anchor: str, now: str) -> Path:
    if not session_id.strip() or not anchor.strip():
        raise ValueError("session_id and anchor must be non-empty")
    get_entry(entry_id)
    path = _session_path(root, session_id)
    if path.exists():
        raise FileExistsError(f"session already exists: {session_id}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return _save_session(root, {
        "session_id": session_id,
        "entry_id": entry_id,
        "anchor": anchor,
        "answers": {},
        "skipped_question_ids": [],
        "status": "active",
        "revision": 1,
        "result_stale": False,
        "created_at": now,
        "updated_at": now,
    })


def next_question(root: Path, session_id: str) -> dict[str, str] | None:
    session = _load_session(root, session_id)
    if session["status"] != "active":
        return None
    for question in get_entry(session["entry_id"])["questions"]:
        if question["id"] not in session["answers"] and question["id"] not in session["skipped_question_ids"]:
            return question
    return None


def answer_question(root: Path, session_id: str, question_id: str, answer: str, now: str) -> Path:
    session = _load_session(root, session_id)
    if session["status"] != "active":
        raise ValueError("only active sessions accept answers")
    if question_id not in _question_ids(session):
        raise ValueError(f"unknown question: {question_id}")
    if not answer.strip():
        raise ValueError("answer must be non-empty")
    if question_id in session["answers"] or question_id in session["skipped_question_ids"]:
        raise ValueError(f"question already handled: {question_id}")
    session["answers"][question_id] = answer
    session["updated_at"] = now
    session["result_stale"] = True
    return _save_session(root, session)


def skip_question(root: Path, session_id: str, question_id: str, now: str) -> Path:
    session = _load_session(root, session_id)
    if session["status"] != "active" or question_id not in _question_ids(session):
        raise ValueError("question cannot be skipped")
    if question_id in session["answers"] or question_id in session["skipped_question_ids"]:
        raise ValueError(f"question already handled: {question_id}")
    session["skipped_question_ids"].append(question_id)
    session["updated_at"] = now
    session["result_stale"] = True
    return _save_session(root, session)


def pause_session(root: Path, session_id: str, now: str) -> Path:
    session = _load_session(root, session_id)
    if session["status"] != "active":
        raise ValueError("only active sessions can pause")
    session["status"] = "paused"
    session["updated_at"] = now
    return _save_session(root, session)


def resume_session(root: Path, session_id: str, now: str) -> Path:
    session = _load_session(root, session_id)
    if session["status"] != "paused":
        raise ValueError("only paused sessions can resume")
    session["status"] = "active"
    session["updated_at"] = now
    return _save_session(root, session)


def edit_anchor(root: Path, session_id: str, anchor: str, now: str) -> Path:
    if not anchor.strip():
        raise ValueError("anchor must be non-empty")
    session = _load_session(root, session_id)
    if session["status"] not in {"active", "paused"}:
        raise ValueError("completed or stopped sessions cannot be edited")
    session["anchor"] = anchor
    session["revision"] = next_revision(session)
    session["result_stale"] = True
    session["updated_at"] = now
    return _save_session(root, session)


def _record_id(session_id: str) -> str:
    return "rec_session_" + session_id.removeprefix("ses_")


def _record(record_id: str, layer: str, text: str, now: str, **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "id": record_id,
        "semantic_layer": layer,
        "text": text,
        "source_refs": ["src_guided_session"],
        "status": "user_confirmed" if layer != "simulation" else "inferred",
        "confidence": 0.8 if layer != "simulation" else 0.3,
        "sensitivity": "medium",
        "visibility": "private",
        "created_at": now,
        "revision": 1,
    }
    value.update(extra)
    return value


def _render_fragment(session: dict[str, Any], entry: dict[str, Any]) -> str:
    answers = session["answers"]
    questions = {question["id"]: question for question in entry["questions"]}
    lines = [
        f"# {entry['label']}：私密人生片段",
        "", "## 那一天", session["anchor"],
    ]
    for question_id, heading in [("detail", "你记得的那一天"), ("feeling", "当时的感受"), ("today", "今天回看")]:
        if question_id in answers:
            lines.extend(["", f"## {heading}", answers[question_id]])
    lines.extend(["", "## 待确认项"])
    skipped = session["skipped_question_ids"]
    lines.extend([f"- {questions[item]['prompt']}" for item in skipped] or ["- 暂无"])
    if entry["allows_simulation"]:
        lines.extend(["", "## 选择整理", "这是基于当前约束的整理，不是对未来的预测。", "", "这是模拟，不是事实。"])
    lines.extend(["", "## 下一步", "你可以补充材料、编辑这份片段，或继续回看。", ""])
    return "\n".join(lines)


def complete_session(root: Path, session_id: str, now: str) -> tuple[Path, Path]:
    session = _load_session(root, session_id)
    if session["status"] != "active":
        raise ValueError("only active sessions can complete")
    if next_question(root, session_id) is not None:
        raise ValueError("all questions must be answered or skipped before completion")
    entry = get_entry(session["entry_id"])
    output_path = root / "outputs" / f"{session_id}.md"
    if output_path.exists():
        raise FileExistsError(f"output already exists: {output_path}")
    fact_id = _record_id(session_id)
    saved = [save_record(root, _record(fact_id, "fact", session["anchor"], now))]
    for index, answer in enumerate(session["answers"].values(), start=1):
        saved.append(save_record(root, _record(f"{fact_id}_memory_{index}", "memory", answer, now)))
    if entry["allows_simulation"]:
        simulation_id = f"{fact_id}_simulation"
        saved.append(save_record(root, _record(simulation_id, "simulation", "基于当前选择与约束的谨慎模拟。", now, base_record_ids=[fact_id])))
        saved.append(save_record(root, _record(f"{fact_id}_understanding", "understanding", "用户确认的当前理解。", now, simulation_origin_id=simulation_id)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".md.tmp")
    temporary.write_text(_render_fragment(session, entry), encoding="utf-8")
    os.replace(temporary, output_path)
    session["status"] = "completed"
    session["result_stale"] = False
    session["updated_at"] = now
    session["record_ids"] = [path.stem for path in saved]
    session["output_path"] = str(output_path)
    _save_session(root, session)
    return saved[0], output_path
