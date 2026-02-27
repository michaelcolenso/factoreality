"""Tests for gates/gate.py (GateRunner automated verification checks)."""

import json
import pytest
from pathlib import Path

from gates.gate import GateRunner


@pytest.fixture()
def runner(project_dir):
    return GateRunner(project_dir)


@pytest.fixture()
def minimal_spec():
    return {
        "hard_constraints": {
            "min_words": 5000,
            "max_words": 15000,
            "min_sections": 3,
            "max_sections": 10,
        }
    }


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_result_has_required_keys(self, runner, minimal_spec):
        result = runner.run_checks(0, minimal_spec)
        assert "passed" in result
        assert "failed" in result
        assert "summary" in result
        assert "pass_rate" in result

    def test_pass_rate_is_float_between_0_and_1(self, runner, minimal_spec):
        result = runner.run_checks(0, minimal_spec)
        assert 0.0 <= result["pass_rate"] <= 1.0

    def test_summary_is_string(self, runner, minimal_spec):
        assert isinstance(runner.run_checks(1, minimal_spec)["summary"], str)

    def test_unknown_gate_returns_empty_result(self, runner, minimal_spec):
        result = runner.run_checks(99, minimal_spec)
        assert result["passed"] == []
        assert result["failed"] == []


# ---------------------------------------------------------------------------
# Gate 0 — plan checks
# ---------------------------------------------------------------------------

class TestGate0:
    def test_fails_when_plan_missing(self, runner, minimal_spec):
        result = runner.run_checks(0, minimal_spec)
        assert any("plan.md" in f.lower() for f in result["failed"])

    def test_passes_when_plan_has_all_milestones(self, project_dir, minimal_spec):
        plan = "\n".join(f"## Milestone {i}" for i in range(1, 7))
        (project_dir / "plan.md").write_text(plan, encoding="utf-8")
        runner = GateRunner(project_dir)
        result = runner.run_checks(0, minimal_spec)
        assert all(
            any(f"Milestone {i}" in p for p in result["passed"])
            for i in range(1, 7)
        )

    def test_fails_for_each_missing_milestone(self, project_dir, minimal_spec):
        # Plan has only Milestone 1
        (project_dir / "plan.md").write_text("## Milestone 1\nsome content", encoding="utf-8")
        runner = GateRunner(project_dir)
        result = runner.run_checks(0, minimal_spec)
        # Milestones 2-6 should be in failed
        assert any("Milestone 2" in f for f in result["failed"])


# ---------------------------------------------------------------------------
# Gate 1 — research checks
# ---------------------------------------------------------------------------

def _write_research_brief(project_dir, content):
    brief = project_dir / "research" / "research-brief.md"
    brief.write_text(content, encoding="utf-8")


class TestGate1:
    def test_fails_when_brief_missing(self, runner, minimal_spec):
        result = runner.run_checks(1, minimal_spec)
        assert any("research-brief.md" in f for f in result["failed"])

    def test_fails_with_fewer_than_10_sources(self, project_dir, minimal_spec):
        links = "\n".join(
            f"- [Source {i}](https://example.com/{i}) — summary" for i in range(5)
        )
        _write_research_brief(project_dir, links)
        result = GateRunner(project_dir).run_checks(1, minimal_spec)
        assert any("Source count" in f for f in result["failed"])

    def test_passes_with_10_or_more_sources(self, project_dir, minimal_spec):
        links = "\n".join(
            f"- [Source {i}](https://example.com/{i}) — summary" for i in range(12)
        )
        _write_research_brief(project_dir, links)
        result = GateRunner(project_dir).run_checks(1, minimal_spec)
        assert any("Source count" in p for p in result["passed"])

    def test_detects_competitive_analysis_table(self, project_dir, minimal_spec):
        content = (
            "- [S1](https://a.com)\n" * 10
            + "| Product | Price | Format | Page Count | Strengths | Gaps |\n"
            + "| A | $27 | PDF | 45 | Good | None |\n"
        )
        _write_research_brief(project_dir, content)
        result = GateRunner(project_dir).run_checks(1, minimal_spec)
        assert any("Competitive" in p for p in result["passed"])

    def test_fails_without_competitive_table(self, project_dir, minimal_spec):
        links = "\n".join(
            f"- [Source {i}](https://example.com/{i}) — summary" for i in range(12)
        )
        _write_research_brief(project_dir, links)
        result = GateRunner(project_dir).run_checks(1, minimal_spec)
        assert any("Competitive" in f for f in result["failed"])

    def test_detects_pain_points_section(self, project_dir, minimal_spec):
        content = (
            "- [S1](https://a.com)\n" * 10
            + "| Product | Price |\n| A | $10 |\n"
            + "## Audience Pain Points\n> Pain 1\n"
        )
        _write_research_brief(project_dir, content)
        result = GateRunner(project_dir).run_checks(1, minimal_spec)
        assert any("Pain points" in p for p in result["passed"])


# ---------------------------------------------------------------------------
# Gate 2 — outline checks
# ---------------------------------------------------------------------------

def _write_outline(project_dir, content):
    (project_dir / "outline" / "outline.md").write_text(content, encoding="utf-8")


class TestGate2:
    def test_fails_when_outline_missing(self, runner, minimal_spec):
        result = runner.run_checks(2, minimal_spec)
        assert any("outline.md" in f for f in result["failed"])

    def test_section_count_within_range_passes(self, project_dir, minimal_spec):
        sections = "\n".join(f"### {i}. Section {i}" for i in range(1, 6))
        wc = "\n".join(
            f"**Word Count Allocation:** 1000 words" for _ in range(5)
        )
        _write_outline(project_dir, sections + "\n" + wc)
        result = GateRunner(project_dir).run_checks(2, minimal_spec)
        assert any("Section count" in p for p in result["passed"])

    def test_section_count_out_of_range_fails(self, project_dir):
        spec = {"hard_constraints": {"min_sections": 5, "max_sections": 8, "min_words": 5000, "max_words": 15000}}
        # Only 2 sections — below minimum of 5
        sections = "\n".join(f"### {i}. Section {i}" for i in range(1, 3))
        _write_outline(project_dir, sections)
        result = GateRunner(project_dir).run_checks(2, spec)
        assert any("Section count" in f for f in result["failed"])

    def test_word_count_sum_in_range_passes(self, project_dir, minimal_spec):
        # 5 sections × 2000 words = 10,000 — within 5000-15000 ±10%
        content = ""
        for i in range(1, 6):
            content += f"### {i}. Section {i}\n**Word Count Allocation:** 2000 words\n\n"
        _write_outline(project_dir, content)
        result = GateRunner(project_dir).run_checks(2, minimal_spec)
        assert any("Word count total" in p for p in result["passed"])

    def test_word_count_sum_out_of_range_fails(self, project_dir, minimal_spec):
        # 3 sections × 100 words = 300 — far below 5000 minimum
        content = ""
        for i in range(1, 4):
            content += f"### {i}. Section {i}\n**Word Count Allocation:** 100 words\n\n"
        _write_outline(project_dir, content)
        result = GateRunner(project_dir).run_checks(2, minimal_spec)
        assert any("Word count total" in f for f in result["failed"])


# ---------------------------------------------------------------------------
# Gate 3 — draft checks
# ---------------------------------------------------------------------------

def _write_draft(project_dir, content):
    (project_dir / "draft" / "draft.md").write_text(content, encoding="utf-8")


class TestGate3:
    def test_fails_when_draft_missing(self, runner, minimal_spec):
        result = runner.run_checks(3, minimal_spec)
        assert any("draft.md" in f for f in result["failed"])

    def test_passes_clean_draft_word_count(self, project_dir, minimal_spec):
        words = "word " * 10000
        _write_draft(project_dir, words)
        result = GateRunner(project_dir).run_checks(3, minimal_spec)
        assert any("Word count" in p and "range" in p for p in result["passed"])

    def test_fails_draft_with_placeholders(self, project_dir, minimal_spec):
        content = ("word " * 10000) + "\nTODO: finish this section\n"
        _write_draft(project_dir, content)
        result = GateRunner(project_dir).run_checks(3, minimal_spec)
        assert any("Placeholder" in f or "placeholder" in f for f in result["failed"])

    def test_passes_no_placeholder_scan(self, project_dir, minimal_spec):
        _write_draft(project_dir, "word " * 10000)
        result = GateRunner(project_dir).run_checks(3, minimal_spec)
        assert any("No placeholder" in p for p in result["passed"])

    def test_fails_draft_with_low_word_count(self, project_dir, minimal_spec):
        _write_draft(project_dir, "only a few words here")
        result = GateRunner(project_dir).run_checks(3, minimal_spec)
        assert any("Word count" in f for f in result["failed"])


# ---------------------------------------------------------------------------
# Gate 4 — editorial checks
# ---------------------------------------------------------------------------

class TestGate4:
    def test_fails_without_edited_draft(self, runner, minimal_spec):
        result = runner.run_checks(4, minimal_spec)
        assert any("draft-edited.md" in f for f in result["failed"])

    def test_passes_when_notes_and_edited_draft_exist(self, project_dir, minimal_spec):
        (project_dir / "draft" / "draft-edited.md").write_text(
            "Clean content with no issues.", encoding="utf-8"
        )
        (project_dir / "editorial" / "editorial-notes.md").write_text(
            "# Editorial Notes\nNo issues.", encoding="utf-8"
        )
        result = GateRunner(project_dir).run_checks(4, minimal_spec)
        assert any("editorial-notes" in p for p in result["passed"])

    def test_fails_when_verify_markers_remain(self, project_dir, minimal_spec):
        (project_dir / "draft" / "draft-edited.md").write_text(
            "Some claim [VERIFY: needs source] is made here.", encoding="utf-8"
        )
        result = GateRunner(project_dir).run_checks(4, minimal_spec)
        assert any("VERIFY" in f for f in result["failed"])


# ---------------------------------------------------------------------------
# Gate 6 — assembly checks
# ---------------------------------------------------------------------------

class TestGate6:
    def test_fails_without_readme(self, runner, minimal_spec):
        result = runner.run_checks(6, minimal_spec)
        assert any("README" in f for f in result["failed"])

    def test_passes_with_readme_and_deliverable(self, project_dir, minimal_spec):
        output = project_dir / "output"
        output.mkdir(exist_ok=True)
        (output / "README.md").write_text(
            "# Package\n\nThis package contains the following files:\n- file.pdf (100 KB)\n",
            encoding="utf-8",
        )
        (output / "manifest.json").write_text(json.dumps({"files": []}), encoding="utf-8")
        (output / "product.pdf").write_bytes(b"%PDF-1.4 content")
        result = GateRunner(project_dir).run_checks(6, minimal_spec)
        assert any("README" in p for p in result["passed"])
        assert any("deliverable" in p for p in result["passed"])

    def test_detects_empty_output_files(self, project_dir, minimal_spec):
        output = project_dir / "output"
        output.mkdir(exist_ok=True)
        (output / "README.md").write_text("# Package\n\nFiles listed here.", encoding="utf-8")
        (output / "manifest.json").write_text("{}", encoding="utf-8")
        (output / "empty.pdf").write_bytes(b"")  # empty file
        result = GateRunner(project_dir).run_checks(6, minimal_spec)
        assert any("Empty" in f or "empty" in f for f in result["failed"])
