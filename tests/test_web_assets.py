import unittest
from pathlib import Path


WEB = Path(__file__).resolve().parents[1] / "web"


class WebAssetTests(unittest.TestCase):
    def test_index_loads_only_local_module_and_styles(self):
        index = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn('<link rel="stylesheet" href="/styles.css">', index)
        self.assertIn('<script type="module" src="/app.js"></script>', index)
        self.assertNotRegex(index, r"https?://|//cdn\.")

    def test_assets_have_no_external_runtime_dependencies(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in WEB.glob("*")
            if path.suffix in {".html", ".css", ".js"}
        )
        network_references = combined.replace("http://www.w3.org/2000/svg", "")
        self.assertNotRegex(
            network_references,
            r"https?://|@import\s+url|url\(['\"]?//",
        )

    def test_app_defines_four_focused_views_and_four_exits(self):
        app = (WEB / "app.js").read_text(encoding="utf-8")
        for name in [
            "renderEntryView",
            "renderQuestionView",
            "renderCompletionView",
            "renderCardView",
        ]:
            self.assertIn(f"function {name}", app)
        for label in ["生成可分享产物", "模拟不同选择", "回到那一天", "继续扩展"]:
            self.assertIn(label, app)

    def test_user_content_uses_text_content_instead_of_inner_html(self):
        app = (WEB / "app.js").read_text(encoding="utf-8")
        self.assertIn("node.textContent = text", app)
        self.assertNotIn("innerHTML", app)

    def test_ai_actions_require_capability_and_two_stage_privacy_review(self):
        app = (WEB / "app.js").read_text(encoding="utf-8")
        client = (WEB / "api.js").read_text(encoding="utf-8")
        for marker in [
            "requestAiJob",
            "waitForJob",
            "textAiAvailable",
            "imageGenerationAvailable",
            'element("dialog"',
        ]:
            self.assertIn(marker, app)
        self.assertNotIn("window.prompt", app)
        for route in ["privacy-reviews", "confirm", "/api/jobs/"]:
            self.assertIn(route, client)


if __name__ == "__main__":
    unittest.main()
