"""Scan a document for placeholder text that should not appear in final output."""

from __future__ import annotations

import re
from pathlib import Path

PLACEHOLDER_PATTERNS = [
    r"\bTODO\b",
    r"\bTBD\b",
    r"\bFIXME\b",
    r"\[INSERT\b",
    r"\[EXAMPLE\b",
    r"\[YOUR\b",
    r"\[ADD\b",
    r"\bPLACEHOLDER\b",
    r"\[CITATION NEEDED\]",
    r"\[VERIFY:",
    r"Lorem ipsum",
]

COMPILED = re.compile("|".join(PLACEHOLDER_PATTERNS), re.IGNORECASE)


def scan_for_placeholders(text: str) -> list[tuple[int, str]]:
    """
    Scan text for placeholder patterns.

    Returns a list of (line_number, matched_line) tuples.
    Empty list means clean.
    """
    results = []
    for i, line in enumerate(text.split("\n"), start=1):
        if COMPILED.search(line):
            results.append((i, line.strip()))
    return results


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Scan a file for placeholder text. Returns list of (line, text) tuples."""
    if not path.exists():
        return []
    return scan_for_placeholders(path.read_text(encoding="utf-8"))


def report(path: Path) -> str:
    """Return a human-readable scan report for a file."""
    hits = scan_file(path)
    if not hits:
        return f"✓ {path.name}: no placeholder text found"
    lines = [f"✗ {path.name}: {len(hits)} placeholder(s) found:"]
    for line_num, text in hits:
        lines.append(f"  Line {line_num}: {text[:100]}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        print(report(Path(arg)))
