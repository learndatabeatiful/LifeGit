from __future__ import annotations

import json
import mimetypes
import os
import secrets
from datetime import datetime, timezone
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

try:
    from scripts.local_security import resolve_within
    from scripts.web_api import WebApi
except ModuleNotFoundError:
    from local_security import resolve_within
    from web_api import WebApi


MAX_BODY = 5 * 1024 * 1024
COOKIE_NAME = "lifegit_session"
CSP = (
    "default-src 'self'; img-src 'self' blob: data:; style-src 'self'; "
    "script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_runtime_manifest(root: Path, port: int, token: str) -> Path:
    path = root / "runtime" / "web.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {"host": "127.0.0.1", "port": port, "token": token, "pid": os.getpid()},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)
    os.chmod(path, 0o600)
    return path


class LifeGitHandler(BaseHTTPRequestHandler):
    workspace: Path
    static_root: Path
    session_token: str
    application: WebApi

    def log_message(self, format, *args):
        return

    def _headers(
        self,
        content_type: str,
        length: int,
        extra: dict[str, str] | None = None,
    ) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _send(
        self,
        status: int,
        body: bytes = b"",
        content_type: str = "text/plain; charset=utf-8",
        extra: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self._headers(content_type, len(body), extra)
        if body:
            self.wfile.write(body)

    def _valid_host(self) -> bool:
        expected = {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }
        return self.headers.get("Host") in expected

    def _valid_cookie(self) -> bool:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            return False
        supplied = cookie.get(COOKIE_NAME)
        return supplied is not None and secrets.compare_digest(
            supplied.value,
            self.session_token,
        )

    def _valid_origin(self) -> bool:
        return self.headers.get("Origin") in {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
        }

    def _handle(self, method: str) -> None:
        if not self._valid_host():
            return self._send(421, b"invalid host")
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        valid_handshake = (
            method == "GET"
            and parsed.path == "/"
            and set(query) == {"token"}
            and query.get("token") == [self.session_token]
        )
        if valid_handshake:
            return self._send(
                303,
                extra={
                    "Location": "/",
                    "Set-Cookie": (
                        f"{COOKIE_NAME}={self.session_token}; "
                        "HttpOnly; SameSite=Strict; Path=/"
                    ),
                },
            )
        if not self._valid_cookie():
            return self._send(401, b"authentication required")
        if method in {"POST", "PATCH"} and not self._valid_origin():
            return self._send(403, b"invalid origin")
        if parsed.path.startswith("/api/"):
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_length)
            except ValueError:
                return self._send(400, b"invalid content length")
            if length < 0 or length > MAX_BODY:
                return self._send(413, b"request too large")
            body = self.rfile.read(length) if length else b""
            content_type = self.headers.get(
                "Content-Type",
                "application/json",
            ).split(";", 1)[0]
            response = self.application.dispatch(method, parsed.path, body, content_type)
            return self._send(
                response.status,
                response.body,
                response.content_type,
                response.headers,
            )
        if method != "GET":
            return self._send(405, b"method not allowed")
        relative = parsed.path.lstrip("/") or "index.html"
        try:
            target = resolve_within(self.static_root, relative)
        except ValueError:
            return self._send(400, b"invalid path")
        if not target.is_file():
            return self._send(404, b"not found")
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return self._send(200, target.read_bytes(), content_type)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PATCH(self):
        self._handle("PATCH")

    def do_PUT(self):
        self._send(405, b"method not allowed")

    def do_DELETE(self):
        self._send(405, b"method not allowed")

    def do_OPTIONS(self):
        self._send(405, b"method not allowed")


def create_server(
    root: Path,
    web_root: Path,
    token: str | None = None,
) -> ThreadingHTTPServer:
    token = token or secrets.token_urlsafe(32)
    api = WebApi(root, utc_now)

    class Handler(LifeGitHandler):
        workspace = root
        static_root = web_root
        session_token = token
        application = api

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    write_runtime_manifest(root, server.server_port, token)
    return server
