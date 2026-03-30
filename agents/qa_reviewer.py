"""QA Reviewer agent — the autonomous human replacement at every gate.

A SEPARATE agent instance (distinct system prompt, fresh context) that evaluates
each stage's output against the spec and plan using structured rubrics.

Returns a verdict (PASS / REVISE / FAIL), a composite score, per-dimension scores,
and targeted feedback for revisions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import BaseAgent
from gates.rubrics import RUBRICS

SYSTEM_PROMPT_TEMPLATE = """You are the QA Reviewer for the Content Factory pipeline.

You are a SEPARATE agent from every production agent. You evaluate objectively.
Your job is NOT to be encouraging — it is to catch failures before they compound.

## Your mandate at every gate:
1. Read spec.md to understand what was supposed to be produced.
2. Read the stage output to understand what was actually produced.
3. Read the deterministic gate-check summary and use it as hard evidence.
4. Score the output on the rubric below — dimension by dimension.
5. Produce a verdict: PASS, REVISE, or FAIL.

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
        gate_checks: dict | None = None,
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
        stage_output = self._read_stage_output(stage_output_path)
        gate_checks = gate_checks or {"passed": [], "failed": [], "summary": "No deterministic checks were run."}

        response = self.call_llm(
            system_prompt=system_prompt,
            user_message=(
                f"## spec.md\n\n{spec_text}\n\n"
                f"## plan.md\n\n{plan_text}\n\n"
                f"## Deterministic Gate Checks\n\n{gate_checks.get('summary', '')}\n\n"
                f"## Stage Output ({stage_output_path.name})\n\n{stage_output}"
            ),
            max_tokens=2048,
        )

        return self._parse_response(response, quality_threshold, rubric)

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

    def _read_stage_output(self, stage_output_path: Path) -> str:
        if not stage_output_path.exists():
            return "(file not found)"
        if stage_output_path.is_dir():
            entries = []
            for child in sorted(stage_output_path.rglob("*")):
                if child.is_file():
                    rel = child.relative_to(stage_output_path)
                    entries.append(f"- {rel} ({child.stat().st_size} bytes)")
            listing = "\n".join(entries) if entries else "(empty directory)"
            return f"Directory listing for {stage_output_path.name}:\n{listing}"
        return self.read_file(stage_output_path)

    def _parse_response(self, response: str, quality_threshold: float, rubric: list[dict]) -> dict:
        """Parse and validate JSON response from the reviewer LLM."""
        text = response.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            if "```" in text:
                text = text.rsplit("```", 1)[0]
            text = text.strip()

        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return self._invalid_response(
                f"QA Reviewer response could not be parsed as JSON. Raw: {response[:500]}"
            )

        if not isinstance(raw, dict):
            return self._invalid_response("QA Reviewer response must be a JSON object.")

        data: dict[str, Any] = {
            "verdict": raw.get("verdict", "FAIL"),
            "score": raw.get("score", 0.0),
            "dimension_scores": raw.get("dimension_scores", {}),
            "feedback": raw.get("feedback", ""),
            "passing_dimensions": raw.get("passing_dimensions", []),
            "failing_dimensions": raw.get("failing_dimensions", []),
        }

        if data["verdict"] not in {"PASS", "REVISE", "FAIL"}:
            return self._invalid_response(f"Invalid verdict: {data['verdict']!r}")

        try:
            data["score"] = float(data["score"])
        except (TypeError, ValueError):
            return self._invalid_response("Reviewer score must be numeric.")

        if not isinstance(data["dimension_scores"], dict):
            return self._invalid_response("dimension_scores must be an object.")

        normalized_scores: dict[str, float] = {}
        rubric_names = {dim["name"] for dim in rubric}
        for name, score in data["dimension_scores"].items():
            if name not in rubric_names:
                continue
            try:
                value = float(score)
            except (TypeError, ValueError):
                return self._invalid_response(f"Invalid dimension score for {name!r}.")
            if value < 0.0 or value > 1.0:
                return self._invalid_response(f"Dimension score for {name!r} must be between 0.0 and 1.0.")
            normalized_scores[name] = value
        data["dimension_scores"] = normalized_scores

        if not isinstance(data["feedback"], str):
            data["feedback"] = str(data["feedback"])

        for key in ("passing_dimensions", "failing_dimensions"):
            if not isinstance(data[key], list):
                return self._invalid_response(f"{key} must be an array.")
            data[key] = [str(item) for item in data[key]]

        critical_dimensions = {dim["name"] for dim in rubric if dim.get("critical")}
        has_critical_failure = any(
            data["dimension_scores"].get(name, 0.0) < 0.5 for name in critical_dimensions
        )

        if data["verdict"] == "PASS" and (data["score"] < quality_threshold or has_critical_failure):
            data["verdict"] = "REVISE"
        elif data["verdict"] == "REVISE" and data["score"] >= quality_threshold and not has_critical_failure:
            data["verdict"] = "PASS"

        if data["verdict"] != "PASS" and not data["feedback"].strip():
            data["feedback"] = "Reviewer requested changes but did not provide actionable feedback. Re-run the review."

        return data

    def _invalid_response(self, message: str) -> dict:
        return {
            "verdict": "FAIL",
            "score": 0.0,
            "dimension_scores": {},
            "feedback": message,
            "passing_dimensions": [],
            "failing_dimensions": [],
        }
