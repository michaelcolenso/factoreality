#!/usr/bin/env python3
"""Factoreality control room — a zero-dependency local web UI for the pipeline.

Serves a single-page dashboard plus a small JSON API over Python's stdlib HTTP
server. No framework, no build step, no external packages — same constraint the
pipeline itself runs under.

Usage:
    python ui/server.py                       # http://127.0.0.1:8420
    python ui/server.py --port 9000
    python ui/server.py --project /path/to/project
    python ui/server.py --no-browser
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ui.runner import RunAlreadyActive, RunManager  # noqa: E402
from ui.state import ProjectState  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_PORT = 8420


class ControlRoomHandler(BaseHTTPRequestHandler):
    """Routes static assets and the JSON API. One instance per request."""

    server_version = "Factoreality/1.0"
    protocol_version = "HTTP/1.1"

    # Injected by serve()
    state: ProjectState
    runner: RunManager

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 — stdlib naming
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)

        try:
            if route.startswith("/api/"):
                self._handle_api_get(route, query)
            else:
                self._serve_static(route)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except FileNotFoundError:
            self._send_json({"error": "Not found."}, status=404)
        except BrokenPipeError:
            pass
        except Exception as exc:  # pragma: no cover — defensive
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, status=500)

    def do_POST(self) -> None:  # noqa: N802 — stdlib naming
        route = urlparse(self.path).path
        try:
            body = self._read_json_body()
            if route == "/api/run":
                self._handle_run(body)
            elif route == "/api/stop":
                self._send_json({"run": self.runner.stop()})
            elif route == "/api/reset":
                self._send_json({"removed": self.runner.reset(), "run": self.runner.snapshot()})
            elif route == "/api/spec":
                self._handle_spec_write(body)
            elif route == "/api/spec/validate":
                self._send_json(self.state.validate_spec_text(body.get("content", "")))
            else:
                self._send_json({"error": "Unknown endpoint."}, status=404)
        except RunAlreadyActive as exc:
            self._send_json({"error": str(exc)}, status=409)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
        except BrokenPipeError:
            pass
        except Exception as exc:  # pragma: no cover — defensive
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, status=500)

    # ------------------------------------------------------------------
    # API — GET
    # ------------------------------------------------------------------

    def _handle_api_get(self, route: str, query: dict[str, list[str]]) -> None:
        if route == "/api/state":
            payload = self.state.payload()
            payload["run"] = self.runner.snapshot()
            self._send_json(payload)
        elif route == "/api/log":
            since = int(query.get("since", ["0"])[0])
            payload = self.runner.log_since(since)
            payload["run"] = self.runner.snapshot()
            self._send_json(payload)
        elif route == "/api/spec":
            spec_path = self.state.project_dir / "spec.md"
            content = spec_path.read_text(encoding="utf-8") if spec_path.exists() else ""
            self._send_json({"content": content, "summary": self.state.spec_summary()})
        elif route == "/api/brief":
            brief_path = self.state.project_dir / "product-brief.md"
            content = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
            self._send_json({"content": content})
        elif route == "/api/file":
            self._send_json(self.state.read_text_file(query.get("path", [""])[0]))
        elif route == "/api/download":
            self._send_download(self.state.resolve(query.get("path", [""])[0]))
        else:
            self._send_json({"error": "Unknown endpoint."}, status=404)

    # ------------------------------------------------------------------
    # API — POST handlers
    # ------------------------------------------------------------------

    def _handle_run(self, body: dict) -> None:
        run = self.runner.start(
            dry_run=bool(body.get("dry_run")),
            resume=bool(body.get("resume")),
            brief=str(body.get("brief") or ""),
            regenerate_spec=bool(body.get("regenerate_spec")),
        )
        self._send_json({"run": run})

    def _handle_spec_write(self, body: dict) -> None:
        content = body.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Spec content is empty.")
        check = self.state.validate_spec_text(content)
        if not check["valid"] and not body.get("force"):
            self._send_json({"saved": False, **check}, status=422)
            return
        (self.state.project_dir / "spec.md").write_text(content, encoding="utf-8")
        self._send_json({"saved": True, "summary": self.state.spec_summary(), **check})

    # ------------------------------------------------------------------
    # Static assets
    # ------------------------------------------------------------------

    def _serve_static(self, route: str) -> None:
        relative = "index.html" if route in ("/", "") else route.lstrip("/")
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in target.parents or not target.is_file():
            raise FileNotFoundError(relative)

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self._send_bytes(data, content_type=f"{content_type}; charset=utf-8", cache=False)

    def _send_download(self, path: Path) -> None:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self._send_bytes(
            path.read_bytes(),
            content_type=content_type,
            extra_headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
        )

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON body: {exc}") from exc
        if not isinstance(body, dict):
            raise ValueError("JSON body must be an object.")
        return body

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, default=str).encode("utf-8")
        self._send_bytes(data, content_type="application/json; charset=utf-8", status=status)

    def _send_bytes(
        self,
        data: bytes,
        content_type: str,
        status: int = 200,
        cache: bool = False,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if not cache:
            self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        """Quieter than the stdlib default — API polling would flood the console."""
        if "/api/log" in self.path or "/api/state" in self.path:
            return
        sys.stderr.write(f"  {self.address_string()} — {fmt % args}\n")


def build_server(host: str, port: int, project_dir: Path) -> ThreadingHTTPServer:
    handler = type(
        "BoundControlRoomHandler",
        (ControlRoomHandler,),
        {
            "state": ProjectState(project_dir),
            "runner": RunManager(REPO_ROOT, project_dir),
        },
    )
    return ThreadingHTTPServer((host, port), handler)


def serve(host: str, port: int, project_dir: Path, open_browser: bool = True) -> None:
    httpd = build_server(host, port, project_dir)
    url = f"http://{host}:{httpd.server_address[1]}"

    print("\n  factoreality control room")
    print(f"  project : {project_dir}")
    print(f"  url     : {url}")
    print("  stop    : ctrl-c\n")

    if host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"  ! Bound to {host}, not loopback. The UI starts processes and writes\n"
            "    spec.md — anyone who can reach this port can do both. Use a trusted\n"
            "    network or an SSH tunnel.\n"
        )

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  shutting down.")
    finally:
        httpd.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Local web UI for the Content Factory pipeline")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--project",
        default=str(REPO_ROOT),
        help="Project directory containing spec.md (default: the repo root)",
    )
    parser.add_argument("--no-browser", action="store_true", help="Do not open a browser on start")
    args = parser.parse_args()

    project_dir = Path(args.project).expanduser().resolve()
    if not project_dir.is_dir():
        print(f"Error: '{project_dir}' is not a directory.")
        sys.exit(1)

    serve(args.host, args.port, project_dir, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
