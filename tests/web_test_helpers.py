from __future__ import annotations

import binascii
import struct
import tempfile
import zlib
from pathlib import Path


NOW = "2026-07-19T00:00:00Z"
LATER = "2026-07-19T01:00:00Z"


def temporary_workspace(test_case):
    from scripts.workspace_store import initialize_workspace

    temporary = tempfile.TemporaryDirectory()
    test_case.addCleanup(temporary.cleanup)
    root = Path(temporary.name) / "data"
    initialize_workspace(root, "ws_test", NOW)
    return root


def completed_return_day_workspace(test_case, session_id="ses_return"):
    from scripts.guided_session import answer_question, complete_session, start_session

    root = temporary_workspace(test_case)
    start_session(root, session_id, "return_day", "毕业那一天", NOW)
    answer_question(root, session_id, "detail", "下雨的操场", NOW)
    answer_question(root, session_id, "feeling", "那一刻我终于放松下来。", NOW)
    answer_question(root, session_id, "today", "想看清自己如何改变", NOW)
    complete_session(root, session_id, LATER)
    return root


def confirmed_review(root, session_id="ses_return", review_id="prv_1", fields=None, redactions=None):
    from scripts.privacy_review import confirm_privacy_review, create_privacy_review

    create_privacy_review(
        root,
        session_id,
        review_id,
        fields or {"feeling": "那一刻我终于放松下来。"},
        redactions or [],
        NOW,
    )
    confirm_privacy_review(root, session_id, review_id, LATER)


def _chunk(kind, data):
    checksum = binascii.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def png_bytes(width, height):
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    row = b"\x00" + b"\x00" * (width * 4)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(row * height))
        + _chunk(b"IEND", b"")
    )
