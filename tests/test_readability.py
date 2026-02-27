"""Tests for utils/readability.py"""

import pytest

from utils.readability import (
    strip_markdown,
    count_syllables,
    flesch_kincaid_grade,
    flesch_reading_ease,
    score_file,
)


class TestStripMarkdown:
    def test_strips_headings(self):
        assert "##" not in strip_markdown("## My Heading\n")
        assert "My Heading" in strip_markdown("## My Heading\n")

    def test_strips_bold(self):
        result = strip_markdown("This is **bold** text.")
        assert "**" not in result
        assert "bold" in result

    def test_strips_inline_code(self):
        result = strip_markdown("Run `git status` now.")
        assert "`" not in result
        assert "Run" in result
        assert "now" in result

    def test_strips_fenced_code_block(self):
        text = "Intro.\n```python\nx = 1\n```\nOutro."
        result = strip_markdown(text)
        assert "x = 1" not in result
        assert "Intro" in result
        assert "Outro" in result

    def test_strips_links_keeps_text(self):
        result = strip_markdown("See [the docs](https://example.com) for more.")
        assert "the docs" in result
        assert "https://" not in result

    def test_strips_image_refs(self):
        result = strip_markdown("![alt text](image.png)")
        assert "![" not in result
        assert "image.png" not in result

    def test_strips_table_rows(self):
        result = strip_markdown("| Column A | Column B |\n| val1 | val2 |")
        assert "|" not in result

    def test_plain_text_unchanged(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert strip_markdown(text) == text


class TestCountSyllables:
    @pytest.mark.parametrize("word,expected", [
        ("cat", 1),
        ("hello", 2),
        ("beautiful", 3),
        ("a", 1),
        ("the", 1),
        ("I", 1),
    ])
    def test_syllable_counts(self, word, expected):
        assert count_syllables(word) == expected

    def test_strips_punctuation(self):
        assert count_syllables("cat.") == count_syllables("cat")
        assert count_syllables("hello,") == count_syllables("hello")

    def test_minimum_one_syllable(self):
        assert count_syllables("x") >= 1
        assert count_syllables("nth") >= 1


class TestFleschKincaidGrade:
    def test_very_simple_text_low_grade(self):
        # Short words, short sentences → low grade level
        text = "The cat sat on the mat. The dog ran fast. It was fun."
        grade = flesch_kincaid_grade(text)
        assert grade < 5.0

    def test_complex_academic_text_higher_grade(self):
        text = (
            "The epistemological implications of contemporary computational "
            "architectures necessitate a fundamental reconsideration of "
            "established phenomenological frameworks. Interdisciplinary "
            "investigation suggests that reductionist methodologies are "
            "insufficient for characterizing emergent systemic properties."
        )
        grade = flesch_kincaid_grade(text)
        assert grade > 12.0

    def test_returns_float(self):
        assert isinstance(flesch_kincaid_grade("Hello world. This is a test."), float)

    def test_never_negative(self):
        assert flesch_kincaid_grade("Hi. OK. Yes.") >= 0.0

    def test_markdown_does_not_skew_score(self):
        plain = "The cat sat on the mat. The dog ran fast."
        markdown = "## Heading\n\nThe cat sat on the mat. The dog ran **fast**.\n"
        # Scores should be close since content is similar
        assert abs(flesch_kincaid_grade(plain) - flesch_kincaid_grade(markdown)) < 3.0


class TestFleschReadingEase:
    def test_simple_text_high_ease(self):
        text = "The cat sat on the mat. The dog ran fast. It was fun."
        assert flesch_reading_ease(text) > 70.0

    def test_complex_text_lower_ease(self):
        text = (
            "The epistemological implications of contemporary computational "
            "architectures necessitate a fundamental reconsideration of "
            "established phenomenological frameworks."
        )
        assert flesch_reading_ease(text) < 40.0

    def test_score_bounded_0_to_100(self):
        for text in [
            "Hi.",
            "The quick brown fox.",
            "Antidisestablishmentarianism is a philosophical position.",
        ]:
            score = flesch_reading_ease(text)
            assert 0.0 <= score <= 100.0


class TestScoreFile:
    def test_scores_valid_file(self, tmp_path):
        f = tmp_path / "draft.md"
        f.write_text(
            "The cat sat on the mat. The dog ran fast. It was a good day.\n" * 5,
            encoding="utf-8",
        )
        result = score_file(f)
        assert "grade_level" in result
        assert "reading_ease" in result
        assert "word_count" in result
        assert result["word_count"] > 0

    def test_missing_file_returns_error(self, tmp_path):
        result = score_file(tmp_path / "nonexistent.md")
        assert "error" in result

    def test_word_count_accurate(self, tmp_path):
        # 10 simple English words, no markdown
        f = tmp_path / "t.md"
        f.write_text("one two three four five six seven eight nine ten", encoding="utf-8")
        result = score_file(f)
        assert result["word_count"] == 10
