"""Project inspection for the UI — turns the file stack into a JSON payload.

The pipeline keeps all of its state in files (``status.json``, ``status.md``,
``qa-reviews/``, stage output dirs). This module reads that stack through a
:class:`~ui.backends.base.Store` and shapes it into what the dashboard renders.

It never touches a filesystem directly. That is deliberate: it is what allows
the same dashboard to be served from a machine that holds the project on disk
or from somewhere that reads the project out of a git repository.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gates.rubrics import RUBRICS
from ui.backends.base import MAX_PREVIEW_BYTES, Store
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


def parse_spec_text(text: str) -> dict[str, Any]:
    """Parse spec text through the pipeline's own parser, without touching disk.

    SpecParser reads from a path, so the text is staged in a temp file. Specs
    are a few kilobytes, so this is cheaper than it looks and keeps the UI from
    forking the parsing rules — the pipeline stays the single source of truth
    on what a valid spec is.
    """
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "spec.md"
        probe.write_text(text, encoding="utf-8")
        return SpecParser(probe).parse()


class ProjectState:
    """Reads a project's file stack for the dashboard."""

    def __init__(self, store: Store) -> None:
        self.store = store

    # ------------------------------------------------------------------
    # Aggregate payload
    # ------------------------------------------------------------------

    def payload(self) -> dict[str, Any]:
        state = self.read_state()
        return {
            "server_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "project_dir": self.store.label,
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

    def read_state(self) -> dict[str, Any]:
        """The pipeline's machine state (``status.json``), or {} if absent."""
        if not self.store.exists("status.json"):
            return {}
        try:
            return json.loads(self.store.read_text("status.json"))
        except (json.JSONDecodeError, ValueError):
            return {}

    # ------------------------------------------------------------------
    # Stages and gates
    # ------------------------------------------------------------------

    def stages(self, state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        state = self.read_state() if state is None else state
        stage_state = state.get("stages", {})
        threshold = self._threshold()
        reviews = self._reviews_by_gate()

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
                    "reviews": reviews.get(gate, []),
                }
            )
        return stages

    def _reviews_by_gate(self) -> dict[int, list[dict[str, Any]]]:
        by_gate: dict[int, list[dict[str, Any]]] = {}
        for meta in self.store.walk("qa-reviews"):
            if not meta.name.startswith("gate-") or not meta.name.endswith(".md"):
                continue
            try:
                gate = int(meta.name.split("-")[1])
            except (IndexError, ValueError):
                continue
            by_gate.setdefault(gate, []).append(
                {"path": meta.path, "attempt": self._attempt_from_name(meta.name)}
            )
        for entries in by_gate.values():
            entries.sort(key=lambda entry: entry["attempt"])
        return by_gate

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
        summary = self.spec_summary()
        if not summary.get("valid"):
            return 0.8
        return summary.get("min_gate_confidence", 0.8)

    # ------------------------------------------------------------------
    # Spec
    # ------------------------------------------------------------------

    def spec_summary(self) -> dict[str, Any]:
        if not self.store.exists("spec.md"):
            return {"exists": False, "valid": False, "error": "spec.md not found."}
        try:
            spec = parse_spec_text(self.store.read_text("spec.md"))
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
        try:
            spec = parse_spec_text(text)
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

        root_files = [meta.as_dict() for name in ROOT_FILES if (meta := self.store.stat(name))]
        if root_files:
            groups.append({"name": "project", "files": root_files})

        for dirname in ARTIFACT_DIRS:
            files = [meta.as_dict() for meta in self.store.walk(dirname)]
            if files:
                groups.append({"name": dirname, "files": files})
        return groups

    # ------------------------------------------------------------------
    # File access
    # ------------------------------------------------------------------

    def read_text_file(self, relative_path: str) -> dict[str, Any]:
        meta = self.store.stat(relative_path)
        content = self.store.read_text(relative_path)
        size = meta.size if meta else len(content.encode("utf-8"))
        return {
            "path": relative_path,
            "size": size,
            "truncated": size > MAX_PREVIEW_BYTES,
            "content": content,
        }
