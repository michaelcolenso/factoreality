"""Stage 1: Research & Discovery agent.

Produces research/research-brief.md containing:
- Source list with summaries (≥10 sources)
- Competitive analysis matrix (≥3 products)
- Audience pain points with citations
- Key statistics and data points
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseAgent

SYSTEM_PROMPT = """You are the Research Analyst for the Content Factory pipeline.

Your task: produce a comprehensive research brief for a digital knowledge product.

Output format — research/research-brief.md — must contain these sections in order:

## 1. Sources
List every source as:
- [Title](URL) — one-sentence summary — date

Minimum 10 sources. Prefer primary sources published within the last 18 months
(exceptions allowed for established data or historical context; flag these).

## 2. Competitive Analysis
For each comparable product:
| Product | Price | Format | Page/Module Count | Strengths | Gaps |
|---------|-------|--------|-------------------|-----------|------|

Minimum 3 entries with pricing data.

## 3. Audience Pain Points
Each pain point as:
> "Exact quote or paraphrase from community source" — [Source Name](URL)

Minimum 5 pain points with citations.

## 4. Key Statistics & Data Points
Bullet list of statistics and data relevant to the topic.
Every item must cite its source.

## 5. Audience Language Glossary
Exact phrases, jargon, and questions real people in the target audience use.
Source each phrase to a community thread, forum post, or survey.

Operating rules:
- Every URL must be real and reachable. Do not fabricate sources.
- Do not include statistics you cannot source.
- Do not editorialize — report what the research shows.
- If a claim cannot be sourced, omit it rather than fabricate a citation.
"""

REVISE_SYSTEM_PROMPT = """You are the Research Analyst for the Content Factory pipeline.

You previously produced a research brief that was reviewed and returned with
the following feedback. Your job is to fix exactly the issues identified —
do not rewrite sections that were not flagged.

Apply the minimal set of changes needed to satisfy the reviewer's feedback.
"""


class ResearchAgent(BaseAgent):
    name = "ResearchAgent"
    default_model = "claude-opus-4-6"

    OUTPUT_PATH = "research/research-brief.md"

    def run(self, spec: dict, dry_run: bool = False) -> Path:
        out = self.project_dir / self.OUTPUT_PATH
        if dry_run:
            self.write_file(out, self._stub(spec))
            return out

        spec_text = self.read_spec()
        content = self.call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_message=(
                f"Produce a research brief for the following product spec:\n\n{spec_text}"
            ),
            max_tokens=8192,
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
                f"Current research brief:\n\n{current}"
            ),
            max_tokens=8192,
        )
        self.write_file(output_path, content)
        return output_path

    def _stub(self, spec: dict) -> str:
        topic = spec.get("topic_angle", "the specified topic")
        return f"""# Research Brief (dry-run stub)

## 1. Sources
- [Example Source 1](https://example.com/1) — Overview of {topic} — 2025-01
- [Example Source 2](https://example.com/2) — Market data — 2025-03
- [Example Source 3](https://example.com/3) — Community discussion — 2025-06
- [Example Source 4](https://example.com/4) — Competitor review — 2025-07
- [Example Source 5](https://example.com/5) — Academic paper — 2024-12
- [Example Source 6](https://example.com/6) — Industry report — 2025-02
- [Example Source 7](https://example.com/7) — Forum thread — 2025-08
- [Example Source 8](https://example.com/8) — Survey data — 2025-04
- [Example Source 9](https://example.com/9) — Case study — 2025-09
- [Example Source 10](https://example.com/10) — Expert interview — 2025-10

## 2. Competitive Analysis
| Product | Price | Format | Page Count | Strengths | Gaps |
|---------|-------|--------|------------|-----------|------|
| Product A | $27 | PDF | 45 | Comprehensive | No exercises |
| Product B | $47 | PDF+DOCX | 80 | Templates included | Outdated data |
| Product C | $19 | PDF | 30 | Affordable | Thin on examples |

## 3. Audience Pain Points
> "I can never find a guide that covers the practical side, not just theory." — [Reddit](https://example.com)
> "Every resource I find is either too basic or too advanced." — [Forum](https://example.com)
> "I need templates, not just explanations." — [Community thread](https://example.com)
> "The examples are always for big companies, not my situation." — [Survey](https://example.com)
> "I've bought 3 guides and still can't get results." — [Review](https://example.com)

## 4. Key Statistics & Data Points
- Stat 1 with citation — [Source](https://example.com)
- Stat 2 with citation — [Source](https://example.com)

## 5. Audience Language Glossary
- "phrase 1" — [Source](https://example.com)
- "phrase 2" — [Source](https://example.com)
"""
