import stat
import unittest
from contextlib import contextmanager
from http.client import HTTPConnection
from threading import Thread

from scripts.web_server import create_server, utc_now
from tests.web_test_helpers import temporary_workspace


def static_root(root):
    web_root = root.parent / "web"
    web_root.mkdir()
    (web_root / "index.html").write_text(
        "<!doctype html><title>LifeGit</title>",
        encoding="utf-8",
    )
    return web_root


@contextmanager
def running_server(root, web_root, token):
    server = create_server(root, web_root, token=token)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def raw_request(
    port,
    method,
    path,
    host=None,
    cookie=None,
    origin=None,
    body=None,
    content_length=None,
):
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    if cookie:
        headers["Cookie"] = cookie
    if origin:
        headers["Origin"] = origin
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    elif body is not None:
        headers["Content-Length"] = str(len(body))
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response.read()
        return response
    finally:
        connection.close()


def authenticate(port, token):
    cookie = raw_request(port, "GET", f"/?token={token}").getheader("Set-Cookie")
    return cookie.split(";", 1)[0]


class WebServerTests(unittest.TestCase):
    def test_server_clock_uses_semantic_record_timestamp_format(self):
        self.assertRegex(
            utc_now(),
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        )

    def test_token_handshake_redirects_to_clean_url_and_sets_http_only_cookie(self):
        root = temporary_workspace(self)
        web_root = static_root(root)
        with running_server(root, web_root, token="secret") as port:
            mode = stat.S_IMODE((root / "runtime" / "web.json").stat().st_mode)
            self.assertEqual(mode, 0o600)
            response = raw_request(port, "GET", "/?token=secret")
            self.assertEqual(response.status, 303)
            self.assertEqual(response.getheader("Location"), "/")
            cookie = response.getheader("Set-Cookie")
            self.assertIn("HttpOnly", cookie)
            self.assertIn("SameSite=Strict", cookie)

    def test_api_rejects_missing_cookie_bad_host_origin_and_oversized_body(self):
        root = temporary_workspace(self)
        web_root = static_root(root)
        with running_server(root, web_root, token="secret") as port:
            self.assertEqual(raw_request(port, "GET", "/api/bootstrap").status, 401)
            self.assertEqual(raw_request(port, "GET", "/", host="evil.example").status, 421)
            cookie = authenticate(port, "secret")
            self.assertEqual(
                raw_request(
                    port,
                    "POST",
                    "/api/sessions",
                    cookie=cookie,
                    origin="http://evil.example",
                    body=b"{}",
                ).status,
                403,
            )
            self.assertEqual(
                raw_request(
                    port,
                    "POST",
                    "/api/sessions",
                    cookie=cookie,
                    origin=f"http://127.0.0.1:{port}",
                    body=b"",
                    content_length=5 * 1024 * 1024 + 1,
                ).status,
                413,
            )

    def test_static_response_has_csp_and_no_cors(self):
        root = temporary_workspace(self)
        web_root = static_root(root)
        with running_server(root, web_root, token="secret") as port:
            response = raw_request(
                port,
                "GET",
                "/",
                cookie=authenticate(port, "secret"),
            )
            self.assertIn("default-src 'self'", response.getheader("Content-Security-Policy"))
            self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))


if __name__ == "__main__":
    unittest.main()
