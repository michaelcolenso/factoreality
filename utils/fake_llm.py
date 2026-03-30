"""Deterministic fake LLM responses for integration testing."""

from __future__ import annotations

import re


class FakeLLM:
    @staticmethod
    def respond(system_prompt: str, user_message: str) -> str:
        if "planning agent for the Content Factory pipeline" in system_prompt:
            return FakeLLM._plan()
        if "Research Analyst for the Content Factory pipeline" in system_prompt:
            return FakeLLM._research()
        if "Content Architect for the Content Factory pipeline" in system_prompt:
            return FakeLLM._outline(user_message)
        if "You are the Writer for the Content Factory pipeline." in system_prompt:
            if "Fix exactly the issues identified" in system_prompt:
                return FakeLLM._draft_revision(user_message)
            return FakeLLM._section(user_message)
        if "You are the Editor for the Content Factory pipeline." in system_prompt:
            return FakeLLM._editorial(user_message)
        if "You are the Formatter for the Content Factory pipeline." in system_prompt:
            return FakeLLM._formatted(user_message)
        if "You are the QA Reviewer for the Content Factory pipeline." in system_prompt:
            return FakeLLM._review(system_prompt)
        if "You are Product Strategist" in system_prompt:
            return FakeLLM._strategy_memo()
        if "You are Spec Writer" in system_prompt:
            return FakeLLM._spec_md()
        return "OK"

    @staticmethod
    def _plan() -> str:
        return """# Content Factory Plan

## Gate 0: Plan Validation
- [ ] Plan covers all deliverables listed in spec
- [ ] Word count allocations sum to spec range
- [ ] Section count within spec constraints
- [ ] Every milestone has machine-verifiable acceptance criteria

## Milestone 1: Research Complete
- [ ] 10+ sources identified and summarized
- [ ] Competitive products analyzed
- [ ] Audience pain points validated
- **Verification:** source count >= 10, competitive analysis table present, audience pain points section present

## Milestone 2: Outline Locked
- [ ] Structure finalized and mapped to deliverables
- **Verification:** section count in range, word allocations sum to target

## Milestone 3: First Draft Complete
- [ ] All sections written, no placeholders
- **Verification:** placeholder scan passes, word count within range

## Milestone 4: Editorial QA Complete
- [ ] Edited draft clean and consistent
- **Verification:** editorial notes present, no unresolved verify markers

## Milestone 5: Formatting Complete
- [ ] YAML front matter and output file generated
- **Verification:** markdown output exists, YAML front matter present

## Milestone 6: Package Assembled
- [ ] README and manifest generated
- **Verification:** output package files exist and are non-empty
"""

    @staticmethod
    def _research() -> str:
        sources = "\n".join(
            f"- [Source {i}](https://example.com/{i}) — Practical evidence item {i} — 2026-01-{i:02d}"
            for i in range(1, 11)
        )
        pains = "\n".join(
            f"> \"Pain Point {i}: people want a structured workflow.\" — [Community {i}](https://example.com/community/{i})"
            for i in range(1, 6)
        )
        glossary = "\n".join(
            f"- \"workflow phrase {i}\" — [Forum {i}](https://example.com/forum/{i})"
            for i in range(1, 4)
        )
        return f"""# Research Brief

## 1. Sources
{sources}

## 2. Competitive Analysis
| Product | Price | Format | Page/Module Count | Strengths | Gaps |
|---------|-------|--------|-------------------|-----------|------|
| Product A | $29 | PDF | 40 | Clear structure | Thin examples |
| Product B | $49 | PDF + templates | 65 | Templates | Weak research |
| Product C | $19 | PDF | 25 | Cheap | Generic advice |

## 3. Audience Pain Points
{pains}

## 4. Key Statistics & Data Points
- 68% of buyers prefer concrete implementation steps — [Survey](https://example.com/stat-1)
- Structured checklists improve completion rates — [Study](https://example.com/stat-2)

## 5. Audience Language Glossary
{glossary}
"""

    @staticmethod
    def _outline(user_message: str) -> str:
        min_words, max_words = FakeLLM._extract_word_range(user_message)
        total = max(min_words, min(max_words, 1500))
        allocations = [500, 500, total - 1000]
        return f"""# Outline

## Product Overview
- Product type: ebook
- Target length: {total} words
- Sections: 3

## Section Structure

### 1. Problem Framing
**Summary:** Defines the problem, context, and why the workflow matters.
**Word Count Allocation:** {allocations[0]} words
**Key Points:** problem, stakes, common mistakes
**Research Integration:** Sources 1-3
**Examples/Data:** Stat 1

### 2. Practical Workflow
**Summary:** Shows the repeatable step-by-step workflow with examples.
**Word Count Allocation:** {allocations[1]} words
**Key Points:** steps, decision points, examples
**Research Integration:** Sources 4-7
**Examples/Data:** Stat 2

### 3. Implementation Checklist
**Summary:** Turns the workflow into a concrete action plan.
**Word Count Allocation:** {allocations[2]} words
**Key Points:** checklist, rollout, troubleshooting
**Research Integration:** Sources 8-10
**Examples/Data:** community language

## Word Count Summary
| Section | Allocation |
|---------|------------|
| Problem Framing | {allocations[0]} |
| Practical Workflow | {allocations[1]} |
| Implementation Checklist | {allocations[2]} |
| **Total** | **{total}** |

## Structural Notes
- Logical flow rationale: start with the problem, move into process, end with action.
- Cross-reference map: section 3 references section 2.
- Deliverable mapping: all sections belong to the main guide deliverable.
"""

    @staticmethod
    def _section(user_message: str) -> str:
        title_match = re.search(r"Write section \d+ of \d+: (.+)", user_message)
        title = title_match.group(1).strip() if title_match else "Section"
        target_match = re.search(r"Target word count: (\d+) words", user_message)
        target = int(target_match.group(1)) if target_match else 500
        sentence = (
            f"{title} gives the reader a concrete move, a cited example, and a direct explanation "
            f"for why the workflow matters in practice [Source](https://example.com/source)."
        )
        words = sentence.split()
        count = max(target, len(words))
        repeated = []
        current = 0
        while current < count:
            repeated.append(sentence)
            current += len(words)
        body = " ".join(repeated)
        return f"## {title}\n\n{body}\n"

    @staticmethod
    def _draft_revision(user_message: str) -> str:
        draft_match = re.search(r"Current draft:\n\n(.+)", user_message, re.DOTALL)
        return draft_match.group(1).strip() if draft_match else "## Revised Draft\n\nClean revised copy."

    @staticmethod
    def _editorial(user_message: str) -> str:
        draft_match = re.search(r"Draft:\n\n(.+)", user_message, re.DOTALL)
        draft = draft_match.group(1).strip() if draft_match else "## Draft\n\nEdited copy."
        return f"""<<<EDITED_DRAFT_START>>>
{draft}
<<<EDITED_DRAFT_END>>>
<<<EDITORIAL_NOTES_START>>>
# Editorial Notes
- Copyedit: cleaned punctuation.
- Consistency: standardized workflow terminology.
- Fact-check: retained cited claims only.
<<<EDITORIAL_NOTES_END>>>
"""

    @staticmethod
    def _formatted(user_message: str) -> str:
        draft_match = re.search(r"Edited draft to format:\n\n(.+)\n\nReturn the fully formatted", user_message, re.DOTALL)
        draft = draft_match.group(1).strip() if draft_match else "# Draft\n\nFormatted copy."
        return f"""---
title: \"Integration Test Product\"
author: \"Content Factory\"
toc: true
---

{draft}
"""

    @staticmethod
    def _review(system_prompt: str) -> str:
        dimensions = re.findall(r"\| ([^|]+) \| [0-9.]+ \|", system_prompt)
        scores = {dim.strip(): 0.95 for dim in dimensions if dim.strip() != "Dimension"}
        return '{"verdict":"PASS","score":0.95,"dimension_scores":' + str(scores).replace("'", '"') + ',"feedback":"","passing_dimensions":' + str(list(scores.keys())).replace("'", '"') + ',"failing_dimensions":[]}'

    @staticmethod
    def _strategy_memo() -> str:
        return """## Product Type
resource-guide

## Topic & Angle
Integration-tested product workflow

## Target Audience
Builders who need a practical workflow.

## Tone & Voice
Direct and practical.

## Competitive Landscape
Most products are generic and unspecific.

## Hard Constraints
- Length: 1200-1600 words
- Sections: 3-3
- Formats: markdown

## Deliverables
1. Main markdown guide

## Quality Thresholds
- Minimum gate confidence: 0.85
- Max retry cycles: 2
- Readability target: Grade 8

## Done When
- [ ] Main guide exists
"""

    @staticmethod
    def _spec_md() -> str:
        return """## Product Type
resource-guide

## Topic & Angle
Integration-tested product workflow

## Target Audience
- Who: builders
- Needs: a practical workflow

## Tone & Voice
- Style: direct
- Reading level: grade 8

## Competitive Landscape
- Existing products: generic guides
- Differentiation: concrete implementation steps

## Hard Constraints
- Length: 1200-1600 words
- Sections: 3-3
- Formats: markdown

## Deliverables
1. Main markdown guide

## Quality Thresholds
- Minimum gate confidence: 0.85
- Max retry cycles: 2
- Readability target: Grade 8

## Done When
- [ ] Main guide exists as a final file
- [ ] No placeholder text anywhere
"""

    @staticmethod
    def _extract_word_range(text: str) -> tuple[int, int]:
        match = re.search(r"Length: .*?(\d[\d,]*)-(\d[\d,]*) words", text)
        if not match:
            return 1200, 1600
        return int(match.group(1).replace(',', '')), int(match.group(2).replace(',', ''))
