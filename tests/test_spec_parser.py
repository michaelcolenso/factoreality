"""Tests for utils/spec_parser.py"""

import pytest
from pathlib import Path

from utils.spec_parser import SpecParser


class TestSpecParserHappyPath:
    def test_parses_product_type(self, spec_file):
        spec = SpecParser(spec_file).parse()
        assert spec["product_type"] == "ebook"

    def test_parses_topic_angle(self, spec_file):
        spec = SpecParser(spec_file).parse()
        assert "Cold email sequences" in spec["topic_angle"]

    def test_parses_deliverables_list(self, spec_file):
        spec = SpecParser(spec_file).parse()
        assert len(spec["deliverables"]) == 3
        assert any("PDF ebook" in d for d in spec["deliverables"])
        assert any("template" in d.lower() for d in spec["deliverables"])

    def test_parses_quality_threshold(self, spec_file):
        spec = SpecParser(spec_file).parse()
        assert spec["quality_thresholds"]["min_gate_confidence"] == pytest.approx(0.85)

    def test_parses_max_retry_cycles(self, spec_file):
        spec = SpecParser(spec_file).parse()
        assert spec["quality_thresholds"]["max_retry_cycles"] == 3

    def test_parses_hard_constraints_word_count(self, spec_file):
        spec = SpecParser(spec_file).parse()
        assert spec["hard_constraints"]["min_words"] == 10000
        assert spec["hard_constraints"]["max_words"] == 15000

    def test_parses_hard_constraints_sections(self, spec_file):
        spec = SpecParser(spec_file).parse()
        assert spec["hard_constraints"]["min_sections"] == 5
        assert spec["hard_constraints"]["max_sections"] == 10

    def test_parses_done_when_checklist(self, spec_file):
        spec = SpecParser(spec_file).parse()
        assert len(spec["done_when"]) == 3
        assert any("placeholder" in item.lower() for item in spec["done_when"])

    def test_raw_text_preserved(self, spec_file):
        spec = SpecParser(spec_file).parse()
        assert "raw" in spec
        assert "Cold email" in spec["raw"]


class TestSpecParserErrors:
    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            SpecParser(tmp_path / "nonexistent.md").parse()

    def test_raises_value_error_missing_product_type(self, tmp_path):
        spec_path = tmp_path / "spec.md"
        spec_path.write_text("## Topic & Angle\nsome topic\n", encoding="utf-8")
        with pytest.raises(ValueError, match="product_type"):
            SpecParser(spec_path).parse()

    def test_raises_value_error_missing_topic(self, tmp_path):
        spec_path = tmp_path / "spec.md"
        spec_path.write_text("## Product Type\nebook\n", encoding="utf-8")
        with pytest.raises(ValueError, match="topic_angle"):
            SpecParser(spec_path).parse()


class TestSpecParserDefaults:
    def test_default_confidence_when_missing(self, tmp_path):
        spec_path = tmp_path / "spec.md"
        spec_path.write_text(
            "## Product Type\nebook\n\n## Topic & Angle\nsome topic\n",
            encoding="utf-8",
        )
        spec = SpecParser(spec_path).parse()
        assert spec["quality_thresholds"]["min_gate_confidence"] == pytest.approx(0.8)

    def test_default_retries_when_missing(self, tmp_path):
        spec_path = tmp_path / "spec.md"
        spec_path.write_text(
            "## Product Type\nebook\n\n## Topic & Angle\nsome topic\n",
            encoding="utf-8",
        )
        spec = SpecParser(spec_path).parse()
        assert spec["quality_thresholds"]["max_retry_cycles"] == 3

    def test_bracket_placeholder_fields_are_excluded(self, tmp_path):
        # topic_angle is a required field; if it's a placeholder the parser
        # strips it and then raises ValueError for the missing required field.
        spec_path = tmp_path / "spec.md"
        spec_path.write_text(
            "## Product Type\nebook\n\n## Topic & Angle\n[Specific topic goes here]\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="topic_angle"):
            SpecParser(spec_path).parse()


class TestHardConstraintParsing:
    def _make_spec(self, tmp_path, constraints_text):
        p = tmp_path / "spec.md"
        p.write_text(
            f"## Product Type\nebook\n\n## Topic & Angle\nsome topic\n\n"
            f"## Hard Constraints\n{constraints_text}\n",
            encoding="utf-8",
        )
        return p

    def test_word_count_with_comma_thousands(self, tmp_path):
        p = self._make_spec(tmp_path, "- Length: 10,000-20,000 words")
        spec = SpecParser(p).parse()
        assert spec["hard_constraints"]["min_words"] == 10000
        assert spec["hard_constraints"]["max_words"] == 20000

    def test_formats_extracted(self, tmp_path):
        p = self._make_spec(tmp_path, "- Formats: PDF, DOCX")
        spec = SpecParser(p).parse()
        assert "PDF" in spec["hard_constraints"]["formats"]
        assert "DOCX" in spec["hard_constraints"]["formats"]
