#!/usr/bin/env python3
"""Render a pipeline run as GitHub-flavored markdown.

Used by the Actions workflow to write a job summary, so a run kicked off from a
phone reports its gate scores where you can actually read them — in the run
view — instead of only in files you would have to download.

Usage:
    python .github/scripts/run_summary.py [project_dir] > summary.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

STAGES = [
    ("plan", 0, "Plan"),
    ("research", 1, "Research"),
    ("outline", 2, "Outline"),
    ("content", 3, "Draft"),
    ("editorial", 4, "Editorial"),
    ("formatting", 5, "Format"),
    ("assembly", 6, "Assembly"),
]

ICONS = {
    "passed": "✅",
    "failed": "❌",
    "revising": "🔁",
    "running": "⏳",
    "pending": "⬜",
}


def human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def render(project_dir: Path) -> str:
    state_path = project_dir / "status.json"
    if not state_path.exists():
        return "## Pipeline run\n\nNo `status.json` was written — the run did not start.\n"

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"## Pipeline run\n\n`status.json` is unreadable: {exc}\n"

    status = state.get("pipeline_status", "unknown")
    headline = {"completed": "✅ All gates passed", "halted": "❌ Halted"}.get(status, f"Status: {status}")

    lines = [f"## {headline}", ""]

    stage_state = state.get("stages", {})
    lines += ["| | Gate | Stage | Score | Attempts |", "|---|---|---|---|---|"]
    for key, gate, label in STAGES:
        recorded = stage_state.get(key, {})
        stage_status = recorded.get("status", "pending")
        score = recorded.get("score")
        lines.append(
            f"| {ICONS.get(stage_status, '⬜')} | {gate} | {label} | "
            f"{f'{score:.2f}' if isinstance(score, (int, float)) else '—'} | "
            f"{recorded.get('attempt', '—')} |"
        )

    if state.get("halt_reason"):
        lines += ["", "### Halt reason", "", "```", state["halt_reason"].strip(), "```"]

    output_dir = project_dir / "output"
    if output_dir.is_dir():
        files = sorted(f for f in output_dir.iterdir() if f.is_file())
        if files:
            lines += ["", f"### Deliverables ({len(files)})", ""]
            lines += [f"- `{f.name}` — {human_size(f.stat().st_size)}" for f in files]
            lines += ["", "Download them from the **Artifacts** section of this run."]

    return "\n".join(lines) + "\n"


def main() -> None:
    project_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    sys.stdout.write(render(project_dir))


if __name__ == "__main__":
    main()
