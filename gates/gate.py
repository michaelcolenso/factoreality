"""
GateRunner — automated verification checks that run BEFORE the QA Reviewer.

These checks are deterministic (no LLM call): counts, scans, file existence.
They augment the QA Reviewer's judgment with hard facts.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


class GateRunner:
    """
    Runs automated verification checks for a given gate.

    Results are passed to the QA Reviewer as additional context so it has
    concrete data to base its rubric scores on.
    """

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir

    def run_checks(self, gate_number: int, spec: dict) -> dict:
        """
        Run all automated checks for the given gate.

        Returns a dict with:
          passed  — list of check names that passed
          failed  — list of check names that failed (with reason)
          summary — human-readable summary string for status.md
        """
        dispatch = {
            0: self._gate_0_checks,
            1: self._gate_1_checks,
            2: self._gate_2_checks,
            3: self._gate_3_checks,
            4: self._gate_4_checks,
            5: self._gate_5_checks,
            6: self._gate_6_checks,
        }
        check_fn = dispatch.get(gate_number, lambda s: {"passed": [], "failed": [], "summary": ""})
        return check_fn(spec)

    # ------------------------------------------------------------------
    # Gate 0 — Plan
    # ------------------------------------------------------------------

    def _gate_0_checks(self, spec: dict) -> dict:
        passed, failed = [], []
        plan_path = self.project_dir / "plan.md"

        if plan_path.exists() and plan_path.stat().st_size > 100:
            passed.append("plan.md exists and is non-trivial")
        else:
            failed.append("plan.md missing or too short")

        # Every major milestone keyword should appear
        plan_text = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
        for keyword in ["Milestone 1", "Milestone 2", "Milestone 3", "Milestone 4", "Milestone 5", "Milestone 6"]:
            if keyword in plan_text:
                passed.append(f"Plan contains {keyword}")
            else:
                failed.append(f"Plan missing {keyword}")

        return self._result(passed, failed)

    # ------------------------------------------------------------------
    # Gate 1 — Research
    # ------------------------------------------------------------------

    def _gate_1_checks(self, spec: dict) -> dict:
        passed, failed = [], []
        brief_path = self.project_dir / "research/research-brief.md"

        if not brief_path.exists():
            failed.append("research-brief.md not found")
            return self._result(passed, failed)

        text = brief_path.read_text(encoding="utf-8")

        # Count sources (lines with markdown links)
        source_lines = re.findall(r"\[.+?\]\(https?://[^\)]+\)", text)
        count = len(source_lines)
        if count >= 10:
            passed.append(f"Source count: {count} (≥10 required)")
        else:
            failed.append(f"Source count: {count} (need ≥10)")

        # Check competitive matrix exists
        if "| Product |" in text or "| product |" in text.lower():
            passed.append("Competitive analysis table present")
        else:
            failed.append("Competitive analysis table not found")

        # Check pain points section
        if "Pain Point" in text or "pain point" in text.lower():
            passed.append("Pain points section present")
        else:
            failed.append("Pain points section not found")

        return self._result(passed, failed)

    # ------------------------------------------------------------------
    # Gate 2 — Outline
    # ------------------------------------------------------------------

    def _gate_2_checks(self, spec: dict) -> dict:
        passed, failed = [], []
        outline_path = self.project_dir / "outline/outline.md"

        if not outline_path.exists():
            failed.append("outline.md not found")
            return self._result(passed, failed)

        text = outline_path.read_text(encoding="utf-8")
        sections = re.findall(r"^### ", text, re.MULTILINE)
        section_count = len(sections)

        min_sec = spec.get("hard_constraints", {}).get("min_sections", 3)
        max_sec = spec.get("hard_constraints", {}).get("max_sections", 20)

        if min_sec <= section_count <= max_sec:
            passed.append(f"Section count: {section_count} (within {min_sec}–{max_sec})")
        else:
            failed.append(f"Section count: {section_count} (expected {min_sec}–{max_sec})")

        # Check word count allocations are present
        wc_entries = re.findall(r"\*\*Word Count Allocation:\*\*\s*(\d[\d,]*)", text)
        if wc_entries:
            total = sum(int(w.replace(",", "")) for w in wc_entries)
            target_min = spec.get("hard_constraints", {}).get("min_words", 5000)
            target_max = spec.get("hard_constraints", {}).get("max_words", 50000)
            tolerance = 0.10
            if target_min * (1 - tolerance) <= total <= target_max * (1 + tolerance):
                passed.append(f"Word count total: {total:,} (within ±10% of {target_min:,}–{target_max:,})")
            else:
                failed.append(f"Word count total: {total:,} (expected {target_min:,}–{target_max:,} ±10%)")
        else:
            failed.append("No word count allocations found in outline")

        return self._result(passed, failed)

    # ------------------------------------------------------------------
    # Gate 3 — Draft
    # ------------------------------------------------------------------

    def _gate_3_checks(self, spec: dict) -> dict:
        passed, failed = [], []
        draft_path = self.project_dir / "draft/draft.md"

        if not draft_path.exists():
            failed.append("draft.md not found")
            return self._result(passed, failed)

        text = draft_path.read_text(encoding="utf-8")

        # Placeholder scan
        placeholder_pattern = re.compile(
            r"TODO|TBD|INSERT|PLACEHOLDER|FIXME|\[INSERT|\[EXAMPLE|\[YOUR ",
            re.IGNORECASE,
        )
        placeholders = placeholder_pattern.findall(text)
        if placeholders:
            failed.append(f"Placeholder text found: {len(placeholders)} instance(s)")
        else:
            passed.append("No placeholder text found")

        # Word count
        word_count = len(text.split())
        target_min = spec.get("hard_constraints", {}).get("min_words", 5000)
        target_max = spec.get("hard_constraints", {}).get("max_words", 50000)
        if target_min * 0.9 <= word_count <= target_max * 1.1:
            passed.append(f"Word count: {word_count:,} (within range)")
        else:
            failed.append(f"Word count: {word_count:,} (expected {target_min:,}–{target_max:,})")

        return self._result(passed, failed)

    # ------------------------------------------------------------------
    # Gate 4 — Editorial
    # ------------------------------------------------------------------

    def _gate_4_checks(self, spec: dict) -> dict:
        passed, failed = [], []
        edited_path = self.project_dir / "draft/draft-edited.md"

        if not edited_path.exists():
            failed.append("draft-edited.md not found")
            return self._result(passed, failed)

        # Check editorial notes exist
        notes_path = self.project_dir / "editorial/editorial-notes.md"
        if notes_path.exists():
            passed.append("editorial-notes.md present")
        else:
            failed.append("editorial-notes.md not found")

        # Placeholder scan on edited draft
        text = edited_path.read_text(encoding="utf-8")
        placeholder_pattern = re.compile(r"TODO|TBD|INSERT|PLACEHOLDER|FIXME", re.IGNORECASE)
        if placeholder_pattern.search(text):
            failed.append("Placeholder text still present in edited draft")
        else:
            passed.append("No placeholder text in edited draft")

        # Check for [VERIFY: ...] markers that were not resolved
        verify_markers = re.findall(r"\[VERIFY:", text)
        if verify_markers:
            failed.append(f"{len(verify_markers)} unresolved [VERIFY:] marker(s) in edited draft")
        else:
            passed.append("No unresolved [VERIFY:] markers")

        return self._result(passed, failed)

    # ------------------------------------------------------------------
    # Gate 5 — Formatting
    # ------------------------------------------------------------------

    def _gate_5_checks(self, spec: dict) -> dict:
        passed, failed = [], []
        output_dir = self.project_dir / "output"

        formatted_files = list(output_dir.glob("*.md")) + list(output_dir.glob("*.pdf"))
        if formatted_files:
            passed.append(f"Formatted file(s) found: {[f.name for f in formatted_files]}")
        else:
            failed.append("No formatted files found in output/")

        # Check for YAML front matter (Pandoc requirement)
        for f in output_dir.glob("*.md"):
            text = f.read_text(encoding="utf-8")
            if text.startswith("---"):
                passed.append(f"{f.name}: YAML front matter present")
            else:
                failed.append(f"{f.name}: missing YAML front matter")
            break

        return self._result(passed, failed)

    # ------------------------------------------------------------------
    # Gate 6 — Assembly
    # ------------------------------------------------------------------

    def _gate_6_checks(self, spec: dict) -> dict:
        passed, failed = [], []
        output_dir = self.project_dir / "output"

        # README
        readme = output_dir / "README.md"
        if readme.exists() and readme.stat().st_size > 50:
            passed.append("README.md present and non-trivial")
        else:
            failed.append("README.md missing or empty")

        # Manifest JSON
        manifest = output_dir / "manifest.json"
        if manifest.exists():
            passed.append("manifest.json present")
        else:
            failed.append("manifest.json missing")

        # At least one non-README output file
        output_files = [
            f for f in output_dir.iterdir()
            if f.is_file() and f.name not in ("README.md", "manifest.json")
        ]
        if output_files:
            passed.append(f"{len(output_files)} deliverable file(s) in output/")
        else:
            failed.append("No deliverable files in output/")

        # All files are non-empty
        empty = [f.name for f in output_files if f.stat().st_size == 0]
        if empty:
            failed.append(f"Empty files: {empty}")
        else:
            passed.append("All output files are non-empty")

        return self._result(passed, failed)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _result(self, passed: list, failed: list) -> dict:
        total = len(passed) + len(failed)
        pass_rate = len(passed) / total if total > 0 else 0.0
        lines = []
        for p in passed:
            lines.append(f"  ✓ {p}")
        for f in failed:
            lines.append(f"  ✗ {f}")
        summary = f"Automated checks: {len(passed)}/{total} passed\n" + "\n".join(lines)
        return {"passed": passed, "failed": failed, "summary": summary, "pass_rate": pass_rate}
