import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.agent_jobs import create_job, register_capabilities
from scripts.share_projection import build_local_projection
from scripts.web_cli import (
    DEFAULT_WORKSPACE,
    build_parser,
    main,
    next_job_with_wait,
    prepare_workspace,
    runtime_status,
)
from tests.web_test_helpers import (
    LATER,
    NOW,
    completed_return_day_workspace,
    confirmed_review,
    temporary_workspace,
)


def command_required_args(command):
    return {
        "serve": [],
        "status": [],
        "register-capabilities": ["--input", "/tmp/capabilities.json"],
        "next-job": ["--worker", "worker"],
        "complete-job": [
            "--worker",
            "worker",
            "--job-id",
            "job_1",
            "--result",
            "/tmp/result.json",
        ],
        "fail-job": [
            "--worker",
            "worker",
            "--job-id",
            "job_1",
            "--code",
            "tool_error",
            "--message",
            "失败",
        ],
    }[command]


def fake_clock():
    return NOW


class WebCliTests(unittest.TestCase):
    def test_prepare_workspace_initializes_then_reuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "LifeGit-data"
            first = prepare_workspace(root, "2026-07-19T00:00:00Z")
            marker = root / "exports" / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            second = prepare_workspace(root, "2026-07-19T00:01:00Z")
            self.assertEqual(first, second)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_serve_parser_uses_default_workspace_when_omitted(self):
        args = build_parser().parse_args(["serve"])
        self.assertEqual(args.workspace, DEFAULT_WORKSPACE)

    def test_bridge_commands_require_workspace_when_omitted(self):
        parser = build_parser()
        for command in [
            "status",
            "register-capabilities",
            "next-job",
            "complete-job",
            "fail-job",
        ]:
            with self.subTest(command=command):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        parser.parse_args([command] + command_required_args(command))

    def test_serve_expands_workspace_before_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            expected = (home / "LifeGit-data").resolve()
            with patch.dict(os.environ, {"HOME": str(home)}):
                with patch("scripts.web_cli.prepare_workspace") as prepare:
                    with patch(
                        "scripts.web_cli.runtime_status",
                        return_value={"status": "running", "port": 8765, "token": "token"},
                    ):
                        with patch("sys.argv", ["web_cli.py", "serve", "--workspace", "~/LifeGit-data"]):
                            with redirect_stdout(io.StringIO()):
                                self.assertEqual(main(), 0)
            self.assertEqual(prepare.call_args.args[0], expected)

    def test_parser_exposes_exact_bridge_commands(self):
        root = temporary_workspace(self)
        parser = build_parser()
        for command in [
            "serve",
            "status",
            "register-capabilities",
            "next-job",
            "complete-job",
            "fail-job",
        ]:
            namespace = parser.parse_args(
                [command, "--workspace", str(root)] + command_required_args(command)
            )
            self.assertEqual(namespace.command, command)

    def test_status_rejects_stale_pid_or_closed_port(self):
        root = temporary_workspace(self)
        (root / "runtime" / "web.json").write_text(
            json.dumps(
                {
                    "host": "127.0.0.1",
                    "port": 9,
                    "token": "secret",
                    "pid": 999999,
                }
            ),
            encoding="utf-8",
        )
        self.assertEqual(runtime_status(root)["status"], "stopped")

    def test_next_job_wait_returns_none_at_deadline_and_claims_new_job(self):
        empty_root = temporary_workspace(self)
        self.assertIsNone(
            next_job_with_wait(
                empty_root,
                "worker",
                wait_seconds=0,
                clock=fake_clock,
                sleeper=lambda _: None,
            )
        )
        root = completed_return_day_workspace(self, "ses_a")
        build_local_projection(root, "ses_a", LATER)
        confirmed_review(root, "ses_a")
        register_capabilities(root, {"text_ai": {"available": True}}, NOW)
        create_job(root, "job_1", "ses_a", "text_enhancement", "prv_1", NOW)
        claimed = next_job_with_wait(
            root,
            "worker",
            wait_seconds=1,
            clock=fake_clock,
            sleeper=lambda _: None,
        )
        self.assertEqual(claimed["status"], "claimed")

    def test_bridge_prompt_sets_capability_and_bounded_wait_contract(self):
        prompt = (
            Path(__file__).resolve().parents[1] / "prompts" / "web_agent_bridge.md"
        ).read_text(encoding="utf-8")
        self.assertIn("实际可调用的能力", prompt)
        self.assertIn("最长 30 秒", prompt)
        self.assertIn("无文字的抽象背景", prompt)
        self.assertIn("不要自动重复", prompt)


if __name__ == "__main__":
    unittest.main()
