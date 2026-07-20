from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any


IDENTIFIER = re.compile(r"^[a-z0-9_]{1,80}$")


def require_identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"invalid {label}: {value!r}")
    return value


def resolve_within(root: Path, relative: str | Path) -> Path:
    relative_path = Path(relative)
    if relative_path.is_absolute():
        raise ValueError("absolute paths are not allowed")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_path).resolve(strict=False)
    if os.path.commonpath([str(resolved_root), str(candidate)]) != str(resolved_root):
        raise ValueError("path escapes workspace")
    return candidate


def load_json_preserving_corrupt(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        recovery = path.with_suffix(path.suffix + ".recovery")
        if not recovery.exists():
            shutil.copy2(path, recovery)
        raise ValueError(f"invalid JSON; recovery copy: {recovery}") from error
