from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
from pathlib import Path

try:
    from scripts.package_manifest import verify_public_manifest
except ModuleNotFoundError:
    from package_manifest import verify_public_manifest


_COPY_IGNORE = shutil.ignore_patterns(".git")
_VERSION = re.compile(r"\d+(?:\.\d+)*")
_FRONTMATTER_FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$")


def _protected_data_roots() -> tuple[Path, Path]:
    return (
        (Path.home() / "Documents" / "LifeGit-data").resolve(),
        Path("/").joinpath("Users", "pika", "LifeGit-data").resolve(),
    )


def _assert_not_data_path(path: Path) -> None:
    path = path.resolve()
    for data_root in _protected_data_roots():
        try:
            path.relative_to(data_root)
        except ValueError:
            try:
                data_root.relative_to(path)
            except ValueError:
                continue
        raise ValueError("LifeGit data directories are never managed by lifecycle")


def _resolve_path(value: Path) -> Path:
    path = Path(value).expanduser()
    _assert_not_data_path(path.absolute())
    if path.is_symlink():
        raise ValueError(f"symbolic-link lifecycle path is not allowed: {path}")
    resolved = path.resolve()
    _assert_not_data_path(resolved)
    return resolved


def _require_directory(value: Path, label: str) -> Path:
    path = _resolve_path(value)
    if not path.is_dir():
        raise FileNotFoundError(f"{label} not found: {path}")
    _validate_package_tree(path, allow_root_git=True)
    return path


def _validate_package_tree(root: Path, allow_root_git: bool) -> None:
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if allow_root_git and relative.parts[0] == ".git":
            continue
        if path.is_symlink():
            raise ValueError(f"symbolic links are not allowed in a LifeGit package: {path}")
        for part in relative.parts:
            if part == ".github":
                continue
            if part.startswith(".") or part == "__pycache__":
                raise ValueError(f"cache or hidden path is not allowed: {relative}")
        if path.is_file() and path.suffix in {".pyc", ".pyo"}:
            raise ValueError(f"cache or hidden path is not allowed: {relative}")


def _ensure_distinct_trees(left: Path, right: Path) -> None:
    try:
        left.relative_to(right)
    except ValueError:
        pass
    else:
        raise ValueError("lifecycle paths must not overlap")
    try:
        right.relative_to(left)
    except ValueError:
        return
    raise ValueError("lifecycle paths must not overlap")


def _require_distinct_trees(*paths: Path) -> None:
    for index, left in enumerate(paths):
        for right in paths[index + 1:]:
            _ensure_distinct_trees(left, right)


def _directory_identity(path: Path, label: str) -> tuple[int, int]:
    try:
        result = os.lstat(path)
    except FileNotFoundError as error:
        raise ValueError(f"{label} directory changed: {path}") from error
    if stat.S_ISLNK(result.st_mode) or not stat.S_ISDIR(result.st_mode):
        raise ValueError(f"{label} directory changed: {path}")
    return result.st_dev, result.st_ino


def _confirm_directory_identity(path: Path, expected: tuple[int, int], label: str) -> None:
    if _directory_identity(path, label) != expected:
        raise ValueError(f"{label} directory changed: {path}")


def _confirm_absent(path: Path, label: str) -> None:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return
    raise ValueError(f"{label} path changed: {path}")


def _frontmatter_name(skill: str) -> str:
    lines = skill.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("package frontmatter name must be exactly lifegit")
    end = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() in {"---", "..."}),
        None,
    )
    if end is None:
        raise ValueError("package frontmatter name must be exactly lifegit")
    names: list[str] = []
    for line in lines[1:end]:
        field = _FRONTMATTER_FIELD.match(line)
        if field is not None and field.group(1) == "name":
            value = field.group(2)
            if value[:1] in {"'", '"'} and value[-1:] == value[:1]:
                value = value[1:-1]
            names.append(value)
    if len(names) != 1 or names[0] != "lifegit":
        raise ValueError("package frontmatter name must be exactly lifegit")
    return names[0]


def verify_package(package_root: Path, allow_root_git: bool = True) -> str:
    package_root = _require_directory(package_root, "LifeGit package")
    _validate_package_tree(package_root, allow_root_git=allow_root_git)
    manifest = verify_public_manifest(package_root)
    skill = (package_root / "SKILL.md").read_text(encoding="utf-8")
    _frontmatter_name(skill)
    version = manifest["version"]
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ValueError("VERSION must use numeric form without a v prefix")
    return version


def _unique_child(root: Path, name: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{name}-{uuid.uuid4().hex}"


def _require_same_filesystem(left: Path, right: Path) -> None:
    right.mkdir(parents=True, exist_ok=True)
    if os.stat(left).st_dev != os.stat(right).st_dev:
        raise ValueError("installed skill and backup directory must share a filesystem")


def _remove_stage(stage: Path, expected: tuple[int, int]) -> None:
    try:
        _confirm_directory_identity(stage, expected, "stage")
    except ValueError as error:
        raise OSError(f"stage cleanup refused because it changed: {stage}") from error
    shutil.rmtree(stage)


def activate_package(package_root: Path, installed_root: Path, backup_root: Path) -> Path:
    package_root = _require_directory(package_root, "LifeGit package")
    verify_package(package_root)
    installed_root = _require_directory(installed_root, "installed LifeGit skill")
    backup_root = _resolve_path(backup_root)
    _require_distinct_trees(package_root, installed_root, backup_root)
    current_version = verify_package(installed_root)
    _require_same_filesystem(installed_root.parent, backup_root)
    package_identity = _directory_identity(package_root, "package")
    installed_identity = _directory_identity(installed_root, "installed")
    backup_root_identity = _directory_identity(backup_root, "backup root")
    stage = Path(tempfile.mkdtemp(prefix=".lifegit-stage-", dir=installed_root.parent))
    stage_identity = _directory_identity(stage, "stage")
    backup = _unique_child(backup_root, f"lifegit-{current_version}")
    moved_current = False
    backup_identity: tuple[int, int] | None = None
    failure: Exception | None = None
    try:
        shutil.copytree(
            package_root,
            stage,
            ignore=_COPY_IGNORE,
            dirs_exist_ok=True,
        )
        verify_package(stage, allow_root_git=False)
        _confirm_directory_identity(package_root, package_identity, "package")
        _confirm_directory_identity(installed_root, installed_identity, "installed")
        _confirm_directory_identity(stage, stage_identity, "stage")
        _confirm_directory_identity(backup_root, backup_root_identity, "backup root")
        _confirm_absent(backup, "backup")
        os.replace(installed_root, backup)
        moved_current = True
        backup_identity = _directory_identity(backup, "backup")
        verify_package(stage, allow_root_git=False)
        _confirm_directory_identity(package_root, package_identity, "package")
        _confirm_directory_identity(stage, stage_identity, "stage")
        _confirm_directory_identity(backup_root, backup_root_identity, "backup root")
        _confirm_directory_identity(backup, backup_identity, "backup")
        _confirm_absent(installed_root, "installed")
        os.replace(stage, installed_root)
        return backup
    except Exception as error:
        failure = error
        cleanup_error: OSError | None = None
        try:
            _remove_stage(stage, stage_identity)
        except OSError as cleanup_failure:
            cleanup_error = cleanup_failure
        if moved_current and backup_identity is not None:
            try:
                _confirm_directory_identity(backup, backup_identity, "backup")
                _confirm_absent(installed_root, "installed")
                os.replace(backup, installed_root)
            except Exception as recovery_error:
                raise OSError(
                    f"activation recovery failed; manual recovery: backup={backup}"
                ) from recovery_error
        if cleanup_error is not None:
            raise cleanup_error from failure
        raise


def rollback_package(installed_root: Path, backup_path: Path) -> Path:
    installed_root = _require_directory(installed_root, "installed LifeGit skill")
    backup_path = _require_directory(backup_path, "LifeGit backup")
    _ensure_distinct_trees(installed_root, backup_path)
    verify_package(installed_root)
    verify_package(backup_path)
    _require_same_filesystem(installed_root.parent, backup_path.parent)
    installed_identity = _directory_identity(installed_root, "installed")
    backup_identity = _directory_identity(backup_path, "backup")
    backup_root_identity = _directory_identity(backup_path.parent, "backup root")
    displaced = _unique_child(backup_path.parent, "lifegit-failed-update")
    moved_current = False
    displaced_identity: tuple[int, int] | None = None
    try:
        _confirm_directory_identity(installed_root, installed_identity, "installed")
        _confirm_directory_identity(backup_path, backup_identity, "backup")
        _confirm_directory_identity(backup_path.parent, backup_root_identity, "backup root")
        _confirm_absent(displaced, "displaced")
        os.replace(installed_root, displaced)
        moved_current = True
        displaced_identity = _directory_identity(displaced, "displaced")
        verify_package(backup_path)
        _confirm_directory_identity(displaced, displaced_identity, "displaced")
        _confirm_directory_identity(backup_path, backup_identity, "backup")
        _confirm_directory_identity(backup_path.parent, backup_root_identity, "backup root")
        _confirm_absent(installed_root, "installed")
        os.replace(backup_path, installed_root)
        return displaced
    except Exception as error:
        if moved_current and displaced_identity is not None:
            try:
                _confirm_directory_identity(displaced, displaced_identity, "displaced")
                _confirm_directory_identity(backup_path, backup_identity, "backup")
                _confirm_absent(installed_root, "installed")
                os.replace(displaced, installed_root)
            except Exception as recovery_error:
                raise OSError(
                    "rollback recovery failed; manual recovery: "
                    f"displaced={displaced} backup={backup_path}"
                ) from recovery_error
        raise


def uninstall_skill(installed_root: Path, backup_root: Path) -> Path:
    installed_root = _require_directory(installed_root, "installed LifeGit skill")
    backup_root = _resolve_path(backup_root)
    _ensure_distinct_trees(installed_root, backup_root)
    verify_package(installed_root)
    _require_same_filesystem(installed_root.parent, backup_root)
    installed_identity = _directory_identity(installed_root, "installed")
    backup_root_identity = _directory_identity(backup_root, "backup root")
    removed = _unique_child(backup_root, "lifegit-uninstalled")
    _assert_not_data_path(installed_root)
    _assert_not_data_path(backup_root)
    _ensure_distinct_trees(installed_root, backup_root)
    verify_package(installed_root)
    _confirm_directory_identity(installed_root, installed_identity, "installed")
    _confirm_directory_identity(backup_root, backup_root_identity, "backup root")
    _confirm_absent(removed, "removed")
    os.replace(installed_root, removed)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and switch LifeGit Skill versions.")
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--package", type=Path, required=True)
    activate = sub.add_parser("activate")
    activate.add_argument("--package", type=Path, required=True)
    activate.add_argument("--installed", type=Path, required=True)
    activate.add_argument("--backups", type=Path, required=True)
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--installed", type=Path, required=True)
    rollback.add_argument("--backup", type=Path, required=True)
    uninstall = sub.add_parser("uninstall")
    uninstall.add_argument("--installed", type=Path, required=True)
    uninstall.add_argument("--backups", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        result = {"status": "verified", "version": verify_package(args.package)}
    elif args.command == "activate":
        result = {
            "status": "activated",
            "backup": str(activate_package(args.package, args.installed, args.backups)),
        }
    elif args.command == "rollback":
        result = {
            "status": "rolled_back",
            "displaced": str(rollback_package(args.installed, args.backup)),
        }
    else:
        result = {
            "status": "uninstalled",
            "backup": str(uninstall_skill(args.installed, args.backups)),
        }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
