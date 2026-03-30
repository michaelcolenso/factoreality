"""File I/O helpers for the Content Factory pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class FileIO:
    """Manages reads and writes to the project file stack."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.status_path = project_dir / "status.md"
        self.state_path = project_dir / "status.json"

    def initialize_status(self, header: str) -> None:
        """Create or overwrite status.md with the run header."""
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        self.status_path.write_text(header, encoding="utf-8")

    def append_status(self, text: str) -> None:
        """Append a line to status.md (creates file if missing)."""
        with self.status_path.open("a", encoding="utf-8") as f:
            f.write(text)

    def read_status(self) -> str:
        if self.status_path.exists():
            return self.status_path.read_text(encoding="utf-8")
        return ""

    def initialize_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    def read_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def update_state(self, **updates: Any) -> dict[str, Any]:
        state = self.read_state()
        state.update(updates)
        self.initialize_state(state)
        return state

    def set_stage_state(self, stage_key: str, status: str, **extra: Any) -> dict[str, Any]:
        state = self.read_state()
        stages = state.setdefault("stages", {})
        stage_state = stages.setdefault(stage_key, {})
        stage_state["status"] = status
        stage_state.update(extra)
        self.initialize_state(state)
        return state

    def read(self, relative_path: str) -> str:
        path = self.project_dir / relative_path
        if path.exists():
            return path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"{relative_path} not found in {self.project_dir}")

    def write(self, relative_path: str, content: str) -> Path:
        path = self.project_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def exists(self, relative_path: str) -> bool:
        return (self.project_dir / relative_path).exists()

    def list_output_files(self) -> list[Path]:
        output_dir = self.project_dir / "output"
        if not output_dir.exists():
            return []
        return [f for f in output_dir.iterdir() if f.is_file()]
