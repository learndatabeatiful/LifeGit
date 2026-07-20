from __future__ import annotations

import argparse
import json
import os
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from pathlib import Path

try:
    from scripts.agent_jobs import (
        claim_next_job,
        complete_job,
        fail_job,
        register_capabilities,
    )
    from scripts.local_security import load_json_preserving_corrupt
    from scripts.web_server import create_server
    from scripts.workspace_store import ensure_workspace_layout, initialize_workspace
except ModuleNotFoundError:
    from agent_jobs import claim_next_job, complete_job, fail_job, register_capabilities
    from local_security import load_json_preserving_corrupt
    from web_server import create_server
    from workspace_store import ensure_workspace_layout, initialize_workspace


DEFAULT_WORKSPACE = Path.home() / "Documents" / "LifeGit-data"


def prepare_workspace(root: Path, created_at: str) -> Path:
    root = root.expanduser().resolve()
    manifest = root / "manifest.json"
    if manifest.exists() or manifest.is_symlink():
        return ensure_workspace_layout(root)
    return initialize_workspace(root, "ws_lifegit", created_at)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LifeGit local Web and Agent bridge")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in [
        "serve",
        "status",
        "register-capabilities",
        "next-job",
        "complete-job",
        "fail-job",
    ]:
        child = sub.add_parser(name)
        if name == "serve":
            child.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
            child.add_argument("--open", action="store_true")
        else:
            child.add_argument("--workspace", type=Path, required=True)
        if name == "register-capabilities":
            child.add_argument("--input", type=Path, required=True)
        elif name == "next-job":
            child.add_argument("--worker", required=True)
            child.add_argument("--wait", type=int, default=30, choices=range(0, 31))
        elif name == "complete-job":
            child.add_argument("--worker", required=True)
            child.add_argument("--job-id", required=True)
            child.add_argument("--result", type=Path, required=True)
        elif name == "fail-job":
            child.add_argument("--worker", required=True)
            child.add_argument("--job-id", required=True)
            child.add_argument("--code", required=True)
            child.add_argument("--message", required=True)
            child.add_argument("--retryable", action="store_true")
    return parser


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _pid_alive(pid: object) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def runtime_status(root: Path) -> dict:
    path = root / "runtime" / "web.json"
    if not path.exists():
        return {"status": "stopped"}
    value = load_json_preserving_corrupt(path)
    if not isinstance(value, dict) or not _pid_alive(value.get("pid")):
        return {**value, "status": "stopped"} if isinstance(value, dict) else {
            "status": "stopped"
        }
    connection = None
    try:
        connection = HTTPConnection(value["host"], value["port"], timeout=0.3)
        connection.request(
            "GET",
            f"/?token={value['token']}",
            headers={"Host": f"{value['host']}:{value['port']}"},
        )
        response = connection.getresponse()
        response.read()
        running = response.status == 303 and response.getheader("Location") == "/"
        return {**value, "status": "running" if running else "stopped"}
    except (KeyError, OSError, TypeError, ValueError):
        return {**value, "status": "stopped"}
    finally:
        if connection is not None:
            connection.close()


def next_job_with_wait(
    root: Path,
    worker: str,
    wait_seconds: int,
    clock=_now,
    sleeper=time.sleep,
):
    deadline = time.monotonic() + wait_seconds
    while True:
        now = clock()
        expires = (
            datetime.fromisoformat(now.replace("Z", "+00:00"))
            + timedelta(seconds=60)
        ).isoformat().replace("+00:00", "Z")
        job = claim_next_job(root, worker, now, expires)
        if job is not None or time.monotonic() >= deadline:
            return job
        sleeper(0.25)


def main() -> int:
    args = build_parser().parse_args()
    workspace = args.workspace.expanduser().resolve()
    if args.command == "serve":
        prepare_workspace(workspace, _now())
        existing = runtime_status(workspace)
        if existing["status"] == "running":
            url = f"http://127.0.0.1:{existing['port']}/?token={existing['token']}"
            print(
                json.dumps(
                    {
                        "status": "resumed",
                        "url": url,
                        "host": "127.0.0.1",
                        "port": existing["port"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
            if args.open:
                webbrowser.open(url)
            return 0
        web_root = Path(__file__).resolve().parents[1] / "web"
        server = create_server(workspace, web_root)
        runtime = load_json_preserving_corrupt(workspace / "runtime" / "web.json")
        url = f"http://127.0.0.1:{server.server_port}/?token={runtime['token']}"
        print(
            json.dumps(
                {
                    "status": "started",
                    "url": url,
                    "host": "127.0.0.1",
                    "port": server.server_port,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    if args.command == "status":
        print(json.dumps(runtime_status(workspace), ensure_ascii=False))
        return 0
    if args.command == "register-capabilities":
        value = load_json_preserving_corrupt(args.input)
        register_capabilities(workspace, value, _now())
        return 0
    if args.command == "next-job":
        job = next_job_with_wait(workspace, args.worker, args.wait)
        print(json.dumps(job, ensure_ascii=False))
        return 0
    if args.command == "complete-job":
        result = load_json_preserving_corrupt(args.result)
        complete_job(workspace, args.job_id, args.worker, result, _now())
        return 0
    if args.command == "fail-job":
        fail_job(
            workspace,
            args.job_id,
            args.worker,
            args.code,
            args.message,
            args.retryable,
            _now(),
        )
        return 0
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
