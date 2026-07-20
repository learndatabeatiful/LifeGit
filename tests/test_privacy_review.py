import json
import unittest

from scripts.guided_session import list_sessions
from scripts.privacy_review import (
    confirm_privacy_review,
    create_privacy_review,
    load_confirmed_payload,
    restore_confirmed_text,
)
from tests.web_test_helpers import LATER, NOW, temporary_workspace


class PrivacyReviewTests(unittest.TestCase):
    def test_preview_replaces_longest_literal_first_and_keeps_map_local(self):
        root = temporary_workspace(self)
        path = create_privacy_review(
            root,
            "ses_a",
            "prv_1",
            {"anchor": "我和小明在上海外国语学校毕业"},
            ["小明", "上海外国语学校", "上海"],
            NOW,
        )
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            value["sanitized_fields"]["anchor"],
            "我和[PRIVATE_2]在[PRIVATE_1]毕业",
        )
        self.assertFalse(value["confirmed"])
        self.assertEqual(list_sessions(root), [])
        with self.assertRaises(ValueError):
            load_confirmed_payload(root, "ses_a", "prv_1")

    def test_confirmation_returns_only_sanitized_fields(self):
        root = temporary_workspace(self)
        create_privacy_review(
            root,
            "ses_a",
            "prv_1",
            {"feeling": "小明让我安心"},
            ["小明"],
            NOW,
        )
        confirm_privacy_review(root, "ses_a", "prv_1", LATER)
        payload = load_confirmed_payload(root, "ses_a", "prv_1")
        self.assertEqual(payload, {"feeling": "[PRIVATE_1]让我安心"})
        self.assertNotIn("小明", json.dumps(payload, ensure_ascii=False))
        self.assertEqual(
            restore_confirmed_text(
                root,
                "ses_a",
                "prv_1",
                "后来，[PRIVATE_1]让我安心。",
            ),
            "后来，小明让我安心。",
        )


if __name__ == "__main__":
    unittest.main()
