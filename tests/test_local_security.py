import unittest

from scripts.local_security import (
    load_json_preserving_corrupt,
    require_identifier,
    resolve_within,
)
from tests.web_test_helpers import temporary_workspace


class LocalSecurityTests(unittest.TestCase):
    def test_identifier_accepts_only_lowercase_safe_ids(self):
        self.assertEqual(require_identifier("ses_20230916", "session_id"), "ses_20230916")
        for value in ["../secret", "/tmp/x", "ses/a", "SES_A", "", "a" * 81]:
            with self.assertRaises(ValueError, msg=value):
                require_identifier(value, "session_id")

    def test_resolve_within_rejects_absolute_parent_and_symlink_escape(self):
        root = temporary_workspace(self)
        outside = root.parent / "outside"
        outside.mkdir()
        (root / "link").symlink_to(outside, target_is_directory=True)
        for relative in ["../outside/x", "/tmp/x", "link/x"]:
            with self.assertRaises(ValueError, msg=relative):
                resolve_within(root, relative)

    def test_invalid_json_keeps_original_and_creates_one_recovery_copy(self):
        root = temporary_workspace(self)
        path = root / "sessions" / "ses_broken.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_json_preserving_corrupt(path)
        recovery = path.with_suffix(".json.recovery")
        self.assertEqual(path.read_text(encoding="utf-8"), "{broken")
        self.assertEqual(recovery.read_text(encoding="utf-8"), "{broken")
        recovery.write_text("保留首次副本", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_json_preserving_corrupt(path)
        self.assertEqual(recovery.read_text(encoding="utf-8"), "保留首次副本")


if __name__ == "__main__":
    unittest.main()
