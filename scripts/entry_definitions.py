from __future__ import annotations

from typing import Any


ENTRIES: dict[str, dict[str, Any]] = {
    "return_day": {
        "id": "return_day",
        "label": "回到那一天",
        "anchor_prompt": "你想回到哪一天或哪个时期？发生了什么？",
        "allows_simulation": False,
        "questions": [
            {"id": "detail", "prompt": "你最想保留或重新理解的细节是什么？", "why": "它能帮助区分真实经历与后来产生的感受。"},
            {"id": "feeling", "prompt": "那时你最强烈的感受是什么？", "why": "它帮助形成回忆层，而不把感受写成事实。"},
            {"id": "today", "prompt": "今天再看这件事，你想弄清什么？", "why": "它帮助形成可修改的当前理解。"},
        ],
    },
    "best_today": {
        "id": "best_today",
        "label": "最好的今天",
        "anchor_prompt": "请用一句话写下你想留住的这个瞬间。",
        "allows_simulation": False,
        "questions": [
            {"id": "scene", "prompt": "当时在哪里，身边有什么？", "why": "它为这个瞬间保留可辨认的场景。"},
            {"id": "feeling", "prompt": "它为什么对你重要？", "why": "它保留你的主观感受，而不强行升华。"},
            {"id": "keep", "prompt": "你最想留住什么？", "why": "它帮助形成未来可回看的线索。"},
        ],
    },
    "future_us": {
        "id": "future_us",
        "label": "后来的我们",
        "anchor_prompt": "你正在比较什么选择？",
        "allows_simulation": True,
        "questions": [
            {"id": "constraint", "prompt": "最现实的期限或约束是什么？", "why": "它让整理建立在现实条件上，而不是预测。"},
            {"id": "value", "prompt": "你最不想失去什么？", "why": "它帮助看清选择背后的价值。"},
            {"id": "unknown", "prompt": "现在最不确定的是什么？", "why": "它会明确待确认项，而不是替你下结论。"},
        ],
    },
}


def entry_ids() -> tuple[str, ...]:
    return tuple(ENTRIES)


def get_entry(entry_id: str) -> dict[str, Any]:
    if entry_id not in ENTRIES:
        raise ValueError(f"unknown entry: {entry_id}")
    return ENTRIES[entry_id]
