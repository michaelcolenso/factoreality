"""Project inspection for the UI — turns the file stack into a JSON payload.

The pipeline keeps all of its state in files (``status.json``, ``status.md``,
``qa-reviews/``, stage output dirs). This module reads that stack and shapes it
into what the dashboard renders. It is read-only: nothing here mutates a run.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gates.rubrics import RUBRICS
from utils.file_io import FileIO
from utils.spec_parser import SpecParser

#: (state key, gate number, display label, one-line purpose, rubric key)
STAGES: tuple[tuple[str, int, str, str, str], ...] = (
    ("plan", 0, "Plan", "Turn the spec into a verifiable build plan", "plan"),
    ("research", 1, "Research", "Sources, competitive matrix, sourced pain points", "research"),
    ("outline", 2, "Outline", "Locked structure and word allocations", "outline"),
    ("content", 3, "Draft", "Full section-by-section draft", "content"),
    ("editorial", 4, "Editorial", "Grammar, facts, readability", "editorial"),
    ("formatting", 5, "Format", "Layout and export", "formatting"),
    ("assembly", 6, "Assembly", "Package, manifest, monetization assets", "assembly"),
)

#: Directories surfaced in the Artifacts tab, in pipeline order.
ARTIFACT_DIRS: tuple[str, ...] = (
    "output",
    "products",
    "draft",
    "editorial",
    "outline",
    "research",
    "qa-reviews",
    ".harness",
)

#: Root-level files worth showing alongside the generated directories.
ROOT_FILES: tuple[str, ...] = (
    "spec.md",
    "plan.md",
    "product-brief.md",
    "status.md",
    "status.json",
    "implement.md",
)

TEXT_SUFFIXES = {".md", ".txt", ".json", ".csv", ".yml", ".yaml", ".py", ".html", ".css", ".js"}
MAX_PREVIEW_BYTES = 400_000


class ProjectState:
    """Reads the project file stack for the dashboard."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.io = FileIO(project_dir)

    # ------------------------------------------------------------------
    # Aggregate payload
    # ------------------------------------------------------------------

    def payload(self) -> dict[str, Any]:
        state = self.io.read_state()
        return {
            "server_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "project_dir": str(self.project_dir),
            "pipeline": {
                "status": state.get("pipeline_status", "idle"),
                "started_at": state.get("started_at"),
                "finished_at": state.get("finished_at"),
                "halted_at": state.get("halted_at"),
                "halt_reason": state.get("halt_reason"),
                "dry_run": state.get("dry_run", False),
            },
            "stages": self.stages(state),
            "spec": self.spec_summary(),
            "artifacts": self.artifacts(),
        }

    # ------------------------------------------------------------------
    # Stages and gates
    # ------------------------------------------------------------------

    def stages(self, state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        state = self.io.read_state() if state is None else state
        stage_state = state.get("stages", {})
        threshold = self._threshold()

        stages: list[dict[str, Any]] = []
        for key, gate, label, purpose, rubric_key in STAGES:
            recorded = stage_state.get(key, {})
            stages.append(
                {
                    "key": key,
                    "gate": gate,
                    "label": label,
                    "purpose": purpose,
                    "status": recorded.get("status", "pending"),
                    "score": recorded.get("score"),
                    "threshold": threshold,
                    "attempt": recorded.get("attempt"),
                    "started_at": recorded.get("started_at"),
                    "completed_at": recorded.get("completed_at"),
                    "output_path": recorded.get("output_path"),
                    "feedback": recorded.get("feedback"),
                    "error": recorded.get("error"),
                    "rubric": RUBRICS.get(rubric_key, []),
                    "reviews": self._reviews_for_gate(gate),
                }
            )
        return stages

    def _reviews_for_gate(self, gate: int) -> list[dict[str, Any]]:
        review_dir = self.project_dir / "qa-reviews"
        if not review_dir.is_dir():
            return []
        matches = sorted(review_dir.glob(f"gate-{gate}-review*.md"))
        return [
            {
                "path": str(path.relative_to(self.project_dir)),
                "attempt": self._attempt_from_name(path.name),
            }
            for path in matches
        ]

    @staticmethod
    def _attempt_from_name(name: str) -> int:
        marker = "-attempt-"
        if marker not in name:
            return 0
        try:
            return int(name.split(marker)[1].split(".")[0])
        except (IndexError, ValueError):
            return 0

    def _threshold(self) -> float:
        try:
            spec = SpecParser(self.project_dir / "spec.md").parse()
        except (FileNotFoundError, ValueError):
            return 0.8
        return spec.get("quality_thresholds", {}).get("min_gate_confidence", 0.8)

    # ------------------------------------------------------------------
    # Spec
    # ------------------------------------------------------------------

    def spec_summary(self) -> dict[str, Any]:
        spec_path = self.project_dir / "spec.md"
        if not spec_path.exists():
            return {"exists": False, "valid": False, "error": "spec.md not found."}
        try:
            spec = SpecParser(spec_path).parse()
        except ValueError as exc:
            return {"exists": True, "valid": False, "error": str(exc)}

        constraints = spec.get("hard_constraints", {})
        thresholds = spec.get("quality_thresholds", {})
        return {
            "exists": True,
            "valid": True,
            "error": None,
            "product_type": spec.get("product_type"),
            "topic_angle": spec.get("topic_angle"),
            "deliverables": spec.get("deliverables", []),
            "done_when": spec.get("done_when", []),
            "word_range": (
                [constraints.get("min_words"), constraints.get("max_words")]
                if constraints.get("min_words")
                else None
            ),
            "section_range": (
                [constraints.get("min_sections"), constraints.get("max_sections")]
                if constraints.get("min_sections")
                else None
            ),
            "formats": constraints.get("formats", []),
            "min_gate_confidence": thresholds.get("min_gate_confidence", 0.8),
            "max_retry_cycles": thresholds.get("max_retry_cycles", 3),
            "readability_target": thresholds.get("readability_target"),
        }

    def validate_spec_text(self, text: str) -> dict[str, Any]:
        """Parse spec text without writing it, for the editor's live check."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "spec.md"
            probe.write_text(text, encoding="utf-8")
            try:
                spec = SpecParser(probe).parse()
            except ValueError as exc:
                return {"valid": False, "error": str(exc)}
        return {
            "valid": True,
            "error": None,
            "product_type": spec.get("product_type"),
            "deliverables": len(spec.get("deliverables", [])),
        }

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def artifacts(self) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []

        root_files = [
            self._describe(self.project_dir / name)
            for name in ROOT_FILES
            if (self.project_dir / name).is_file()
        ]
        if root_files:
            groups.append({"name": "project", "files": root_files})

        for dirname in ARTIFACT_DIRS:
            directory = self.project_dir / dirname
            if not directory.is_dir():
                continue
            files = [
                self._describe(path)
                for path in sorted(directory.rglob("*"))
                if path.is_file() and "__pycache__" not in path.parts
            ]
            if files:
                groups.append({"name": dirname, "files": files})
        return groups

    def _describe(self, path: Path) -> dict[str, Any]:
        stat = path.stat()
        return {
            "path": str(path.relative_to(self.project_dir)),
            "name": path.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "suffix": path.suffix.lower(),
            "previewable": path.suffix.lower() in TEXT_SUFFIXES,
        }

    # ------------------------------------------------------------------
    # File access (sandboxed to the project directory)
    # ------------------------------------------------------------------

    def resolve(self, relative_path: str) -> Path:
        """Resolve a request path inside the project dir, or raise ValueError.

        Guards against ``..`` traversal and symlinks pointing outside the
        project, and refuses to serve the git directory.
        """
        if not relative_path:
            raise ValueError("No path given.")
        candidate = (self.project_dir / relative_path).resolve()
        root = self.project_dir.resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("Path escapes the project directory.")
        if ".git" in candidate.relative_to(root).parts:
            raise ValueError("Refusing to serve the git directory.")
        if not candidate.is_file():
            raise ValueError(f"Not a file: {relative_path}")
        return candidate

    def read_text_file(self, relative_path: str) -> dict[str, Any]:
        path = self.resolve(relative_path)
        size = path.stat().st_size
        truncated = size > MAX_PREVIEW_BYTES
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            content = handle.read(MAX_PREVIEW_BYTES)
        return {
            "path": relative_path,
            "size": size,
            "truncated": truncated,
            "content": content,
        }
