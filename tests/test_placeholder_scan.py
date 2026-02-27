"""Tests for utils/placeholder_scan.py"""

import pytest
from pathlib import Path

from utils.placeholder_scan import scan_for_placeholders, scan_file, report


class TestScanForPlaceholders:
    def test_clean_text_returns_empty(self):
        text = "This is clean content with no placeholders."
        assert scan_for_placeholders(text) == []

    @pytest.mark.parametrize("token", [
        "TODO",
        "TBD",
        "FIXME",
        "[INSERT example here]",
        "[EXAMPLE goes here]",
        "[YOUR name]",
        "[ADD content]",
        "PLACEHOLDER",
        "[CITATION NEEDED]",
        "[VERIFY: check this stat]",
        "Lorem ipsum dolor sit amet",
    ])
    def test_detects_placeholder_token(self, token):
        text = f"Some text before. {token} Some text after."
        hits = scan_for_placeholders(text)
        assert len(hits) == 1
        assert token in hits[0][1]

    def test_case_insensitive(self):
        assert scan_for_placeholders("some todo item") != []
        assert scan_for_placeholders("some Todo item") != []
        assert scan_for_placeholders("some TODO item") != []

    def test_returns_correct_line_number(self):
        text = "Line one is clean.\nLine two has TODO here.\nLine three is clean."
        hits = scan_for_placeholders(text)
        assert hits[0][0] == 2

    def test_multiple_placeholders_on_different_lines(self):
        text = "TODO first\nClean line\nFIXME second\nClean again"
        hits = scan_for_placeholders(text)
        assert len(hits) == 2
        assert hits[0][0] == 1
        assert hits[1][0] == 3

    def test_multiple_placeholders_on_same_line(self):
        text = "TODO and also FIXME on the same line"
        hits = scan_for_placeholders(text)
        # One hit per line, not per token
        assert len(hits) == 1

    def test_real_content_not_flagged(self):
        text = (
            "In 2024, enterprise software procurement teams evaluated an average "
            "of 8.3 vendors before making a purchase decision. [Smith & Jones, 2024]\n"
            "The key insight is that decision-makers prioritize risk reduction over "
            "feature richness in the final 20% of the evaluation cycle."
        )
        assert scan_for_placeholders(text) == []


class TestScanFile:
    def test_clean_file_returns_empty(self, tmp_path):
        f = tmp_path / "draft.md"
        f.write_text("# Clean Draft\n\nAll real content here.", encoding="utf-8")
        assert scan_file(f) == []

    def test_file_with_placeholder_returns_hits(self, tmp_path):
        f = tmp_path / "draft.md"
        f.write_text("# Draft\n\nTODO: write this section\n", encoding="utf-8")
        hits = scan_file(f)
        assert len(hits) == 1

    def test_nonexistent_file_returns_empty(self, tmp_path):
        assert scan_file(tmp_path / "missing.md") == []


class TestReport:
    def test_clean_file_shows_checkmark(self, tmp_path):
        f = tmp_path / "draft.md"
        f.write_text("Clean content.", encoding="utf-8")
        assert "✓" in report(f)
        assert "no placeholder" in report(f)

    def test_dirty_file_shows_cross(self, tmp_path):
        f = tmp_path / "draft.md"
        f.write_text("Some TODO here.", encoding="utf-8")
        r = report(f)
        assert "✗" in r
        assert "1 placeholder" in r

    def test_report_includes_line_number(self, tmp_path):
        f = tmp_path / "draft.md"
        f.write_text("Clean.\nTODO: fix this.\nClean.", encoding="utf-8")
        r = report(f)
        assert "Line 2" in r
