"""Tests for agents/qa_reviewer.py

Tests focus on _parse_response and _format_rubric — the logic that does not
require an LLM call. The review_gate method (which calls the LLM) is tested
via mocking.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from agents.qa_reviewer import QAReviewerAgent
from gates.rubrics import RUBRICS


@pytest.fixture()
def reviewer(project_dir):
    return QAReviewerAgent(project_dir)


@pytest.fixture()
def minimal_spec():
    return {"quality_thresholds": {"min_gate_confidence": 0.8}}


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_parses_clean_pass_json(self, reviewer):
        payload = {
            "verdict": "PASS",
            "score": 0.92,
            "dimension_scores": {"source_coverage": 0.9, "source_quality": 0.95},
            "feedback": "",
            "passing_dimensions": ["source_coverage", "source_quality"],
            "failing_dimensions": [],
        }
        result = reviewer._parse_response(json.dumps(payload), quality_threshold=0.8)
        assert result["verdict"] == "PASS"
        assert result["score"] == pytest.approx(0.92)
        assert result["dimension_scores"]["source_coverage"] == pytest.approx(0.9)

    def test_parses_revise_json(self, reviewer):
        payload = {
            "verdict": "REVISE",
            "score": 0.65,
            "dimension_scores": {"source_coverage": 0.5, "source_quality": 0.8},
            "feedback": "Add 5 more sources; competitive matrix is missing pricing data.",
            "passing_dimensions": ["source_quality"],
            "failing_dimensions": ["source_coverage"],
        }
        result = reviewer._parse_response(json.dumps(payload), quality_threshold=0.8)
        assert result["verdict"] == "REVISE"
        assert "sources" in result["feedback"]

    def test_parses_fail_json(self, reviewer):
        payload = {
            "verdict": "FAIL",
            "score": 0.2,
            "dimension_scores": {},
            "feedback": "Output is completely off-spec.",
            "passing_dimensions": [],
            "failing_dimensions": [],
        }
        result = reviewer._parse_response(json.dumps(payload), quality_threshold=0.8)
        assert result["verdict"] == "FAIL"

    def test_strips_markdown_code_fence(self, reviewer):
        payload = {"verdict": "PASS", "score": 0.9, "dimension_scores": {}, "feedback": ""}
        wrapped = f"```json\n{json.dumps(payload)}\n```"
        result = reviewer._parse_response(wrapped, quality_threshold=0.8)
        assert result["verdict"] == "PASS"

    def test_strips_code_fence_without_language(self, reviewer):
        payload = {"verdict": "PASS", "score": 0.9, "dimension_scores": {}, "feedback": ""}
        wrapped = f"```\n{json.dumps(payload)}\n```"
        result = reviewer._parse_response(wrapped, quality_threshold=0.8)
        assert result["verdict"] == "PASS"

    def test_fallback_on_invalid_json(self, reviewer):
        result = reviewer._parse_response("This is not JSON at all.", quality_threshold=0.8)
        assert result["verdict"] in {"PASS", "REVISE", "FAIL"}
        assert "feedback" in result

    def test_fallback_detects_pass_keyword_in_garbage(self, reviewer):
        result = reviewer._parse_response('Some text "PASS" and more text', quality_threshold=0.8)
        assert result["verdict"] == "PASS"

    def test_fallback_detects_revise_keyword(self, reviewer):
        result = reviewer._parse_response('Some text "REVISE" and more', quality_threshold=0.8)
        assert result["verdict"] == "REVISE"

    def test_missing_fields_get_defaults(self, reviewer):
        # Minimal valid JSON missing optional fields
        result = reviewer._parse_response(
            json.dumps({"verdict": "PASS", "score": 0.9}),
            quality_threshold=0.8,
        )
        assert result["dimension_scores"] == {}
        assert result["feedback"] == ""
        assert result["passing_dimensions"] == []
        assert result["failing_dimensions"] == []

    def test_score_above_threshold_upgrades_revise_to_pass(self, reviewer):
        # If score >= threshold and no critical dimension < 0.5, REVISE → PASS
        payload = {
            "verdict": "REVISE",
            "score": 0.85,
            "dimension_scores": {"dim_a": 0.9, "dim_b": 0.8},
            "feedback": "Minor tweak suggested.",
            "passing_dimensions": [],
            "failing_dimensions": [],
        }
        result = reviewer._parse_response(json.dumps(payload), quality_threshold=0.8)
        assert result["verdict"] == "PASS"

    def test_score_above_threshold_but_critical_dim_low_stays_revise(self, reviewer):
        payload = {
            "verdict": "REVISE",
            "score": 0.85,
            "dimension_scores": {"dim_a": 0.4, "dim_b": 0.9},  # dim_a below 0.5
            "feedback": "Critical dimension failed.",
            "passing_dimensions": [],
            "failing_dimensions": ["dim_a"],
        }
        result = reviewer._parse_response(json.dumps(payload), quality_threshold=0.8)
        assert result["verdict"] == "REVISE"


# ---------------------------------------------------------------------------
# _format_rubric
# ---------------------------------------------------------------------------

class TestFormatRubric:
    def test_returns_markdown_table(self, reviewer):
        rubric = RUBRICS["research"]
        table = reviewer._format_rubric(rubric)
        assert "| Dimension |" in table
        assert "| Weight |" in table

    def test_all_dimension_names_present(self, reviewer):
        rubric = RUBRICS["outline"]
        table = reviewer._format_rubric(rubric)
        for dim in rubric:
            assert dim["name"] in table

    def test_all_weights_present(self, reviewer):
        rubric = RUBRICS["content"]
        table = reviewer._format_rubric(rubric)
        for dim in rubric:
            assert str(dim["weight"]) in table


# ---------------------------------------------------------------------------
# review_gate (mocked LLM call)
# ---------------------------------------------------------------------------

class TestReviewGate:
    def _mock_llm_response(self, verdict, score, feedback=""):
        return json.dumps({
            "verdict": verdict,
            "score": score,
            "dimension_scores": {"dim_a": score},
            "feedback": feedback,
            "passing_dimensions": [],
            "failing_dimensions": [],
        })

    def test_returns_pass_when_llm_says_pass(self, reviewer, minimal_spec, project_dir):
        (project_dir / "research" / "output.md").write_text("some content", encoding="utf-8")
        with patch.object(reviewer, "call_llm", return_value=self._mock_llm_response("PASS", 0.9)):
            result = reviewer.review_gate(
                gate_number=1,
                spec=minimal_spec,
                stage_output_path=project_dir / "research" / "output.md",
                rubric_key="research",
            )
        assert result["verdict"] == "PASS"
        assert result["score"] == pytest.approx(0.9)

    def test_returns_revise_when_llm_says_revise(self, reviewer, minimal_spec, project_dir):
        (project_dir / "research" / "output.md").write_text("some content", encoding="utf-8")
        with patch.object(
            reviewer, "call_llm",
            return_value=self._mock_llm_response("REVISE", 0.6, "Add more sources.")
        ):
            result = reviewer.review_gate(
                gate_number=1,
                spec=minimal_spec,
                stage_output_path=project_dir / "research" / "output.md",
                rubric_key="research",
            )
        assert result["verdict"] == "REVISE"
        assert "sources" in result["feedback"]

    def test_handles_missing_output_file(self, reviewer, minimal_spec, project_dir):
        with patch.object(reviewer, "call_llm", return_value=self._mock_llm_response("FAIL", 0.0)):
            result = reviewer.review_gate(
                gate_number=1,
                spec=minimal_spec,
                stage_output_path=project_dir / "research" / "nonexistent.md",
                rubric_key="research",
            )
        # Should still return a verdict dict (content will note file not found)
        assert "verdict" in result

    def test_uses_spec_quality_threshold(self, reviewer, project_dir):
        (project_dir / "outline" / "outline.md").write_text("outline", encoding="utf-8")
        high_threshold_spec = {"quality_thresholds": {"min_gate_confidence": 0.95}}
        # LLM says REVISE with score 0.85 — above default 0.8 but below 0.95
        with patch.object(
            reviewer, "call_llm",
            return_value=self._mock_llm_response("REVISE", 0.85, "needs work")
        ):
            result = reviewer.review_gate(
                gate_number=2,
                spec=high_threshold_spec,
                stage_output_path=project_dir / "outline" / "outline.md",
                rubric_key="outline",
            )
        # With threshold 0.95 and score 0.85, should remain REVISE
        assert result["verdict"] == "REVISE"
