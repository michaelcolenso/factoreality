"""Gate 0: Plan generator agent.

Auto-generates plan.md from spec.md. The QA Reviewer then validates it before
any production stages begin.
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseAgent

SYSTEM_PROMPT = """You are the planning agent for the Content Factory pipeline.

Your job: read a product spec and produce a detailed plan.md that the orchestrator
will use to sequence all six production stages.

Rules:
- Every milestone must have machine-verifiable acceptance criteria (counts, scans,
  scores) — no subjective milestones like "content feels good."
- Word count allocations per section must sum to the spec's total word count range.
- Section count must be within the spec's hard constraints.
- Every deliverable listed in the spec must appear in the plan.
- The plan must cover all six stages: Research, Outline, Content, Editorial,
  Formatting, Assembly.
- Do not add deliverables or sections not mentioned in the spec.
- Output valid Markdown only. No commentary outside the Markdown document.
"""


class PlannerAgent(BaseAgent):
    name = "PlannerAgent"

    def generate(self, spec: dict, feedback: str = "", dry_run: bool = False) -> str:
        if dry_run:
            return self._stub_plan(spec)

        spec_text = self.read_spec()
        feedback_section = (
            f"\n\n---\nPrevious plan was rejected with this feedback:\n{feedback}\n"
            "Revise accordingly."
            if feedback
            else ""
        )

        return self.call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_message=f"Here is the product spec:\n\n{spec_text}{feedback_section}",
            max_tokens=4096,
        )

    def run(self, spec: dict, dry_run: bool = False) -> Path:
        content = self.generate(spec, dry_run=dry_run)
        out = self.project_dir / "plan.md"
        if not dry_run:
            self.write_file(out, content)
        return out

    def revise(self, feedback: str, output_path: Path, spec: dict, dry_run: bool = False) -> Path:
        content = self.generate(spec, feedback=feedback, dry_run=dry_run)
        if not dry_run:
            self.write_file(output_path, content)
        return output_path

    # ------------------------------------------------------------------

    def _stub_plan(self, spec: dict) -> str:
        product_type = spec.get("product_type", "ebook")
        return f"""# Content Factory Plan (dry-run stub)

## Gate 0: Plan Validation
- [ ] Plan covers all deliverables listed in spec
- [ ] Word count allocations sum to spec range
- [ ] Section count within spec constraints
- [ ] Every milestone has machine-verifiable acceptance criteria

## Milestone 1: Research Complete
- [ ] 10+ sources identified and summarized
- [ ] Competitive products analyzed
- [ ] Audience pain points validated
- **Verification:** source count >= 10, all URLs return HTTP 200

## Milestone 2: Outline Locked
- [ ] Structure finalized for {product_type}
- **Verification:** section count in spec range, word estimates sum within ±10%

## Milestone 3: First Draft Complete
- [ ] All sections written, no placeholders
- **Verification:** placeholder scan passes, word count within range

## Milestone 4: Editorial QA Complete
- [ ] Grammar/spelling clean, readability on target
- **Verification:** spell check = 0 errors, readability score in range

## Milestone 5: Formatting Complete
- [ ] Layout applied, TOC accurate
- **Verification:** files generate without errors, TOC matches headings

## Milestone 6: Package Assembled
- [ ] All deliverables in output/
- **Verification:** every spec deliverable exists, all files open cleanly
"""
