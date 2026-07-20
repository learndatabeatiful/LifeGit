import json
import unittest

from scripts.guided_session import load_session
from scripts.share_projection import (
    build_local_projection,
    load_projection,
    save_card_png,
    update_card_copy,
)
from tests.web_test_helpers import LATER, completed_return_day_workspace, png_bytes


class ShareProjectionTests(unittest.TestCase):
    def test_builds_local_ready_projection_from_exact_user_quote(self):
        root = completed_return_day_workspace(self)
        path = build_local_projection(root, "ses_return", LATER)
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(value["stage"], "local_ready")
        self.assertIn(
            {
                "id": "quote_1",
                "text": "那一刻我终于放松下来。",
                "source_type": "exact_quote",
                "source_question_id": "feeling",
            },
            value["core_candidates"],
        )
        self.assertIn("## 当时的感受", value["local_fragment_markdown"])
        self.assertEqual(load_session(root, "ses_return")["status"], "completed")

    def test_user_copy_is_editable_without_changing_source_candidate(self):
        root = completed_return_day_workspace(self)
        build_local_projection(root, "ses_return", LATER)
        update_card_copy(
            root,
            "ses_return",
            {
                "theme_text": "还记得第一次看到海的那一天吗？",
                "core_text": "那一刻我终于放松下来",
                "footer_text": "2026.07.19 · 海边",
            },
            LATER,
        )
        value = load_projection(root, "ses_return")
        self.assertEqual(value["card_copy"]["core_text"], "那一刻我终于放松下来")
        self.assertEqual(value["core_candidates"][0]["source_type"], "exact_quote")
        with self.assertRaises(ValueError):
            update_card_copy(
                root,
                "ses_return",
                {"theme_text": "主题", "core_text": "太" * 49, "footer_text": ""},
                LATER,
            )

    def test_png_export_uses_incrementing_names_and_refuses_wrong_dimensions(self):
        root = completed_return_day_workspace(self)
        build_local_projection(root, "ses_return", LATER)
        first = save_card_png(root, "ses_return", png_bytes(1080, 1350), LATER)
        second = save_card_png(root, "ses_return", png_bytes(1080, 1350), LATER)
        self.assertEqual(first.name, "ses_return-card-v1.png")
        self.assertEqual(second.name, "ses_return-card-v2.png")
        with self.assertRaises(ValueError):
            save_card_png(root, "ses_return", png_bytes(100, 100), LATER)


if __name__ == "__main__":
    unittest.main()
