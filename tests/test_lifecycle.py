import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.lifecycle import (
    activate_package,
    rollback_package,
    uninstall_skill,
    verify_package,
)
from scripts.package_manifest import write_public_manifest


def make_package(root: Path, version: str, marker: str) -> Path:
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text("---\nname: lifegit\n---\n", encoding="utf-8")
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    (root / "marker.txt").write_text(marker, encoding="utf-8")
    write_public_manifest(root)
    return root


class LifecycleTests(unittest.TestCase):
    def test_verify_rejects_tampered_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(Path(tmp) / "package", "0.2.0", "new")
            (package / "marker.txt").write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                verify_package(package)

    def test_activate_backs_up_current_skill_and_installs_verified_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            backup = activate_package(package, installed, root / "backups")
            self.assertEqual((installed / "VERSION").read_text().strip(), "0.2.0")
            self.assertEqual((installed / "marker.txt").read_text(), "new")
            self.assertEqual((backup / "marker.txt").read_text(), "old")

    def test_rollback_restores_previous_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.2.0", "new")
            backup = make_package(root / "backups" / "lifegit-0.1.0", "0.1.0", "old")
            displaced = rollback_package(installed, backup)
            self.assertEqual((installed / "marker.txt").read_text(), "old")
            self.assertEqual((displaced / "marker.txt").read_text(), "new")

    def test_uninstall_moves_program_and_preserves_external_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "program")
            data = root / "Documents" / "LifeGit-data"
            data.mkdir(parents=True)
            record = data / "record.txt"
            record.write_text("my life", encoding="utf-8")
            before = record.read_bytes()
            removed = uninstall_skill(installed, root / "backups")
            self.assertFalse(installed.exists())
            self.assertTrue(removed.is_dir())
            self.assertEqual(record.read_bytes(), before)

    def test_activate_restores_old_skill_when_atomic_switch_fails(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            real_replace = lifecycle.os.replace
            calls = 0

            def fail_second_replace(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected switch failure")
                return real_replace(source, target)

            with patch.object(lifecycle.os, "replace", side_effect=fail_second_replace):
                with self.assertRaisesRegex(OSError, "injected switch failure"):
                    activate_package(package, installed, root / "backups")
            self.assertEqual((installed / "marker.txt").read_text(), "old")
            self.assertEqual(list((root / "skills").glob(".lifegit-stage-*")), [])

    def test_rejects_protected_data_roots_and_their_ancestors_without_touching_them(self):
        from scripts import lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            documents = Path.home() / "Documents"
            data = documents / "LifeGit-data"
            with self.assertRaisesRegex(ValueError, "data directories"):
                verify_package(documents)
            with self.assertRaisesRegex(ValueError, "data directories"):
                verify_package(Path.home())
            with self.assertRaisesRegex(ValueError, "data directories"):
                verify_package(data / "..")
            with self.assertRaisesRegex(ValueError, "data directories"):
                activate_package(documents, installed, root / "backups")
            with self.assertRaisesRegex(ValueError, "data directories"):
                activate_package(package, Path.home(), root / "backups")
            with self.assertRaisesRegex(ValueError, "data directories"):
                activate_package(package, installed, Path.home())
            with self.assertRaisesRegex(ValueError, "data directories"):
                rollback_package(installed, documents)
            with self.assertRaisesRegex(ValueError, "data directories"):
                uninstall_skill(installed, Path.home())
            linked_home = root / "linked-home"
            linked_home.symlink_to(Path.home(), target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "data directories"):
                verify_package(linked_home)
            lifecycle._assert_not_data_path(Path.home() / ".codex" / "skills" / "lifegit")
            self.assertEqual((installed / "marker.txt").read_text(), "old")

    def test_protected_data_root_follows_current_home_without_foreign_account_path(self):
        from unittest.mock import patch
        from scripts import lifecycle

        current_home = Path("/").joinpath("Users", "alice")
        foreign_home = Path("/").joinpath("Users", "pika")
        with patch.object(lifecycle.Path, "home", return_value=current_home):
            with self.assertRaisesRegex(ValueError, "data directories"):
                lifecycle._assert_not_data_path(current_home / "Documents")
            lifecycle._assert_not_data_path(foreign_home)

    def test_verify_requires_one_exact_frontmatter_name(self):
        invalid_skills = {
            "prefix": "---\nname: lifegit-evil\n---\n",
            "duplicate": "---\nname: lifegit\nname: lifegit\n---\n",
            "outside": "---\ndescription: lifegit\n---\nname: lifegit\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for label, skill in invalid_skills.items():
                with self.subTest(label=label):
                    package = root / label
                    make_package(package, "0.2.0", "new")
                    (package / "SKILL.md").write_text(skill, encoding="utf-8")
                    write_public_manifest(package)
                    with self.assertRaisesRegex(ValueError, "frontmatter name"):
                        verify_package(package)

    def test_activate_rejects_any_package_installed_backup_overlap_before_mkdir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            backup_inside_package = package / "backup"
            with self.assertRaisesRegex(ValueError, "must not overlap"):
                activate_package(package, installed, backup_inside_package)
            self.assertFalse(backup_inside_package.exists())
            with self.assertRaisesRegex(ValueError, "must not overlap"):
                activate_package(package, installed, package)
            self.assertEqual((installed / "marker.txt").read_text(), "old")

    def test_activate_rejects_package_identity_change_before_switch(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            real_copytree = lifecycle.shutil.copytree

            def replace_package_then_copy(source, target, **kwargs):
                shutil.rmtree(package)
                make_package(package, "0.2.0", "changed")
                return real_copytree(source, target, **kwargs)

            with patch.object(lifecycle.shutil, "copytree", side_effect=replace_package_then_copy):
                with self.assertRaisesRegex(ValueError, "package directory changed"):
                    activate_package(package, installed, root / "backups")
            self.assertEqual((installed / "marker.txt").read_text(), "old")
            self.assertEqual(list((root / "skills").glob(".lifegit-stage-*")), [])

    def test_activate_rejects_stage_symlink_before_switch(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            replacement = root / "replacement"
            replacement.mkdir()
            real_verify = lifecycle.verify_package

            def verify_then_swap_stage(path, **kwargs):
                result = real_verify(path, **kwargs)
                if Path(path).name.startswith(".lifegit-stage-"):
                    shutil.rmtree(path)
                    Path(path).symlink_to(replacement, target_is_directory=True)
                return result

            with patch.object(lifecycle, "verify_package", side_effect=verify_then_swap_stage):
                with self.assertRaisesRegex(OSError, "stage cleanup refused"):
                    activate_package(package, installed, root / "backups")
            self.assertEqual((installed / "marker.txt").read_text(), "old")
            stages = list((root / "skills").glob(".lifegit-stage-*"))
            self.assertEqual(len(stages), 1)
            self.assertTrue(stages[0].is_symlink())

    def test_rejects_hidden_cache_in_manifest_and_stage(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cached = make_package(root / "cached", "0.2.0", "new")
            (cached / ".mypy_cache").mkdir()
            (cached / ".mypy_cache" / "state").write_text("cache", encoding="utf-8")
            write_public_manifest(cached)
            with self.assertRaisesRegex(ValueError, "cache or hidden path"):
                verify_package(cached)

            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            real_copytree = lifecycle.shutil.copytree

            def copy_then_add_cache(source, target, **kwargs):
                result = real_copytree(source, target, **kwargs)
                cache = Path(target) / ".mypy_cache"
                cache.mkdir()
                (cache / "state").write_text("cache", encoding="utf-8")
                return result

            with patch.object(lifecycle.shutil, "copytree", side_effect=copy_then_add_cache):
                with self.assertRaisesRegex(ValueError, "cache or hidden path"):
                    activate_package(package, installed, root / "backups")
            self.assertEqual((installed / "marker.txt").read_text(), "old")
            self.assertEqual(list((root / "skills").glob(".lifegit-stage-*")), [])

    def test_verify_ignores_runtime_bytecode_cache_and_activate_does_not_install_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            cache = package / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "package_manifest.cpython-312.pyc").write_bytes(b"runtime cache")

            self.assertEqual(verify_package(package), "0.2.0")

            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            activate_package(package, installed, root / "backups")
            self.assertFalse((installed / "scripts" / "__pycache__").exists())

    def test_rejects_python_bytecode_in_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = make_package(Path(tmp) / "package", "0.2.0", "new")
            (package / "payload.pyo").write_bytes(b"bytecode")
            write_public_manifest(package)
            with self.assertRaisesRegex(ValueError, "cache or hidden path"):
                verify_package(package)

    def test_activate_excludes_checkout_git_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            (package / ".git").mkdir()
            (package / ".git" / "config").write_text("private", encoding="utf-8")
            activate_package(package, installed, root / "backups")
            self.assertFalse((installed / ".git").exists())

    def test_rollback_failure_restores_displaced_skill(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.2.0", "new")
            backup = make_package(root / "backups" / "lifegit-0.1.0", "0.1.0", "old")
            real_replace = lifecycle.os.replace
            calls = 0

            def fail_second_replace(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected rollback failure")
                return real_replace(source, target)

            with patch.object(lifecycle.os, "replace", side_effect=fail_second_replace):
                with self.assertRaisesRegex(OSError, "injected rollback failure"):
                    rollback_package(installed, backup)
            self.assertEqual((installed / "marker.txt").read_text(), "new")
            self.assertEqual((backup / "marker.txt").read_text(), "old")

    def test_rollback_recovery_failure_reports_manual_recovery_paths(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.2.0", "new")
            backup = make_package(root / "backups" / "lifegit-0.1.0", "0.1.0", "old")
            real_replace = lifecycle.os.replace
            calls = 0

            def fail_switch_and_recovery(source, target):
                nonlocal calls
                calls += 1
                if calls in (2, 3):
                    raise OSError("injected rollback failure")
                return real_replace(source, target)

            with patch.object(lifecycle.os, "replace", side_effect=fail_switch_and_recovery):
                with self.assertRaisesRegex(OSError, "manual recovery.*displaced=.*backup="):
                    rollback_package(installed, backup)
            displaced = next((root / "backups").glob("lifegit-failed-update-*"))
            self.assertFalse(installed.exists())
            self.assertEqual((displaced / "marker.txt").read_text(), "new")
            self.assertEqual((backup / "marker.txt").read_text(), "old")

    def test_uninstall_rejects_backup_root_replaced_with_protected_symlink(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "program")
            backup_root = root / "backups"
            data = root / "LifeGit-data"
            data.mkdir()
            record = data / "record.txt"
            record.write_text("my life", encoding="utf-8")
            real_same_filesystem = lifecycle._require_same_filesystem

            def switch_backup_root(left, right):
                real_same_filesystem(left, right)
                backup_root.rmdir()
                backup_root.symlink_to(data, target_is_directory=True)

            with patch.object(
                lifecycle,
                "_protected_data_roots",
                return_value=(data.resolve(), data.resolve()),
            ):
                with patch.object(
                    lifecycle,
                    "_require_same_filesystem",
                    side_effect=switch_backup_root,
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "data directories|backup root directory changed",
                    ):
                        uninstall_skill(installed, backup_root)
            self.assertEqual((installed / "marker.txt").read_text(), "program")
            self.assertEqual(record.read_text(encoding="utf-8"), "my life")

    def test_activate_rejects_stage_content_change_before_second_move(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            real_verify = lifecycle.verify_package
            stage_verifications = 0

            def verify_then_mutate_stage(path, **kwargs):
                nonlocal stage_verifications
                result = real_verify(path, **kwargs)
                if Path(path).name.startswith(".lifegit-stage-"):
                    stage_verifications += 1
                    if stage_verifications == 1:
                        (Path(path) / "marker.txt").write_text("tampered", encoding="utf-8")
                return result

            with patch.object(lifecycle, "verify_package", side_effect=verify_then_mutate_stage):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    activate_package(package, installed, root / "backups")
            self.assertEqual((installed / "marker.txt").read_text(), "old")
            self.assertEqual(list((root / "skills").glob(".lifegit-stage-*")), [])

    def test_rollback_rejects_backup_content_change_before_second_move(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = make_package(root / "skills" / "lifegit", "0.2.0", "new")
            backup = make_package(root / "backups" / "lifegit-0.1.0", "0.1.0", "old")
            real_verify = lifecycle.verify_package
            backup_verifications = 0

            def verify_then_mutate_backup(path, **kwargs):
                nonlocal backup_verifications
                result = real_verify(path, **kwargs)
                if Path(path).resolve() == backup.resolve():
                    backup_verifications += 1
                    if backup_verifications == 1:
                        (backup / "marker.txt").write_text("tampered", encoding="utf-8")
                return result

            with patch.object(lifecycle, "verify_package", side_effect=verify_then_mutate_backup):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    rollback_package(installed, backup)
            self.assertEqual((installed / "marker.txt").read_text(), "new")
            self.assertEqual((backup / "marker.txt").read_text(), "tampered")

    def test_rejects_existing_full_uuid_targets_without_deleting_them(self):
        from unittest.mock import patch
        import scripts.lifecycle as lifecycle

        class FixedUuid:
            hex = "0" * 32

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backup_root = root / "backups"
            backup_root.mkdir()
            full = "0" * 32
            backup_target = backup_root / f"lifegit-0.1.0-{full}"
            backup_target.mkdir()
            (backup_target / "marker.txt").write_text("keep-backup", encoding="utf-8")
            installed = make_package(root / "skills" / "lifegit", "0.1.0", "old")
            package = make_package(root / "download" / "lifegit", "0.2.0", "new")
            with patch.object(lifecycle.uuid, "uuid4", return_value=FixedUuid()):
                with self.assertRaisesRegex(ValueError, "backup path changed"):
                    activate_package(package, installed, backup_root)
            self.assertEqual((backup_target / "marker.txt").read_text(), "keep-backup")
            self.assertEqual((installed / "marker.txt").read_text(), "old")

            displaced_target = backup_root / f"lifegit-failed-update-{full}"
            displaced_target.mkdir()
            (displaced_target / "marker.txt").write_text("keep-displaced", encoding="utf-8")
            installed = make_package(root / "skills-2" / "lifegit", "0.2.0", "new")
            backup = make_package(backup_root / "lifegit-0.1.0", "0.1.0", "old")
            with patch.object(lifecycle.uuid, "uuid4", return_value=FixedUuid()):
                with self.assertRaisesRegex(ValueError, "displaced path changed"):
                    rollback_package(installed, backup)
            self.assertEqual((displaced_target / "marker.txt").read_text(), "keep-displaced")
            self.assertEqual((installed / "marker.txt").read_text(), "new")

            removed_target = backup_root / f"lifegit-uninstalled-{full}"
            removed_target.mkdir()
            (removed_target / "marker.txt").write_text("keep-removed", encoding="utf-8")
            installed = make_package(root / "skills-3" / "lifegit", "0.1.0", "program")
            with patch.object(lifecycle.uuid, "uuid4", return_value=FixedUuid()):
                with self.assertRaisesRegex(ValueError, "removed path changed"):
                    uninstall_skill(installed, backup_root)
            self.assertEqual((removed_target / "marker.txt").read_text(), "keep-removed")
            self.assertEqual((installed / "marker.txt").read_text(), "program")


if __name__ == "__main__":
    unittest.main()
