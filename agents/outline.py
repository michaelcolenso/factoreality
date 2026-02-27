"""Stage 2: Outline & Structure agent.

Produces outline/outline.md — the FROZEN structural blueprint that all
downstream agents follow exactly.
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseAgent

SYSTEM_PROMPT = """You are the Content Architect for the Content Factory pipeline.

Your task: produce the definitive outline for a digital knowledge product.

This outline will be LOCKED after QA review. Every downstream agent —
the writer, editor, and formatter — follows this outline exactly.
No structural changes are permitted after this stage passes its QA gate.

Output format — outline/outline.md — must contain:

## Product Overview
- Product type, target length, number of sections

## Section Structure
For each chapter/section/module:
### [Number]. [Title]
**Summary:** 2–3 sentences describing the specific content of this section.
**Word Count Allocation:** [N] words
**Key Points:** bullet list of 3–5 specific points to cover
**Research Integration:** cite which research brief items this section draws on
**Examples/Data:** specific examples, case studies, or statistics to include

## Word Count Summary
| Section | Allocation |
|---------|------------|
| [each section] | [N words] |
| **Total** | **[sum] words** |

## Structural Notes
- Logical flow rationale (why this order)
- Cross-reference map (sections that reference each other)
- Deliverable mapping (which sections belong to which deliverable files)

Rules:
- Section count must be within the spec's hard constraints.
- Word count allocations must sum to within ±10% of the spec's total.
- Every spec deliverable must have a corresponding section or group of sections.
- Section summaries must be specific and concrete — not "overview of X" but
  "explains the three-step framework for X with a worked example for Y audience."
- Do not invent content not supported by the research brief.
- Do not duplicate content across sections (max 20% topic overlap between any two sections).
"""

REVISE_SYSTEM_PROMPT = """You are the Content Architect for the Content Factory pipeline.

Your outline was reviewed and returned with the following feedback.
Fix exactly the issues identified. Do not restructure sections that passed review.
The final outline will be locked after this revision passes the QA gate.
"""


class OutlineAgent(BaseAgent):
    name = "OutlineAgent"
    default_model = "claude-opus-4-6"

    OUTPUT_PATH = "outline/outline.md"

    def run(self, spec: dict, dry_run: bool = False) -> Path:
        out = self.project_dir / self.OUTPUT_PATH
        if dry_run:
            self.write_file(out, self._stub(spec))
            return out

        spec_text = self.read_spec()
        research_path = self.project_dir / "research/research-brief.md"
        research_text = self.read_file(research_path) if research_path.exists() else "(no research brief found)"

        content = self.call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_message=(
                f"Spec:\n\n{spec_text}\n\n"
                f"Research Brief:\n\n{research_text}"
            ),
            max_tokens=6144,
        )
        self.write_file(out, content)
        return out

    def revise(
        self,
        feedback: str,
        output_path: Path,
        spec: dict,
        dry_run: bool = False,
    ) -> Path:
        if dry_run:
            return output_path

        current = self.read_file(output_path)
        spec_text = self.read_spec()
        content = self.call_llm(
            system_prompt=REVISE_SYSTEM_PROMPT,
            user_message=(
                f"Spec:\n\n{spec_text}\n\n"
                f"Reviewer feedback:\n{feedback}\n\n"
                f"Current outline:\n\n{current}"
            ),
            max_tokens=6144,
        )
        self.write_file(output_path, content)
        return output_path

    def _stub(self, spec: dict) -> str:
        product_type = spec.get("product_type", "ebook")
        return f"""# Outline (dry-run stub)

## Product Overview
- Type: {product_type}
- Target length: 15,000 words
- Sections: 7

## Section Structure

### 1. Introduction
**Summary:** Sets context, explains what the reader will learn and why it matters.
**Word Count Allocation:** 1,500 words
**Key Points:** Hook, problem statement, promise, roadmap
**Research Integration:** Pain points section of research brief
**Examples/Data:** Opening statistic from Key Statistics section

### 2. Chapter 1
**Summary:** First major concept with practical application.
**Word Count Allocation:** 2,000 words
**Key Points:** Concept, framework, application, common mistakes
**Research Integration:** Sources 1-3 from research brief
**Examples/Data:** Case study from research

### 3. Chapter 2
**Summary:** Second major concept building on Chapter 1.
**Word Count Allocation:** 2,000 words
**Key Points:** Concept, step-by-step process, worked example
**Research Integration:** Sources 4-6 from research brief
**Examples/Data:** Real-world data point

### 4. Chapter 3
**Summary:** Third major concept with templates.
**Word Count Allocation:** 2,000 words
**Key Points:** Templates, customization guide, examples
**Research Integration:** Competitive gaps from research
**Examples/Data:** Before/after comparison

### 5. Chapter 4
**Summary:** Advanced application and troubleshooting.
**Word Count Allocation:** 2,000 words
**Key Points:** Advanced tactics, edge cases, troubleshooting
**Research Integration:** Sources 7-10 from research brief
**Examples/Data:** Expert quotes

### 6. Implementation Guide
**Summary:** Step-by-step action plan for the reader.
**Word Count Allocation:** 3,000 words
**Key Points:** 30-day action plan, milestones, checklists
**Research Integration:** Audience language from research brief
**Examples/Data:** Timeline example

### 7. Conclusion & Resources
**Summary:** Summary, next steps, resource list.
**Word Count Allocation:** 2,500 words
**Key Points:** Key takeaways, next actions, further reading
**Research Integration:** All sources
**Examples/Data:** Summary framework

## Word Count Summary
| Section | Allocation |
|---------|------------|
| Introduction | 1,500 |
| Chapter 1 | 2,000 |
| Chapter 2 | 2,000 |
| Chapter 3 | 2,000 |
| Chapter 4 | 2,000 |
| Implementation Guide | 3,000 |
| Conclusion & Resources | 2,500 |
| **Total** | **15,000** |
"""
