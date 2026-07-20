import json
import unittest

from scripts.agent_jobs import (
    claim_next_job,
    complete_job,
    create_job,
    get_job,
    register_capabilities,
)
from scripts.share_projection import build_local_projection
from scripts.web_api import WebApi
from tests.web_test_helpers import (
    LATER,
    NOW,
    completed_return_day_workspace,
    confirmed_review,
    png_bytes,
    temporary_workspace,
)


def request(api, method, path, value=None, content_type="application/json"):
    body = json.dumps(value, ensure_ascii=False).encode() if value is not None else b""
    response = api.dispatch(method, path, body, content_type)
    payload = (
        json.loads(response.body)
        if response.content_type == "application/json"
        else response.body
    )
    return response.status, payload


def completed_web_session(api):
    request(
        api,
        "POST",
        "/api/sessions",
        {"session_id": "ses_web", "entry_id": "return_day", "anchor": "毕业那一天"},
    )
    for question_id, answer in [
        ("detail", "下雨的操场"),
        ("feeling", "那一刻我终于放松下来。"),
        ("today", "想看清改变"),
    ]:
        request(
            api,
            "POST",
            "/api/sessions/ses_web/answers",
            {"question_id": question_id, "answer": answer},
        )
    request(api, "POST", "/api/sessions/ses_web/complete", {})


class WebApiTests(unittest.TestCase):
    def test_image_asset_is_available_only_through_completed_image_job(self):
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
        source = root.parent / "generated.png"
        source.write_bytes(png_bytes(1080, 1350))
        complete_job(root, "job_image", "worker", {"source_path": str(source)}, LATER)
        completed = get_job(root, "job_image")
        api = WebApi(root, lambda: LATER)

        response = api.dispatch("GET", f"/api/jobs/{completed['job_id']}/asset")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "image/png")
        self.assertEqual(response.body[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(api.dispatch("GET", "/api/jobs/job_text/asset").status, 404)

    def test_three_question_flow_completes_to_local_ready(self):
        root = temporary_workspace(self)
        api = WebApi(root, lambda: NOW)
        status, _ = request(
            api,
            "POST",
            "/api/sessions",
            {
                "session_id": "ses_web",
                "entry_id": "return_day",
                "anchor": "毕业那一天",
            },
        )
        self.assertEqual(status, 201)
        for question_id, answer in [
            ("detail", "下雨的操场"),
            ("feeling", "那一刻我终于放松下来。"),
            ("today", "想看清改变"),
        ]:
            status, _ = request(
                api,
                "POST",
                "/api/sessions/ses_web/answers",
                {"question_id": question_id, "answer": answer},
            )
            self.assertEqual(status, 200)
        status, result = request(api, "POST", "/api/sessions/ses_web/complete", {})
        self.assertEqual(status, 201)
        self.assertEqual(result["projection"]["stage"], "local_ready")

    def test_privacy_job_and_export_routes_use_domain_guards(self):
        root = temporary_workspace(self)
        api = WebApi(root, lambda: NOW)
        completed_web_session(api)
        status, preview = request(
            api,
            "POST",
            "/api/sessions/ses_web/privacy-reviews",
            {
                "review_id": "prv_1",
                "fields": {"feeling": "小明让我安心"},
                "redactions": ["小明"],
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(preview["sanitized_fields"]["feeling"], "[PRIVATE_1]让我安心")
        request(
            api,
            "POST",
            "/api/sessions/ses_web/privacy-reviews/prv_1/confirm",
            {},
        )
        register_capabilities(root, {"text_ai": {"available": True}}, NOW)
        status, _ = request(
            api,
            "POST",
            "/api/sessions/ses_web/jobs",
            {
                "job_id": "job_1",
                "kind": "text_enhancement",
                "privacy_review_id": "prv_1",
            },
        )
        self.assertEqual(status, 201)
        response = api.dispatch(
            "POST",
            "/api/sessions/ses_web/card-export",
            png_bytes(1080, 1350),
            "image/png",
        )
        self.assertEqual(response.status, 201)
        self.assertEqual(json.loads(response.body)["filename"], "ses_web-card-v1.png")

    def test_api_maps_bad_ids_missing_files_and_conflicts(self):
        root = temporary_workspace(self)
        api = WebApi(root, lambda: NOW)
        self.assertEqual(request(api, "GET", "/api/sessions/../secret")[0], 400)
        self.assertEqual(request(api, "GET", "/api/sessions/ses_missing")[0], 404)
        self.assertEqual(request(api, "POST", "/api/sessions", {})[0], 400)


if __name__ == "__main__":
    unittest.main()
