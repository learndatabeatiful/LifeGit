import json
import tempfile
import unittest
from pathlib import Path

from scripts.guided_session import (
    answer_question,
    complete_session,
    edit_anchor,
    list_sessions,
    load_session,
    next_question,
    pause_session,
    resume_session,
    skip_question,
    start_session,
)
from scripts.workspace_store import initialize_workspace


NOW = "2026-07-19T00:00:00Z"
LATER = "2026-07-19T01:00:00Z"


class GuidedSessionTests(unittest.TestCase):
    def test_load_and_list_sessions_return_fresh_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", NOW)
            start_session(root, "ses_b", "best_today", "晚霞", NOW)
            start_session(root, "ses_a", "return_day", "毕业那天", NOW)
            (root / "sessions" / "ses_a.privacy.json").write_text("{}", encoding="utf-8")

            self.assertEqual(
                [item["session_id"] for item in list_sessions(root)],
                ["ses_a", "ses_b"],
            )
            snapshot = load_session(root, "ses_a")
            snapshot["anchor"] = "只改内存"
            self.assertEqual(load_session(root, "ses_a")["anchor"], "毕业那天")

    def test_skip_pause_and_resume_continue_from_next_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", NOW)
            start_session(root, "ses_today", "best_today", "日落", NOW)
            self.assertEqual(next_question(root, "ses_today")["id"], "scene")
            skip_question(root, "ses_today", "scene", NOW)
            pause_session(root, "ses_today", NOW)
            resume_session(root, "ses_today", LATER)
            self.assertEqual(next_question(root, "ses_today")["id"], "feeling")

    def test_edit_anchor_creates_new_revision_and_marks_result_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", NOW)
            start_session(root, "ses_today", "best_today", "日落", NOW)
            session_path = edit_anchor(root, "ses_today", "和朋友看的日落", LATER)
            session = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(session["anchor"], "和朋友看的日落")
            self.assertEqual(session["revision"], 2)
            self.assertTrue(session["result_stale"])

    def test_rejects_question_outside_the_entry_definition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", NOW)
            start_session(root, "ses_today", "best_today", "日落", NOW)
            with self.assertRaises(ValueError):
                answer_question(root, "ses_today", "fourth_question", "不应保存", NOW)

    def test_return_day_completes_as_private_fragment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", NOW)
            start_session(root, "ses_return", "return_day", "高三毕业那天", NOW)
            answer_question(root, "ses_return", "detail", "下雨的操场", NOW)
            answer_question(root, "ses_return", "feeling", "舍不得", NOW)
            skip_question(root, "ses_return", "today", NOW)
            record_path, output_path = complete_session(root, "ses_return", LATER)
            self.assertEqual(record_path, root / "records" / "rec_session_return.json")
            self.assertEqual(output_path, root / "outputs" / "ses_return.md")
            output = output_path.read_text(encoding="utf-8")
            for heading in ["## 那一天", "## 你记得的那一天", "## 当时的感受", "## 待确认项"]:
                self.assertIn(heading, output)
            self.assertNotIn("## 用户主观回忆", output)
            self.assertNotIn("## 当前理解", output)
            self.assertIn("下雨的操场", output)
            self.assertIn("舍不得", output)
            self.assertIn("今天再看这件事，你想弄清什么？", output)

    def test_future_us_keeps_simulation_separate_from_fact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", NOW)
            start_session(root, "ses_future", "future_us", "留在北京还是回家乡", NOW)
            for question_id in ["constraint", "value", "unknown"]:
                answer_question(root, "ses_future", question_id, "测试回答", NOW)
            _, output_path = complete_session(root, "ses_future", LATER)
            simulation = json.loads((root / "records" / "rec_session_future_simulation.json").read_text(encoding="utf-8"))
            understanding = json.loads((root / "records" / "rec_session_future_understanding.json").read_text(encoding="utf-8"))
            self.assertEqual(simulation["base_record_ids"], ["rec_session_future"])
            self.assertEqual(understanding["simulation_origin_id"], "rec_session_future_simulation")
            self.assertIn("## 选择整理", output_path.read_text(encoding="utf-8"))
            self.assertIn("这是模拟，不是事实。", output_path.read_text(encoding="utf-8"))

    def test_completion_refuses_existing_output_and_repeat_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", NOW)
            start_session(root, "ses_existing", "best_today", "日落", NOW)
            for question_id in ["scene", "feeling", "keep"]:
                answer_question(root, "ses_existing", question_id, "测试回答", NOW)
            output = root / "outputs" / "ses_existing.md"
            output.parent.mkdir(exist_ok=True)
            output.write_text("保留原文", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                complete_session(root, "ses_existing", LATER)
            self.assertEqual(output.read_text(encoding="utf-8"), "保留原文")
