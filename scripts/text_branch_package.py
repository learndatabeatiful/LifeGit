"""Validate an in-memory P1 text branch package."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

try:
    from scripts.local_security import require_identifier
    from scripts.schema_validation import validate_value_against_schema
    from scripts.workspace_store import ensure_workspace_layout
except ModuleNotFoundError:
    from local_security import require_identifier
    from schema_validation import validate_value_against_schema
    from workspace_store import ensure_workspace_layout


ALLOWED_CERTAINTY = frozenset({
    "high_certainty",
    "medium_possibility",
    "low_certainty_imagination",
})
REQUIRED_STORY_HEADINGS = (
    "## 当年的分叉点",
    "## 不会改变的现实约束",
    "## 选择如何走到今天",
    "## 另一种今天",
    "## Main / Branch",
    "## 回到 Main",
    "### 不能改变的事",
    "### 值得带回的理解",
    "### 一个自主可选的小行动",
)
OBVIOUS_PRIVACY_PATTERNS = {
    "phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "chinese_id": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    "bank_card": re.compile(r"(?<!\d)(?:\d[ -]?){15,18}\d(?!\d)"),
    "credential": re.compile(
        r"(?:\bsk-[A-Za-z0-9_-]{20,}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
    ),
}


def scan_obvious_privacy_leaks(text: str) -> None:
    for label, pattern in OBVIOUS_PRIVACY_PATTERNS.items():
        if pattern.search(text):
            raise ValueError(f"obvious privacy leak: {label}")


def _load_schema(schema_root: Path, name: str) -> dict[str, object]:
    return json.loads((schema_root / name).read_text(encoding="utf-8"))


def _raise_schema_errors(value: dict[str, object], schema: dict[str, object], label: str) -> None:
    errors = validate_value_against_schema(value, schema, {}, label)
    if errors:
        raise ValueError("; ".join(errors))


def validate_metadata_payload(metadata: dict[str, object], schema_root: Path) -> None:
    _raise_schema_errors(metadata, _load_schema(schema_root, "branch-metadata.schema.json"), "metadata")


def _require_non_empty_string(value: object, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"branch {path} must be a non-empty string")


def _require_non_empty_string_items(values: object, path: str) -> None:
    if not isinstance(values, list):
        return
    for index, value in enumerate(values):
        _require_non_empty_string(value, f"{path}[{index}]")


def validate_branch_payload(branch: dict[str, object], schema_root: Path) -> None:
    for field in (
        "turning_point",
        "sensitive_fact_rewrite_attempted",
        "scenario_summary",
        "outcomes",
        "unchanged_constraints",
        "risks",
        "present_day_scenes",
        "main_branch_comparison",
        "merge_back",
    ):
        if field not in branch:
            if field == "sensitive_fact_rewrite_attempted":
                raise ValueError("branch sensitive fact rewrite decision is missing")
            raise ValueError(f"branch missing P1 field: {field}")
    scenes = branch["present_day_scenes"]
    if not isinstance(scenes, list) or len(scenes) != 3:
        raise ValueError("branch must contain exactly three present_day_scenes")
    if branch["sensitive_fact_rewrite_attempted"] is not False:
        raise ValueError("branch sensitive fact rewrite decision must be explicitly safe")
    _raise_schema_errors(branch, _load_schema(schema_root, "branch.schema.json"), "branch")
    if not branch.get("unchanged_constraints"):
        raise ValueError("branch unchanged_constraints must not be empty")

    for field in (
        "branch_name",
        "base_commit",
        "turning_point",
        "alternative_choice",
        "scenario_summary",
        "merge_back_action",
    ):
        _require_non_empty_string(branch[field], field)
    for field in ("diff", "unchanged_constraints", "risks"):
        _require_non_empty_string_items(branch[field], field)
    for index, outcome in enumerate(branch["outcomes"]):
        _require_non_empty_string(outcome["description"], f"outcomes[{index}].description")
        _require_non_empty_string_items(outcome.get("evidence", []), f"outcomes[{index}].evidence")
    for index, scene in enumerate(scenes):
        _require_non_empty_string(scene["title"], f"present_day_scenes[{index}].title")
        _require_non_empty_string(scene["description"], f"present_day_scenes[{index}].description")
    for index, comparison in enumerate(branch["main_branch_comparison"]):
        for field in ("dimension", "main", "branch"):
            _require_non_empty_string(
                comparison[field],
                f"main_branch_comparison[{index}].{field}",
            )
    merge_back = branch["merge_back"]
    for field in ("unchangeable", "understanding", "optional_action"):
        _require_non_empty_string(merge_back[field], f"merge_back.{field}")
    if merge_back["optional_action"] != branch["merge_back_action"]:
        raise ValueError("merge_back optional_action must match merge_back_action")


def _extract_main_branch_section(story: str) -> str:
    main_branch_heading = "## Main / Branch"
    return_to_main_heading = "## 回到 Main"
    main_branch_start = story.find(main_branch_heading)
    return_to_main_start = story.find(return_to_main_heading)
    if main_branch_start == -1 or return_to_main_start == -1 or main_branch_start >= return_to_main_start:
        raise ValueError("story heading order invalid: ## Main / Branch must appear before ## 回到 Main")
    return story[main_branch_start + len(main_branch_heading):return_to_main_start]


def _extract_heading_section(story: str, heading: str) -> str:
    lines = story.splitlines()
    try:
        start = lines.index(heading)
    except ValueError as exc:
        raise ValueError(f"story missing heading: {heading}") from exc
    level = len(heading) - len(heading.lstrip("#"))
    section_lines = []
    for line in lines[start + 1:]:
        match = re.match(r"^(#{1,6})\s", line)
        if match and len(match.group(1)) <= level:
            break
        if not match:
            section_lines.append(line)
    return "\n".join(section_lines).strip()


def validate_story(story: str, branch: dict[str, object]) -> None:
    if not story.startswith("# "):
        raise ValueError("story must start with a level-one title")
    if "这是模拟，不是事实。" not in story:
        raise ValueError("story missing required disclaimer")
    for heading in REQUIRED_STORY_HEADINGS:
        section = _extract_heading_section(story, heading)
        if not section:
            raise ValueError(f"story section lacks substantive text: {heading}")
    scenes = branch["present_day_scenes"]
    for index, scene in enumerate(scenes, start=1):
        heading = f"### 场景 {index}：{scene['title']}"
        if story.count(heading) != 1:
            raise ValueError(f"story must contain scene heading exactly once: {heading}")
        if scene["description"] not in _extract_heading_section(story, heading):
            raise ValueError(f"story scene description does not match scene {index}")
    if len(re.findall(r"^### 场景 \d+：", story, flags=re.MULTILINE)) != 3:
        raise ValueError("story must contain exactly three present-day scene headings")
    if not any(constraint in story for constraint in branch["unchanged_constraints"]):
        raise ValueError("story missing unchanged constraint")
    merge_back = branch["merge_back"]
    for field in ("unchangeable", "understanding", "optional_action"):
        if merge_back[field] not in story:
            raise ValueError(f"story missing merge_back {field}")
    main_branch_section = _extract_main_branch_section(story)
    unrestrained_patterns = (
        r"(?:Main|Branch)\s*(?:是|将是|会是)\s*完美人生",
        r"(?:Main|Branch).{0,20}(?:唯一正确|绝对更好)",
        r"(?:Main|Branch).{0,20}(?:绝对|必然|一定|肯定).{0,12}(?:更好|正确|成功)",
        r"(?:你|用户)\s*(?:应该|必须|应当)",
        r"请(?:照着做|按照|按|务必|选择|行动)",
    )
    if any(re.search(pattern, main_branch_section) for pattern in unrestrained_patterns):
        raise ValueError("story Main / Branch comparison must be restrained and non-directive")
    certainty_words = ("几乎可以确定", "比较可能", "想象")
    if not any(word in story for word in certainty_words):
        raise ValueError("story must express uncertainty")


def validate_package_payload(
    metadata: dict[str, object],
    branch: dict[str, object],
    story: str,
    schema_root: Path,
) -> None:
    scan_obvious_privacy_leaks(json.dumps(metadata, ensure_ascii=False))
    scan_obvious_privacy_leaks(json.dumps(branch, ensure_ascii=False))
    scan_obvious_privacy_leaks(story)
    validate_metadata_payload(metadata, schema_root)
    validate_branch_payload(branch, schema_root)
    validate_story(story, branch)


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_branch_package(
    root: Path,
    branch_id: str,
    metadata: dict[str, object],
    branch: dict[str, object],
    story: str,
    schema_root: Path,
) -> Path:
    require_identifier(branch_id, "branch_id")
    completed = root / "branches" / branch_id
    if completed.exists() or completed.is_symlink():
        raise FileExistsError(f"branch package already exists: {completed}")
    validate_package_payload(metadata, branch, story, schema_root)
    ensure_workspace_layout(root)
    pending_root = root / "branches" / ".pending"
    with tempfile.TemporaryDirectory(prefix=f"{branch_id}_", dir=pending_root) as temporary:
        staged = Path(temporary)
        _write_json(staged / "metadata.json", metadata)
        _write_json(staged / "branch.json", branch)
        (staged / "story.md").write_text(story.rstrip() + "\n", encoding="utf-8")
        os.replace(staged, completed)
    return completed
