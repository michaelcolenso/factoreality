"""
Flesch-Kincaid readability scoring for plain text / Markdown.

Strips Markdown formatting before scoring so code blocks, links, and headers
don't skew the result.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Markdown stripper
# ---------------------------------------------------------------------------

_STRIP_PATTERNS = [
    (re.compile(r"```.*?```", re.DOTALL), " "),         # code blocks
    (re.compile(r"`[^`]+`"), " "),                        # inline code
    (re.compile(r"!\[.*?\]\(.*?\)"), " "),                # images
    (re.compile(r"\[([^\]]+)\]\([^\)]+\)"), r"\1"),       # links → text
    (re.compile(r"^#+\s+", re.MULTILINE), ""),            # headings
    (re.compile(r"[*_]{1,3}([^*_]+)[*_]{1,3}"), r"\1"),  # bold/italic
    (re.compile(r"^\s*[>\-\*\+]\s+", re.MULTILINE), ""), # blockquotes / lists
    (re.compile(r"\|[^\n]*", re.MULTILINE), " "),          # table rows
    (re.compile(r"---+"), " "),                           # horizontal rules
]


def strip_markdown(text: str) -> str:
    for pattern, repl in _STRIP_PATTERNS:
        text = pattern.sub(repl, text)
    return text


# ---------------------------------------------------------------------------
# Syllable counter (English approximation)
# ---------------------------------------------------------------------------

def count_syllables(word: str) -> int:
    word = word.lower().strip(".,;:!?\"'()")
    if not word:
        return 0
    # Special cases
    if len(word) <= 3:
        return 1
    # Remove silent e
    if word.endswith("e"):
        word = word[:-1]
    count = len(re.findall(r"[aeiou]+", word))
    return max(1, count)


# ---------------------------------------------------------------------------
# Flesch-Kincaid Grade Level
# ---------------------------------------------------------------------------

def flesch_kincaid_grade(text: str) -> float:
    """
    Returns the Flesch-Kincaid Grade Level for a text string.

    FK Grade = 0.39 × (words/sentences) + 11.8 × (syllables/words) − 15.59
    """
    plain = strip_markdown(text)

    # Split into sentences
    sentences = re.split(r"[.!?]+", plain)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) >= 3]
    num_sentences = max(1, len(sentences))

    # Split into words
    words = re.findall(r"\b[a-zA-Z]+\b", plain)
    num_words = max(1, len(words))

    # Count syllables
    num_syllables = sum(count_syllables(w) for w in words)

    asl = num_words / num_sentences       # average sentence length
    asw = num_syllables / num_words       # average syllables per word

    grade = 0.39 * asl + 11.8 * asw - 15.59
    return round(max(0.0, grade), 1)


def flesch_reading_ease(text: str) -> float:
    """
    Flesch Reading Ease (higher = easier, 100 = very easy, 0 = very hard).
    """
    plain = strip_markdown(text)
    sentences = re.split(r"[.!?]+", plain)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) >= 3]
    num_sentences = max(1, len(sentences))
    words = re.findall(r"\b[a-zA-Z]+\b", plain)
    num_words = max(1, len(words))
    num_syllables = sum(count_syllables(w) for w in words)

    asl = num_words / num_sentences
    asw = num_syllables / num_words
    score = 206.835 - 1.015 * asl - 84.6 * asw
    return round(max(0.0, min(100.0, score)), 1)


def score_file(path: Path) -> dict:
    """Score a file. Returns dict with grade_level, reading_ease, word_count."""
    if not path.exists():
        return {"error": f"{path.name} not found"}
    text = path.read_text(encoding="utf-8")
    words = re.findall(r"\b[a-zA-Z]+\b", strip_markdown(text))
    return {
        "grade_level": flesch_kincaid_grade(text),
        "reading_ease": flesch_reading_ease(text),
        "word_count": len(words),
        "file": str(path),
    }


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        result = score_file(Path(arg))
        if "error" in result:
            print(result["error"])
        else:
            print(
                f"{result['file']}: "
                f"Grade {result['grade_level']}, "
                f"Ease {result['reading_ease']}, "
                f"{result['word_count']:,} words"
            )
