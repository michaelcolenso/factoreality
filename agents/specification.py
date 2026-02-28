"""Spec generation agent that orchestrates subagents to create spec.md from a brief."""

from __future__ import annotations

from pathlib import Path

from .base import BaseAgent

STRATEGIST_PROMPT = """You are Product Strategist, a subagent in a product factory.

Task: Convert a freeform product brief into a precise strategy memo.

Return markdown with exactly these sections:
- Product Type
- Topic & Angle
- Target Audience
- Tone & Voice
- Competitive Landscape
- Hard Constraints
- Deliverables
- Quality Thresholds
- Done When

Rules:
- Be concrete and measurable.
- Avoid placeholders.
- Prefer conservative defaults when detail is missing.
- Keep constraints realistic for a first product launch.
"""

SPEC_WRITER_PROMPT = """You are Spec Writer, a subagent in a product factory.

Task: Convert the strategy memo into a production-ready spec.md document.

Rules:
- Output valid Markdown only.
- Use exact level-2 headings for each section in this order:
  Product Type, Topic & Angle, Target Audience, Tone & Voice,
  Competitive Landscape, Hard Constraints, Deliverables,
  Quality Thresholds, Done When.
- Hard Constraints must include:
  - Length: X-Y words
  - Sections: A-B
  - Formats: markdown, pdf (unless memo specifies otherwise)
- Quality Thresholds must include:
  - Minimum gate confidence: 0.80 or higher
  - Max retry cycles: 3
  - Readability target: sentence with grade range
- Done When must be a markdown checklist.
"""


class SpecificationAgent(BaseAgent):
    """Creates a full spec.md from a short product brief using internal subagents."""

    name = "SpecificationAgent"

    def run(self, brief: str, dry_run: bool = False) -> Path:
        out = self.project_dir / "spec.md"
        if dry_run:
            self.write_file(out, self._stub_spec(brief))
            return out

        strategy_memo = self.call_llm(
            system_prompt=STRATEGIST_PROMPT,
            user_message=f"Create the strategy memo from this product brief:\n\n{brief}",
            max_tokens=2500,
        )
        spec_md = self.call_llm(
            system_prompt=SPEC_WRITER_PROMPT,
            user_message=(
                "Use this strategy memo to create a complete spec.md file:\n\n"
                f"{strategy_memo}"
            ),
            max_tokens=3500,
        )
        self.write_file(out, spec_md)
        return out

    def revise(
        self,
        feedback: str,
        output_path: Path,
        spec: dict,
        dry_run: bool = False,
    ) -> Path:
        raise NotImplementedError("SpecificationAgent does not use revise().")

    def _stub_spec(self, brief: str) -> str:
        title = brief.strip().split("\n", 1)[0][:80] or "Practical product topic"
        return f"""## Product Type
resource-guide

## Topic & Angle
{title}

## Target Audience
- Professionals with beginner-to-intermediate familiarity who need a practical starting point.

## Tone & Voice
- Actionable, clear, and evidence-based.

## Competitive Landscape
- Analyze top 5 alternatives and identify gaps in clarity, implementation, and proof.

## Hard Constraints
- Length: 4,500-6,000 words
- Sections: 7-10
- Formats: markdown, pdf

## Deliverables
1. Main guide with implementation steps
2. Quick-start checklist
3. References appendix

## Quality Thresholds
- Minimum gate confidence: 0.80
- Max retry cycles: 3
- Readability target: Grade 8-10

## Done When
- [ ] All deliverables listed above exist in output/
- [ ] No placeholders remain in any generated file
- [ ] Claims are sourced in the references appendix
"""
