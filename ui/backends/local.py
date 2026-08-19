"""Local backend — a project directory on disk, driven by a subprocess.

This is the implementation the CLI's own workflow implies: the file stack is a
directory, and a run is ``python orchestrator.py`` in a child process. It is
the reference implementation of both protocols in ``ui.backends.base``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ui.backends.base import FileMeta, MAX_PREVIEW_BYTES, RunAlreadyActive, StoreError

MAX_LOG_LINES = 4000
BRIEF_FILENAME = "product-brief.md"

#: Directories and files the pipeline generates. "Reset run" clears exactly
#: these and nothing else — the spec, the brief, and source code are never
#: touched.
GENERATED_DIRS = ("research", "outline", "draft", "editorial", "qa-reviews", "output", ".harness")
GENERATED_FILES = ("plan.md", "status.json")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------
# Store
# ----------------------------------------------------------------------


class LocalStore:
    """A project directory, with every path resolved inside it."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.root = project_dir.resolve()

    @property
    def label(self) -> str:
        return str(self.project_dir)

    # -- path safety ---------------------------------------------------

    def resolve(self, relative_path: str) -> Path:
        """Resolve a request path inside the project dir, or raise StoreError.

        Guards against ``..`` traversal and symlinks pointing outside the
        project, and refuses to serve the git directory.
        """
        if not relative_path:
            raise StoreError("No path given.")
        candidate = (self.project_dir / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise StoreError("Path escapes the project directory.")
        if ".git" in candidate.relative_to(self.root).parts:
            raise StoreError("Refusing to serve the git directory.")
        if not candidate.is_file():
            raise StoreError(f"Not a file: {relative_path}")
        return candidate

    # -- Store protocol ------------------------------------------------

    def exists(self, path: str) -> bool:
        return (self.project_dir / path).is_file()

    def read_text(self, path: str) -> str:
        target = self.resolve(path)
        with target.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(MAX_PREVIEW_BYTES)

    def read_bytes(self, path: str) -> bytes:
        return self.resolve(path).read_bytes()

    def write_text(self, path: str, content: str) -> None:
        target = self.project_dir / path
        if self.root not in target.resolve().parents:
            raise StoreError("Path escapes the project directory.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def stat(self, path: str) -> FileMeta | None:
        target = self.project_dir / path
        if not target.is_file():
            return None
        return self._meta(target)

    def walk(self, prefix: str) -> Iterable[FileMeta]:
        directory = self.project_dir / prefix
        if not directory.is_dir():
            return []
        return [
            self._meta(path)
            for path in sorted(directory.rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts
        ]

    def _meta(self, path: Path) -> FileMeta:
        info = path.stat()
        return FileMeta(
            path=path.relative_to(self.project_dir).as_posix(),
            name=path.name,
            size=info.st_size,
            modified=datetime.fromtimestamp(info.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------


class LocalRunner:
    """Owns the orchestrator subprocess launched from the UI.

    The UI never imports the pipeline in-process. It shells out to
    ``orchestrator.py`` exactly the way the CLI does, so a run started from the
    browser is byte-for-byte the run a human would start from a terminal.
    Stdout/stderr are captured line by line into a bounded ring buffer that the
    front end tails with ``/api/log?since=N``.
    """

    def __init__(self, repo_root: Path, project_dir: Path) -> None:
        self.repo_root = repo_root
        self.project_dir = project_dir

        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._reader: threading.Thread | None = None
        self._log: deque[dict[str, Any]] = deque(maxlen=MAX_LOG_LINES)
        self._seq = 0
        self._run: dict[str, Any] = {
            "active": False,
            "pid": None,
            "argv": [],
            "mode": None,
            "backend": "local",
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "stopped_by_user": False,
        }

    # -- lifecycle -----------------------------------------------------

    def start(
        self,
        *,
        dry_run: bool = False,
        resume: bool = False,
        brief: str = "",
        regenerate_spec: bool = False,
    ) -> dict[str, Any]:
        """Launch a pipeline run. Returns the new run snapshot."""
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RunAlreadyActive("A pipeline run is already in progress.")

            argv = [sys.executable, "orchestrator.py", str(self.project_dir)]
            if dry_run:
                argv.append("--dry-run")
            if resume:
                argv.append("--resume")

            brief = brief.strip()
            if brief:
                brief_path = self.project_dir / BRIEF_FILENAME
                brief_path.write_text(brief + "\n", encoding="utf-8")
                argv += ["--brief-file", str(brief_path)]
                if regenerate_spec:
                    argv.append("--regenerate-spec")
            elif regenerate_spec:
                raise ValueError(
                    "Regenerating spec.md requires a product brief. "
                    "Write one in the Brief tab first."
                )

            env = dict(os.environ, PYTHONUNBUFFERED="1")
            self._process = subprocess.Popen(
                argv,
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )

            self._log.clear()
            self._seq = 0
            self._run = {
                "active": True,
                "pid": self._process.pid,
                "argv": argv[1:],  # hide the interpreter path
                "mode": self._describe_mode(dry_run, resume, bool(brief)),
                "backend": "local",
                "started_at": utcnow(),
                "finished_at": None,
                "exit_code": None,
                "stopped_by_user": False,
            }
            self._append_log("system", f"$ python {' '.join(argv[1:])}")

            self._reader = threading.Thread(target=self._pump_output, args=(self._process,), daemon=True)
            self._reader.start()
            return dict(self._run)

    def stop(self) -> dict[str, Any]:
        """Terminate an in-flight run, escalating to SIGKILL if it lingers."""
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None:
                return dict(self._run)
            self._run["stopped_by_user"] = True
            self._append_log("system", "Stop requested — terminating orchestrator.")
            process.terminate()

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with self._lock:
                self._append_log("system", "Orchestrator did not exit in 5s — killing.")
            process.kill()
            process.wait(timeout=5)

        return self.snapshot()

    def reset(self) -> list[str]:
        """Delete generated pipeline artifacts so the next run starts clean.

        Only the fixed allowlist above is removed. Refuses while a run is
        active so a half-written stage is never yanked out from under it.
        """
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise RunAlreadyActive("Cannot reset while a run is in progress.")

        removed: list[str] = []
        for name in GENERATED_DIRS:
            target = self.project_dir / name
            if target.is_dir():
                shutil.rmtree(target)
                removed.append(f"{name}/")
        for name in GENERATED_FILES:
            target = self.project_dir / name
            if target.is_file():
                target.unlink()
                removed.append(name)

        with self._lock:
            self._log.clear()
            self._seq = 0
            self._run.update(active=False, pid=None, exit_code=None, started_at=None, finished_at=None)
            if removed:
                self._append_log("system", "Reset removed: " + ", ".join(removed))
            else:
                self._append_log("system", "Reset: nothing to remove — workspace already clean.")
        return removed

    # -- observation ---------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if process is not None:
                code = process.poll()
                if code is None:
                    self._run["active"] = True
                elif self._run["active"]:
                    self._run["active"] = False
                    self._run["exit_code"] = code
                    self._run["finished_at"] = utcnow()
            return dict(self._run)

    def log_since(self, since: int) -> dict[str, Any]:
        with self._lock:
            lines = [entry for entry in self._log if entry["seq"] > since]
            return {"lines": lines, "cursor": self._seq}

    # -- internals -----------------------------------------------------

    def _pump_output(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            with self._lock:
                self._append_log("stdout", line.rstrip("\n"))
        process.stdout.close()
        code = process.wait()
        with self._lock:
            self._run["active"] = False
            self._run["exit_code"] = code
            self._run["finished_at"] = utcnow()
            if self._run["stopped_by_user"]:
                verdict = "Run stopped by user."
            elif code == 0:
                verdict = "Run finished — all gates passed."
            else:
                verdict = f"Run failed (exit {code}) — see the halt reason in status.md."
            self._append_log("system", verdict)

    def _append_log(self, stream: str, text: str) -> None:
        """Append one log line. Caller must hold ``self._lock``."""
        self._seq += 1
        self._log.append({"seq": self._seq, "stream": stream, "text": text, "at": utcnow()})

    @staticmethod
    def _describe_mode(dry_run: bool, resume: bool, has_brief: bool) -> str:
        parts = []
        if dry_run:
            parts.append("dry run")
        if resume:
            parts.append("resume")
        if has_brief:
            parts.append("brief-driven")
        return " + ".join(parts) if parts else "full run"
