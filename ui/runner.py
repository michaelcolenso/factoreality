"""RunManager — owns the orchestrator subprocess launched from the UI.

The UI never imports the pipeline in-process. It shells out to
``orchestrator.py`` exactly the way the CLI does, so a run started from the
browser is byte-for-byte the same run a human would start from a terminal.
Stdout/stderr are captured line by line into a bounded ring buffer that the
front end tails with ``/api/log?since=N``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_LOG_LINES = 4000
BRIEF_FILENAME = "product-brief.md"

#: Directories and files the pipeline generates. "Reset run" clears exactly
#: these and nothing else — the spec, the brief, and source code are never
#: touched.
GENERATED_DIRS = ("research", "outline", "draft", "editorial", "qa-reviews", "output", ".harness")
GENERATED_FILES = ("plan.md", "status.json")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RunAlreadyActive(RuntimeError):
    """Raised when a second run is requested while one is still in flight."""


class RunManager:
    """Starts, stops and observes a single orchestrator run at a time."""

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
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "stopped_by_user": False,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

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
        import shutil

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

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

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
