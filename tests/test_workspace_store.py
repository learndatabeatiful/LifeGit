import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.workspace_store import (
    export_record,
    ensure_workspace_layout,
    initialize_workspace,
    inspect_delete_impact,
    restore_record,
    save_record,
    trash_record,
)
from scripts.web_cli import prepare_workspace


def record(record_id, layer="fact", **overrides):
    value = {
        "id": record_id,
        "semantic_layer": layer,
        "text": "测试文本",
        "source_refs": ["src_note_001"],
        "status": "user_confirmed",
        "confidence": 0.8,
        "sensitivity": "low",
        "visibility": "private",
        "created_at": "2026-07-17T00:00:00Z",
        "revision": 1,
    }
    value.update(overrides)
    return value


class WorkspaceStoreTests(unittest.TestCase):
    def assert_invalid_workspace_is_untouched(self, root: Path) -> None:
        marker = root / "keep.txt"
        manifest = root / "manifest.json"
        entries_before = {path.relative_to(root) for path in root.rglob("*")}
        directories_before = {
            path.relative_to(root)
            for path in root.rglob("*")
            if path.is_dir() and not path.is_symlink()
        }
        manifest_content_before = manifest.read_bytes()
        manifest_link_before = manifest.readlink() if manifest.is_symlink() else None

        for operation in (
            ensure_workspace_layout,
            lambda path: prepare_workspace(path, "2026-07-20T00:00:00Z"),
        ):
            with self.assertRaises(ValueError):
                operation(root)

        directories_after = {
            path.relative_to(root)
            for path in root.rglob("*")
            if path.is_dir() and not path.is_symlink()
        }
        entries_after = {path.relative_to(root) for path in root.rglob("*")}
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        self.assertEqual(entries_after, entries_before)
        self.assertEqual(directories_after, directories_before)
        self.assertEqual(manifest.read_bytes(), manifest_content_before)
        self.assertEqual(
            manifest.readlink() if manifest.is_symlink() else None,
            manifest_link_before,
        )

    def test_invalid_manifest_is_rejected_without_creating_workspace_files(self):
        manifests = {
            "invalid JSON": "{not JSON",
            "missing required fields": json.dumps({"format_version": "1.0"}),
            "invalid identifier": json.dumps(
                {
                    "format_version": "1.0",
                    "workspace_id": "workspace-id",
                    "created_at": "2026-07-20T00:00:00Z",
                    "record_ids": [],
                    "deleted_record_ids": [],
                }
            ),
            "invalid field type": json.dumps(
                {
                    "format_version": "1.0",
                    "workspace_id": "ws_lifegit",
                    "created_at": "2026-07-20T00:00:00Z",
                    "record_ids": "rec_one",
                    "deleted_record_ids": [],
                }
            ),
            "invalid record id list": json.dumps(
                {
                    "format_version": "1.0",
                    "workspace_id": "ws_lifegit",
                    "created_at": "2026-07-20T00:00:00Z",
                    "record_ids": ["rec_one", "rec_one"],
                    "deleted_record_ids": [],
                }
            ),
            "invalid record identifier": json.dumps(
                {
                    "format_version": "1.0",
                    "workspace_id": "ws_lifegit",
                    "created_at": "2026-07-20T00:00:00Z",
                    "record_ids": ["rec-one"],
                    "deleted_record_ids": [],
                }
            ),
            "overlapping record id lists": json.dumps(
                {
                    "format_version": "1.0",
                    "workspace_id": "ws_lifegit",
                    "created_at": "2026-07-20T00:00:00Z",
                    "record_ids": ["rec_one"],
                    "deleted_record_ids": ["rec_one"],
                }
            ),
        }
        for label, content in manifests.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp) / "occupied"
                    root.mkdir()
                    (root / "keep.txt").write_text("keep", encoding="utf-8")
                    (root / "manifest.json").write_text(content, encoding="utf-8")
                    self.assert_invalid_workspace_is_untouched(root)

    def test_symlink_manifest_is_rejected_without_creating_workspace_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "occupied"
            external = Path(tmp) / "external-manifest.json"
            root.mkdir()
            (root / "keep.txt").write_text("keep", encoding="utf-8")
            external.write_text(
                json.dumps(
                    {
                        "format_version": "1.0",
                        "workspace_id": "ws_lifegit",
                        "created_at": "2026-07-20T00:00:00Z",
                        "record_ids": [],
                        "deleted_record_ids": [],
                    }
                ),
                encoding="utf-8",
            )
            (root / "manifest.json").symlink_to(external)

            self.assert_invalid_workspace_is_untouched(root)

    def test_initializes_manifest_and_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "life-data"
            manifest_path = initialize_workspace(root, "ws_demo", "2026-07-17T00:00:00Z")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["record_ids"], [])
            self.assertTrue((root / "records").is_dir())
            self.assertTrue((root / ".trash" / "records").is_dir())
            self.assertTrue((root / "exports").is_dir())
            for relative in ["sessions", "jobs", "outputs/cards", "outputs/images", "runtime"]:
                self.assertTrue((root / relative).is_dir(), relative)

    def test_initialize_workspace_accepts_existing_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            manifest = initialize_workspace(root, "ws_lifegit", "2026-07-19T00:00:00Z")
            self.assertTrue(manifest.is_file())

    def test_initialize_workspace_refuses_existing_non_workspace_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "occupied"
            root.mkdir()
            marker = root / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "not empty"):
                initialize_workspace(root, "ws_lifegit", "2026-07-19T00:00:00Z")
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_ensure_layout_requires_a_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "empty"
            root.mkdir()
            with self.assertRaises(FileNotFoundError):
                ensure_workspace_layout(root)
            self.assertEqual(list(root.iterdir()), [])

    def test_ensure_layout_upgrades_existing_workspace_without_touching_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "life-data"
            initialize_workspace(root, "ws_demo", "2026-07-17T00:00:00Z")
            marker = root / "records" / "keep.txt"
            marker.write_text("保留", encoding="utf-8")
            for relative in ["jobs", "outputs/cards", "outputs/images", "runtime"]:
                shutil.rmtree(root / relative)

            ensure_workspace_layout(root)

            self.assertEqual(marker.read_text(encoding="utf-8"), "保留")
            self.assertTrue((root / "outputs" / "cards").is_dir())

    def test_save_export_trash_and_restore_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "life-data"
            initialize_workspace(root, "ws_demo", "2026-07-17T00:00:00Z")
            saved = save_record(root, record("rec_fact_a"))
            exported = export_record(root, "rec_fact_a", root / "exports" / "rec_fact_a.json")
            trashed = trash_record(root, "rec_fact_a", "2026-07-17T01:00:00Z")
            self.assertTrue(trashed.exists())
            restored = restore_record(root, "rec_fact_a")
            self.assertTrue(saved.exists())
            self.assertTrue(exported.exists())
            self.assertTrue(restored.exists())

    def test_delete_impact_lists_referencing_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "life-data"
            initialize_workspace(root, "ws_demo", "2026-07-17T00:00:00Z")
            save_record(root, record("rec_fact_a"))
            save_record(root, record("rec_sim_a", "simulation", status="inferred", base_record_ids=["rec_fact_a"]))
            impacts = inspect_delete_impact(root, "rec_fact_a")
            self.assertEqual(impacts, ["rec_sim_a"])

    def test_export_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "life-data"
            initialize_workspace(root, "ws_demo", "2026-07-17T00:00:00Z")
            save_record(root, record("rec_fact_a"))
            target = root / "exports" / "rec_fact_a.json"
            export_record(root, "rec_fact_a", target)
            with self.assertRaises(FileExistsError):
                export_record(root, "rec_fact_a", target)
