"""Shared pytest fixtures for the Content Factory test suite."""

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Minimal valid spec text
# ---------------------------------------------------------------------------

VALID_SPEC = """\
# Content Factory Spec

## Product Type
ebook

## Topic & Angle
Cold email sequences for B2B SaaS founders targeting enterprise procurement teams.

## Target Audience
- Who: B2B SaaS founders, 1-5 years experience
- Already knows: basic email marketing concepts
- Needs: systematic cold outreach that converts enterprise prospects
- Willing to pay: $47-97

## Tone & Voice
- Style: professional
- Person: second
- Reading level: grade 12

## Competitive Landscape
- Existing products: Cold Email Mastery ($37), Enterprise Outreach Bible ($97)
- Differentiation: focuses specifically on procurement team decision-makers

## Hard Constraints
- Length: 10000-15000 words
- Sections: 5-10 chapters
- Formats: PDF, DOCX
- Brand: none

## Deliverables
1. 50-page PDF ebook
2. 5 email template DOCX files
3. Resource links document

## Quality Thresholds
- Minimum gate confidence: 0.85
- Readability target: Flesch-Kincaid grade 12
- Max retry cycles per gate: 3

## Done When
- [ ] All deliverables exist as final files
- [ ] No placeholder text anywhere
- [ ] Table of contents matches actual content
"""


@pytest.fixture()
def valid_spec_text():
    return VALID_SPEC


@pytest.fixture()
def spec_file(tmp_path, valid_spec_text):
    """Write a valid spec.md to a temp directory and return its Path."""
    p = tmp_path / "spec.md"
    p.write_text(valid_spec_text, encoding="utf-8")
    return p


@pytest.fixture()
def project_dir(tmp_path, valid_spec_text):
    """A minimal project directory with spec.md in place."""
    (tmp_path / "spec.md").write_text(valid_spec_text, encoding="utf-8")
    for subdir in ("research", "outline", "draft", "editorial", "output", "qa-reviews"):
        (tmp_path / subdir).mkdir()
    return tmp_path
