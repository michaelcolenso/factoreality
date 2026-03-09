"""QA Reviewer agent — the autonomous human replacement at every gate.

A SEPARATE agent instance (distinct system prompt, fresh context) that evaluates
each stage's output against the spec and plan using structured rubrics.

Returns a verdict (PASS / REVISE / FAIL), a composite score, per-dimension scores,
and targeted feedback for revisions.
"""

from __future__ import annotations

import json
from pathlib import Path

from .base import BaseAgent
from gates.rubrics import RUBRICS

SYSTEM_PROMPT_TEMPLATE = """You are the QA Reviewer for the Content Factory pipeline.

You are a SEPARATE agent from every production agent. You evaluate objectively.
Your job is NOT to be encouraging — it is to catch failures before they compound.

## Your mandate at every gate:
1. Read spec.md to understand what was supposed to be produced.
2. Read the stage output to understand what was actually produced.
3. Score the output on the rubric below — dimension by dimension.
4. Produce a verdict: PASS, REVISE, or FAIL.

## Verdict rules:
- PASS: composite score >= quality_threshold AND no critical dimension scores below 0.5
- REVISE: composite score < threshold OR any critical dimension < 0.5
  → List specific, actionable fixes for each failing dimension
  → Do NOT request changes to passing dimensions
- FAIL: only if the output is fundamentally unusable
  (e.g., completely off-spec, empty, all placeholders, factually catastrophic)

## Gate {gate_number} Rubric:
{rubric_text}

## Quality threshold: {quality_threshold}

## Output format (JSON only, no other text):
{{
  "verdict": "PASS" | "REVISE" | "FAIL",
  "score": 0.00,
  "dimension_scores": {{
    "dimension_name": 0.00,
    ...
  }},
  "feedback": "Specific, actionable instructions for the stage agent. Empty if PASS.",
  "passing_dimensions": ["list of dimension names that passed"],
  "failing_dimensions": ["list of dimension names that need work"]
}}
"""


class QAReviewerAgent(BaseAgent):
    name = "QAReviewerAgent"
    # Always use the best available model — never economize on the reviewer
    default_model = "claude-opus-4-6"

    def review_gate(
        self,
        gate_number: int,
        spec: dict,
        stage_output_path: Path,
        rubric_key: str,
        dry_run: bool = False,
    ) -> dict:
        """
        Evaluate stage output at the specified gate.

        Returns a dict with keys: verdict, score, dimension_scores, feedback,
        passing_dimensions, failing_dimensions.
        """
        rubric = RUBRICS.get(rubric_key, RUBRICS["research"])
        quality_threshold = spec.get("quality_thresholds", {}).get("min_gate_confidence", 0.8)

        rubric_text = self._format_rubric(rubric)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            gate_number=gate_number,
            rubric_text=rubric_text,
            quality_threshold=quality_threshold,
        )

        spec_text = self.read_spec()
        plan_text = self.read_plan()
        if stage_output_path.is_file():
            stage_output = self.read_file(stage_output_path)
        elif stage_output_path.is_dir():
            entries = sorted(
                str(path.relative_to(stage_output_path))
                for path in stage_output_path.rglob("*")
                if path.is_file()
            )
            preview = "\n".join(f"- {entry}" for entry in entries[:200])
            stage_output = (
                f"(directory listing)\n{preview}"
                if preview
                else "(directory exists but has no files)"
            )
        else:
            stage_output = "(file not found)"

        if dry_run:
            return {
                "verdict": "PASS",
                "score": 1.0,
                "dimension_scores": {
                    dim["name"]: 1.0 for dim in rubric
                },
                "feedback": "",
                "passing_dimensions": [dim["name"] for dim in rubric],
                "failing_dimensions": [],
            }

        response = self.call_llm(
            system_prompt=system_prompt,
            user_message=(
                f"## spec.md\n\n{spec_text}\n\n"
                f"## plan.md\n\n{plan_text}\n\n"
                f"## Stage Output ({stage_output_path.name})\n\n{stage_output}"
            ),
            max_tokens=2048,
        )

        return self._parse_response(response, quality_threshold)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_rubric(self, rubric: list[dict]) -> str:
        lines = ["| Dimension | Weight | What It Measures |",
                 "|-----------|--------|-----------------|"]
        for dim in rubric:
            lines.append(
                f"| {dim['name']} | {dim['weight']} | {dim['measures']} |"
            )
        return "\n".join(lines)

    def _parse_response(self, response: str, quality_threshold: float) -> dict:
        """Parse JSON response from the reviewer LLM."""
        # Strip any markdown code fences
        text = response.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            # Strip closing fence
            if "```" in text:
                text = text.rsplit("```", 1)[0]
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Fallback: extract key fields with heuristics
            verdict = "FAIL"
            if '"PASS"' in response:
                verdict = "PASS"
            elif '"REVISE"' in response:
                verdict = "REVISE"
            return {
                "verdict": verdict,
                "score": 0.0,
                "dimension_scores": {},
                "feedback": f"QA Reviewer response could not be parsed as JSON. Raw: {response[:500]}",
                "passing_dimensions": [],
                "failing_dimensions": [],
            }

        # Ensure required fields exist
        data.setdefault("verdict", "FAIL")
        data.setdefault("score", 0.0)
        data.setdefault("dimension_scores", {})
        data.setdefault("feedback", "")
        data.setdefault("passing_dimensions", [])
        data.setdefault("failing_dimensions", [])

        # Safety check: if score passes threshold but verdict is REVISE, trust the score
        if data["score"] >= quality_threshold and data["verdict"] == "REVISE":
            # Check if any critical dimension is below 0.5
            if not any(s < 0.5 for s in data["dimension_scores"].values()):
                data["verdict"] = "PASS"

        return data
