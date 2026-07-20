import unittest
from pathlib import Path

from scripts.agent_jobs import (
    claim_next_job,
    complete_job,
    create_job,
    fail_job,
    get_job,
    register_capabilities,
)
from scripts.privacy_review import create_privacy_review
from scripts.share_projection import build_local_projection, load_projection
from tests.web_test_helpers import (
    LATER,
    NOW,
    completed_return_day_workspace,
    confirmed_review,
    png_bytes,
)


class AgentJobsTests(unittest.TestCase):
    def test_completed_text_job_enhances_projection_without_replacing_exact_quote(self):
        root = completed_return_day_workspace(self)
        build_local_projection(root, "ses_return", LATER)
        confirmed_review(root, "ses_return")
        register_capabilities(root, {"text_ai": {"available": True}}, NOW)
        create_job(root, "job_text", "ses_return", "text_enhancement", "prv_1", NOW)
        self.assertEqual(load_projection(root, "ses_return")["stage"], "awaiting_agent")
        claim_next_job(root, "worker", NOW, "2026-07-19T00:01:00Z")
        result = {
            "fragment_markdown": "# 更自然的私密片段",
            "core_candidates": [
                {
                    "text": "我的人生从那一天开始绚烂。",
                    "source_type": "light_edit",
                }
            ],
        }
        complete_job(root, "job_text", "worker", result, LATER)
        complete_job(root, "job_text", "worker", result, LATER)
        projection = load_projection(root, "ses_return")
        self.assertEqual(projection["stage"], "ready")
        self.assertEqual(projection["pending_job_ids"], [])
        self.assertEqual(projection["ai_job_ids"], ["job_text"])
        self.assertTrue(
            any(item["source_type"] == "exact_quote" for item in projection["core_candidates"])
        )
        self.assertTrue(
            any(
                item["text"] == "我的人生从那一天开始绚烂。"
                for item in projection["core_candidates"]
            )
        )

    def test_completed_image_job_copies_background_and_sets_ai_marker(self):
        root = completed_return_day_workspace(self)
        build_local_projection(root, "ses_return", LATER)
        confirmed_review(root, "ses_return")
        register_capabilities(
            root,
            {
                "image_generation": {
                    "available": True,
                    "provider": "test-imagegen",
                    "model_id": None,
                }
            },
            NOW,
        )
        create_job(root, "job_image", "ses_return", "image_background", "prv_1", NOW)
        claim_next_job(root, "worker", NOW, "2026-07-19T00:01:00Z")
        source_png = root.parent / "agent-image.png"
        source_png.write_bytes(png_bytes(1080, 1350))
        complete_job(root, "job_image", "worker", {"source_path": str(source_png)}, LATER)
        projection = load_projection(root, "ses_return")
        self.assertTrue(Path(projection["background_image"]["path"]).is_file())
        self.assertTrue(projection["background_image"]["ai_generated"])

    def test_non_retryable_failure_returns_to_usable_local_projection(self):
        root = completed_return_day_workspace(self)
        build_local_projection(root, "ses_return", LATER)
        confirmed_review(root, "ses_return")
        register_capabilities(root, {"text_ai": {"available": True}}, NOW)
        create_job(root, "job_failed", "ses_return", "text_enhancement", "prv_1", NOW)
        claim_next_job(root, "worker", NOW, "2026-07-19T00:01:00Z")
        fail_job(
            root,
            "job_failed",
            "worker",
            "tool_unavailable",
            "工具不可用",
            False,
            LATER,
        )
        self.assertEqual(load_projection(root, "ses_return")["stage"], "local_ready")

    def test_text_job_requires_confirmed_privacy_review(self):
        root = completed_return_day_workspace(self, "ses_a")
        build_local_projection(root, "ses_a", LATER)
        create_privacy_review(root, "ses_a", "prv_1", {"anchor": "测试"}, [], NOW)
        register_capabilities(root, {"text_ai": {"available": True}}, NOW)
        with self.assertRaises(ValueError):
            create_job(root, "job_1", "ses_a", "text_enhancement", "prv_1", NOW)

    def test_capabilities_require_explicit_boolean_availability(self):
        root = completed_return_day_workspace(self, "ses_a")
        with self.assertRaises(ValueError):
            register_capabilities(root, {"text_ai": {"available": "yes"}}, NOW)

    def test_expired_claim_can_be_recovered_and_completion_is_idempotent(self):
        root = completed_return_day_workspace(self, "ses_a")
        build_local_projection(root, "ses_a", LATER)
        confirmed_review(root, "ses_a")
        register_capabilities(root, {"text_ai": {"available": True}}, NOW)
        create_job(root, "job_1", "ses_a", "text_enhancement", "prv_1", NOW)
        claim_next_job(root, "worker_a", NOW, "2026-07-19T00:00:30Z")
        recovered = claim_next_job(
            root,
            "worker_b",
            "2026-07-19T00:00:31Z",
            "2026-07-19T00:01:00Z",
        )
        self.assertEqual(recovered["worker_id"], "worker_b")
        result = {
            "fragment_markdown": "# 私密片段",
            "core_candidates": [
                {
                    "text": "那一刻我终于放松下来。",
                    "source_type": "exact_quote",
                }
            ],
        }
        first = complete_job(root, "job_1", "worker_b", result, LATER)
        second = complete_job(root, "job_1", "worker_b", result, LATER)
        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            complete_job(
                root,
                "job_1",
                "worker_b",
                {**result, "fragment_markdown": "冲突"},
                LATER,
            )

    def test_image_job_is_rejected_without_image_capability(self):
        root = completed_return_day_workspace(self, "ses_a")
        build_local_projection(root, "ses_a", LATER)
        confirmed_review(root, "ses_a")
        register_capabilities(
            root,
            {
                "text_ai": {"available": True},
                "image_generation": {
                    "available": False,
                    "provider": None,
                    "model_id": None,
                },
            },
            NOW,
        )
        with self.assertRaises(ValueError):
            create_job(root, "job_img", "ses_a", "image_background", "prv_1", NOW)

    def test_image_completion_rejects_a_fake_png(self):
        root = completed_return_day_workspace(self, "ses_a")
        build_local_projection(root, "ses_a", LATER)
        confirmed_review(root, "ses_a")
        register_capabilities(
            root,
            {
                "image_generation": {
                    "available": True,
                    "provider": "test-imagegen",
                    "model_id": None,
                }
            },
            NOW,
        )
        create_job(root, "job_img", "ses_a", "image_background", "prv_1", NOW)
        claim_next_job(root, "worker", NOW, "2026-07-19T00:01:00Z")
        source = root.parent / "fake.png"
        source.write_bytes(b"not an image")
        with self.assertRaises(ValueError):
            complete_job(root, "job_img", "worker", {"source_path": str(source)}, LATER)

    def test_text_completion_restores_private_placeholders_after_agent_returns(self):
        root = completed_return_day_workspace(self, "ses_a")
        build_local_projection(root, "ses_a", LATER)
        confirmed_review(
            root,
            "ses_a",
            fields={"feeling": "小明让我安心"},
            redactions=["小明"],
        )
        register_capabilities(root, {"text_ai": {"available": True}}, NOW)
        create_job(root, "job_private", "ses_a", "text_enhancement", "prv_1", NOW)
        claim_next_job(root, "worker", NOW, "2026-07-19T00:01:00Z")
        complete_job(
            root,
            "job_private",
            "worker",
            {
                "fragment_markdown": "[PRIVATE_1]让我安心",
                "core_candidates": [
                    {"text": "谢谢[PRIVATE_1]。", "source_type": "light_edit"}
                ],
            },
            LATER,
        )
        result = get_job(root, "job_private")["result"]
        self.assertEqual(result["fragment_markdown"], "小明让我安心")
        self.assertEqual(result["core_candidates"][0]["text"], "谢谢小明。")

    def test_text_completion_rejects_a_false_exact_quote(self):
        root = completed_return_day_workspace(self, "ses_a")
        build_local_projection(root, "ses_a", LATER)
        confirmed_review(root, "ses_a")
        register_capabilities(root, {"text_ai": {"available": True}}, NOW)
        create_job(root, "job_false", "ses_a", "text_enhancement", "prv_1", NOW)
        claim_next_job(root, "worker", NOW, "2026-07-19T00:01:00Z")
        with self.assertRaises(ValueError):
            complete_job(
                root,
                "job_false",
                "worker",
                {
                    "fragment_markdown": "整理",
                    "core_candidates": [
                        {"text": "用户从未说过的话", "source_type": "exact_quote"}
                    ],
                },
                LATER,
            )


if __name__ == "__main__":
    unittest.main()
