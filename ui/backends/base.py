"""The seam between the control plane and the execution plane.

The control room shows pipeline state and starts runs. Those are two different
jobs with two different requirements: reading state needs *a filesystem*,
starting a run needs *a POSIX process*. Fusing them is what pins the UI to one
machine, so they are split here into two protocols.

    Store   — where the project's file stack lives
    Runner  — what actually executes orchestrator.py

Today both are local (see ``ui.backends.local``). The point of the seam is that
they need not be: a Store can be a git repository read through the GitHub API,
and a Runner can be a CI job dispatched to run somewhere else entirely. The
front end never learns the difference — it talks to the same JSON API either
way, because that API is shaped like pipeline state, not like a filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol, runtime_checkable

#: File suffixes the UI will render as text rather than offer as a download.
TEXT_SUFFIXES = {".md", ".txt", ".json", ".csv", ".yml", ".yaml", ".py", ".html", ".css", ".js"}

#: Cap on how much of a single file the preview endpoint returns.
MAX_PREVIEW_BYTES = 400_000


@dataclass(frozen=True)
class FileMeta:
    """One file in a project, described without reference to any filesystem."""

    path: str
    name: str
    size: int
    modified: str

    @property
    def suffix(self) -> str:
        dot = self.name.rfind(".")
        return self.name[dot:].lower() if dot > 0 else ""

    @property
    def previewable(self) -> bool:
        return self.suffix in TEXT_SUFFIXES

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "modified": self.modified,
            "suffix": self.suffix,
            "previewable": self.previewable,
        }


class StoreError(ValueError):
    """A path was rejected, or could not be read."""


@runtime_checkable
class Store(Protocol):
    """Read/write access to a project's file stack.

    Paths are always project-relative, POSIX-style, and never absolute — that
    is what lets one implementation be a directory and another a git tree.
    Implementations are responsible for rejecting paths that escape the
    project (see ``LocalStore.resolve``).
    """

    @property
    def label(self) -> str:
        """Human-readable location, shown in the UI header."""

    def exists(self, path: str) -> bool: ...

    def read_text(self, path: str) -> str: ...

    def read_bytes(self, path: str) -> bytes: ...

    def write_text(self, path: str, content: str) -> None: ...

    def stat(self, path: str) -> FileMeta | None: ...

    def walk(self, prefix: str) -> Iterable[FileMeta]:
        """Every file under ``prefix``, recursively, sorted by path."""


@runtime_checkable
class Runner(Protocol):
    """Executes the pipeline and reports on it.

    ``snapshot`` and ``log_since`` are polled by the front end; both must be
    safe to call at any time, including before the first run.
    """

    def start(
        self,
        *,
        dry_run: bool = False,
        resume: bool = False,
        brief: str = "",
        regenerate_spec: bool = False,
    ) -> dict[str, Any]: ...

    def stop(self) -> dict[str, Any]: ...

    def reset(self) -> list[str]: ...

    def snapshot(self) -> dict[str, Any]: ...

    def log_since(self, since: int) -> dict[str, Any]: ...


class RunAlreadyActive(RuntimeError):
    """A run was requested while one was still in flight."""
