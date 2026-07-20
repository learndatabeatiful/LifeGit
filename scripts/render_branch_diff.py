#!/usr/bin/env python3
"""Render a LifeGit branch simulation JSON file as Markdown diff."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REQUIRED_DISCLAIMER = "这是模拟，不是事实。"
ALLOWED_CERTAINTY = {
    "high_certainty",
    "medium_possibility",
    "low_certainty_imagination",
}


class RenderError(Exception):
    """Raised when branch JSON cannot be rendered safely."""


def load_json_file(path: Path, label: str = "JSON") -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RenderError(f"invalid {label}: {exc}") from exc
    if not isinstance(data, dict):
        raise RenderError(f"{label} must be an object")
    return data


def load_branch(path: Path) -> dict[str, Any]:
    return load_json_file(path, "branch JSON")


def require_branch_fields(branch: dict[str, Any]) -> None:
    required = [
        "branch_name",
        "base_commit",
        "alternative_choice",
        "disclaimer",
        "scenario_summary",
        "outcomes",
        "diff",
        "unchanged_constraints",
        "merge_back_action",
    ]
    missing = [field for field in required if not branch.get(field)]
    if missing:
        raise RenderError(f"missing required fields: {', '.join(missing)}")
    if branch.get("disclaimer") != REQUIRED_DISCLAIMER:
        raise RenderError("branch missing required disclaimer")
    for index, outcome in enumerate(branch.get("outcomes", []), start=1):
        certainty = outcome.get("certainty") if isinstance(outcome, dict) else None
        if certainty not in ALLOWED_CERTAINTY:
            raise RenderError(f"outcome {index} has invalid certainty: {certainty!r}")



def find_by_id(items: list[dict[str, Any]], item_id: str | None) -> dict[str, Any] | None:
    if not item_id:
        return None
    for item in items:
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    return None


def join_list(items: list[Any], separator: str = ", ") -> str:
    return separator.join(str(item) for item in items) if items else "UNKNOWN"


def build_checkout_context(
    branch: dict[str, Any],
    commit: dict[str, Any] | None = None,
    model: dict[str, Any] | None = None,
) -> dict[str, str]:
    context = {
        "commit": branch.get("base_commit", "UNKNOWN"),
        "date": "UNKNOWN",
        "main_event": "UNKNOWN",
        "user_state": "UNKNOWN",
        "important_people": "UNKNOWN",
        "world_constraints": "see unchanged constraints below",
    }
    if not commit or not model:
        return context

    timeline_node = find_by_id(model.get("timeline", []), commit.get("timeline_node"))
    event_node = find_by_id(model.get("event_graph", []), commit.get("event_id"))

    if timeline_node:
        context["date"] = timeline_node.get("date") or context["date"]
        context["main_event"] = timeline_node.get("event") or context["main_event"]
        context["important_people"] = join_list(timeline_node.get("people", []))
        emotions = timeline_node.get("emotions", [])
        if emotions:
            context["user_state"] = "、".join(str(item) for item in emotions)
    if event_node:
        context["date"] = context["date"] if context["date"] != "UNKNOWN" else event_node.get("date", "UNKNOWN")
        context["main_event"] = context["main_event"] if context["main_event"] != "UNKNOWN" else event_node.get("event", "UNKNOWN")
        if context["important_people"] == "UNKNOWN":
            context["important_people"] = join_list(event_node.get("related_people", []))
    if context["main_event"] == "UNKNOWN" and commit.get("message"):
        context["main_event"] = commit["message"]

    world_constraints = []
    for item in model.get("world_layer", []):
        if not isinstance(item, dict):
            continue
        name = item.get("name_or_token") or item.get("id") or "world"
        summary = item.get("constraint_summary") or item.get("why_it_matters") or "UNKNOWN"
        world_constraints.append(f"{name}：{summary}")
    if world_constraints:
        context["world_constraints"] = "；".join(world_constraints)

    return context

def bullets(items: list[Any]) -> str:
    if not items:
        return "- UNKNOWN"
    return "\n".join(f"- {item}" for item in items)


def render_outcomes(outcomes: list[dict[str, Any]]) -> str:
    lines = ["| 结果 | 依据 | certainty |", "| --- | --- | --- |"]
    for outcome in outcomes:
        evidence = "; ".join(outcome.get("evidence", [])) or "UNKNOWN"
        lines.append(f"| {outcome.get('description', 'UNKNOWN')} | {evidence} | `{outcome.get('certainty')}` |")
    return "\n".join(lines)


def render_branch_diff(branch: dict[str, Any], commit: dict[str, Any] | None = None, model: dict[str, Any] | None = None) -> str:
    require_branch_fields(branch)
    checkout = build_checkout_context(branch, commit, model)
    risks = branch.get("risks", [])
    lines = [
        f"## 分支差异（Branch Diff）：`{branch['branch_name']}` vs `main`",
        "",
        f"> {REQUIRED_DISCLAIMER}",
        "",
        "### Checkout 上下文",
        "",
        f"- Commit：`{checkout['commit']}`",
        f"- 时间：{checkout['date']}",
        f"- 主事件：{checkout['main_event']}",
        f"- 当时状态：{checkout['user_state']}",
        f"- 重要人物：{checkout['important_people']}",
        f"- 世界约束：{checkout['world_constraints']}",
        "",
        "### 分支选择",
        "",
        f"- 替代选择：{branch['alternative_choice']}",
        f"- 为什么这个分支重要：{branch['scenario_summary']}",
        "",
        "### 差异摘要",
        "",
        render_outcomes(branch.get("outcomes", [])),
        "",
        "### 事件图变化",
        "",
        "- 新增事件：",
        bullets(branch.get("diff", [])),
        "- 删除事件：",
        "  - 没有删除现实主线事实；只新增一个模拟分支。",
        "- 改变的后果：",
        bullets(branch.get("diff", [])),
        "- 不变约束：",
        bullets(branch.get("unchanged_constraints", [])),
        "",
        "### 风险与边界",
        "",
        bullets(risks),
        "",
        "### 这个分支带回 main 的东西",
        "",
        "- 洞察：模拟分支用于理解遗憾的结构，而不是证明另一个人生一定更好。",
        "- 边界：他人的真实想法和长期结果仍不可知。",
        f"- 今天可以做的小行动：{branch['merge_back_action']}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a LifeGit branch JSON file as Markdown diff.")
    parser.add_argument("branch_json", type=Path, help="Path to branch JSON file")
    parser.add_argument("--output", type=Path, help="Optional Markdown output path")
    parser.add_argument("--commit", type=Path, help="Optional LifeGit commit JSON used to fill checkout context")
    parser.add_argument("--model", type=Path, help="Optional Life World Model JSON used to fill checkout context")
    args = parser.parse_args(argv)

    try:
        commit = load_json_file(args.commit, "commit JSON") if args.commit else None
        model = load_json_file(args.model, "Life World Model JSON") if args.model else None
        markdown = render_branch_diff(load_branch(args.branch_json), commit=commit, model=model)
    except RenderError as exc:
        print(f"render_branch_diff failed: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
