import json
import tempfile
import unittest
from pathlib import Path

from scripts.text_branch_session import load_confirmed_input, save_confirmed_input
from scripts.workspace_store import initialize_workspace


class TextBranchSessionTests(unittest.TestCase):
    def test_saves_only_explicit_current_confirmed_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            path = save_confirmed_input(
                root=root,
                session_id="ses_text_001",
                sanitized_turning_point="当年是否购买 ITEM_001",
                alternative_choice="暂缓购买",
                reality_state="当时收入稳定但缓冲较少",
                unchanged_constraints=["家庭责任仍在"],
                desired_today_change="想看今天的安全感是否不同",
                privacy_mode="manual",
                user_redaction_list=["原商品名"],
                privacy_confirmed=True,
                sensitive_fact_rewrite_attempted=False,
                confirmed_at="2026-07-31T10:00:00+08:00",
            )
            saved = path.read_text(encoding="utf-8")
            self.assertNotIn("原商品名", saved)
            self.assertNotIn("ru" + "ns/", saved)
            self.assertIs(
                load_confirmed_input(root, "ses_text_001")["sensitive_fact_rewrite_attempted"],
                False,
            )
            self.assertEqual(load_confirmed_input(root, "ses_text_001")["question_count"], 3)

    def test_rejects_attempted_or_unknown_sensitive_fact_rewrite_before_ready_save(self):
        for decision in (True, None):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "data"
                initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
                with self.assertRaisesRegex(ValueError, "sensitive fact rewrite"):
                    save_confirmed_input(
                        root=root,
                        session_id="ses_sensitive",
                        sanitized_turning_point="一次选择",
                        alternative_choice="另一选择",
                        reality_state=None,
                        unchanged_constraints=["死亡事实不会改变"],
                        desired_today_change=None,
                        privacy_mode="manual",
                        user_redaction_list=[],
                        privacy_confirmed=True,
                        sensitive_fact_rewrite_attempted=decision,
                        confirmed_at="2026-07-31T10:00:00+08:00",
                    )
                self.assertFalse((root / "sessions" / "ses_sensitive.text-branch.json").exists())

    def test_load_rejects_tampered_unsafe_or_missing_sensitive_fact_decision(self):
        for decision in (True, None):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "data"
                initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
                payload = {
                    "session_id": "ses_tampered",
                    "privacy_confirmed": True,
                    "generation_status": "ready",
                }
                if decision is not None:
                    payload["sensitive_fact_rewrite_attempted"] = decision
                (root / "sessions" / "ses_tampered.text-branch.json").write_text(
                    json.dumps(payload),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "sensitive fact rewrite"):
                    load_confirmed_input(root, "ses_tampered")

    def test_allows_skipped_questions_without_adding_more(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            save_confirmed_input(root, "ses_text_002", "一次选择", "另一选择", None, [], None, "manual", [], True, False, "2026-07-31T10:00:00+08:00")
            saved = load_confirmed_input(root, "ses_text_002")
            self.assertEqual(saved["question_count"], 0)
            self.assertIsNone(saved["reality_state"])

    def test_rejects_obvious_high_risk_text_before_model_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            with self.assertRaisesRegex(ValueError, "phone"):
                save_confirmed_input(root, "ses_text_003", "手机号 " + "13800" + "138000", "不改变", None, [], None, "manual", [], True, False, "2026-07-31T10:00:00+08:00")

    def test_rejects_private_path_references_in_all_persisted_user_fields(self):
        cases = {
            "sanitized_turning_point": "参考 ru" + "ns/raw-input.json",
            "alternative_choice": "读取 sess" + "ions/ses_text_old",
            "reality_state": "来自 ru" + "ns/raw-input.json",
            "unchanged_constraints": ["保留 sess" + "ions/ses_text_old"],
            "desired_today_change": "比较 ru" + "ns/raw-input.json",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "data"
                    initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
                    args = {
                        "root": root,
                        "session_id": "ses_text_path",
                        "sanitized_turning_point": "一次选择",
                        "alternative_choice": "另一选择",
                        "reality_state": "当时的现实",
                        "unchanged_constraints": ["家庭责任仍在"],
                        "desired_today_change": "今天的感受",
                        "privacy_mode": "manual",
                        "user_redaction_list": [],
                        "privacy_confirmed": True,
                        "sensitive_fact_rewrite_attempted": False,
                        "confirmed_at": "2026-07-31T10:00:00+08:00",
                    }
                    args[field] = value
                    with self.assertRaisesRegex(ValueError, "private path reference"):
                        save_confirmed_input(**args)

    def test_allows_ordinary_prose_that_mentions_runs_without_path_syntax(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            path = save_confirmed_input(
                root, "ses_text_prose", "一次选择", "另一选择", None, [],
                "今天只是在讨论 runs 这个英文词", "manual", [], True, False,
                "2026-07-31T10:00:00+08:00",
            )
            self.assertTrue(path.is_file())

    def test_rejects_chinese_id_before_model_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            with self.assertRaisesRegex(ValueError, "chinese_id"):
                save_confirmed_input(root, "ses_text_id", "身份证 " + "110101199" + "003078417", "不改变", None, [], None, "manual", [], True, False, "2026-07-31T10:00:00+08:00")

    def test_rejects_bank_card_before_model_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            with self.assertRaisesRegex(ValueError, "bank_card"):
                save_confirmed_input(root, "ses_text_card", "卡号 6222021234567890", "不改变", None, [], None, "manual", [], True, False, "2026-07-31T10:00:00+08:00")

    def test_rejects_missing_explicit_privacy_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            with self.assertRaisesRegex(ValueError, "privacy confirmation"):
                save_confirmed_input(root, "ses_text_005", "一次选择", "另一选择", None, [], None, "manual", [], False, False, "2026-07-31T10:00:00+08:00")

    def test_refuses_to_overwrite_a_confirmed_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "data"
            initialize_workspace(root, "ws_demo", "2026-07-31T10:00:00+08:00")
            args = (root, "ses_text_004", "一次选择", "另一选择", None, [], None, "manual", [], True, False, "2026-07-31T10:00:00+08:00")
            save_confirmed_input(*args)
            with self.assertRaises(FileExistsError):
                save_confirmed_input(*args)
