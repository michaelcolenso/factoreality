#!/usr/bin/env python3
"""
Content Factory Orchestrator — Autonomous Mode

Reads spec.md, generates plan.md, then executes the 6-stage pipeline with
QA gates at every milestone. Writes status.md throughout.

Usage:
    python orchestrator.py [project_dir]
    python orchestrator.py --dry-run [project_dir]
    python orchestrator.py --resume [project_dir]
    python orchestrator.py --brief-file product-brief.md [project_dir]
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from agents.research import ResearchAgent
from agents.outline import OutlineAgent
from agents.content import ContentAgent
from agents.editorial import EditorialAgent
from agents.formatter import FormatterAgent
from agents.assembler import AssemblerAgent
from agents.qa_reviewer import QAReviewerAgent
from agents.specification import SpecificationAgent
from gates.gate import GateRunner
from utils.file_io import FileIO
from utils.spec_parser import SpecParser


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Orchestrator:
    """
    Sequentially executes the Content Factory pipeline.

    State machine:
      INIT → PLAN → STAGE_1 → GATE_1 → STAGE_2 → GATE_2 → ...
      → STAGE_6 → GATE_6 → DONE (or HALTED on failure)
    """

    STAGES = [
        ("research",   "Stage 1: Research & Discovery",    "gate-1"),
        ("outline",    "Stage 2: Outline & Structure",     "gate-2"),
        ("content",    "Stage 3: Content Generation",      "gate-3"),
        ("editorial",  "Stage 4: Editorial & QA",          "gate-4"),
        ("formatting", "Stage 5: Design & Formatting",     "gate-5"),
        ("assembly",   "Stage 6: Assembly & Export",       "gate-6"),
    ]

    def __init__(
        self,
        project_dir: Path,
        dry_run: bool = False,
        resume: bool = False,
        brief: str = "",
        regenerate_spec: bool = False,
    ):
        self.project_dir = project_dir
        self.dry_run = dry_run
        self.resume = resume
        self.brief = brief
        self.regenerate_spec = regenerate_spec

        self.io = FileIO(project_dir)
        self.spec = None
        self.plan = None

        self.agents = {
            "research":   ResearchAgent(project_dir),
            "outline":    OutlineAgent(project_dir),
            "content":    ContentAgent(project_dir),
            "editorial":  EditorialAgent(project_dir),
            "formatting": FormatterAgent(project_dir),
            "assembly":   AssemblerAgent(project_dir),
        }
        self.qa = QAReviewerAgent(project_dir)
        self.gate_runner = GateRunner(project_dir)
        self.spec_agent = SpecificationAgent(project_dir)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> bool:
        """Execute the full pipeline. Returns True on success, False on failure."""
        self._log_run_start()

        if not self._ensure_spec_exists():
            return False

        try:
            self.spec = SpecParser(self.project_dir / "spec.md").parse()
        except ValueError as exc:
            self._halt(f"spec.md is invalid: {exc}")
            return False

        if self.resume:
            return self._resume_from_state()

        # Gate 0: generate and validate the plan
        if not self._run_gate_zero():
            return False

        # Stages 1–6
        for stage_key, stage_name, gate_key in self.STAGES:
            if not self._run_stage(stage_key, stage_name, gate_key):
                return False

        self._log_success()
        return True

    def _ensure_spec_exists(self) -> bool:
        spec_path = self.project_dir / "spec.md"
        has_existing_spec = spec_path.exists()
        has_brief = bool(self.brief.strip())

        if has_existing_spec and not self.regenerate_spec:
            return True

        if self.regenerate_spec and not has_brief:
            self._halt(
                "--regenerate-spec requires --brief or --brief-file. "
                "Provide a brief to overwrite spec.md."
            )
            return False

        if not has_existing_spec and not has_brief:
            self._halt(
                "spec.md not found. Create it from templates/spec_template.md or "
                "run with --brief/--brief-file to auto-generate a spec."
            )
            return False

        action = "Regenerating" if has_existing_spec else "Generating"
        self.io.append_status(f"{action} spec.md from product brief via SpecificationAgent.\n")
        self.spec_agent.run(brief=self.brief, dry_run=self.dry_run)
        return True

    # ------------------------------------------------------------------
    # Gate 0 — plan generation and validation
    # ------------------------------------------------------------------

    def _run_gate_zero(self) -> bool:
        self.io.append_status(f"\n## Gate 0 — Plan Validation\n**Started:** {utcnow()}\n")
        self.io.set_stage_state("plan", "running", started_at=utcnow())

        plan_path = self.project_dir / "plan.md"
        if plan_path.exists() and not self.dry_run:
            self.io.append_status("Existing plan.md found, using it.\n")
        else:
            self.io.append_status("Generating plan.md from spec...\n")
            if not self.dry_run:
                plan_content = self._generate_plan()
                plan_path.write_text(plan_content, encoding="utf-8")

        # Gate 0 has only 2 retries; if it keeps failing the spec is the problem
        for attempt in range(0, 3):
            gate_checks = self.gate_runner.run_checks(0, self.spec)
            self.io.append_status(gate_checks["summary"] + "\n")

            review = self.qa.review_gate(
                gate_number=0,
                spec=self.spec,
                stage_output_path=plan_path,
                rubric_key="plan",
                gate_checks=gate_checks,
            )
            self._persist_gate_review(0, review, attempt=attempt)

            if review["verdict"] == "PASS":
                self.io.append_status(f"Gate 0 PASSED (score: {review['score']:.2f})\n")
                self.io.set_stage_state(
                    "plan",
                    "passed",
                    completed_at=utcnow(),
                    score=review["score"],
                    attempt=attempt + 1,
                )
                return True

            if attempt == 2 or review["verdict"] == "FAIL":
                self.io.set_stage_state(
                    "plan",
                    "failed",
                    completed_at=utcnow(),
                    score=review.get("score", 0.0),
                    attempt=attempt + 1,
                    feedback=review.get("feedback", ""),
                )
                self._halt(
                    f"Gate 0 FAILED after max retries.\n"
                    f"Last score: {review['score']:.2f}\n"
                    f"Feedback: {review['feedback']}\n"
                    f"Recommendation: Rewrite spec.md with more specific constraints."
                )
                return False

            self.io.append_status(
                f"Gate 0 REVISE (attempt {attempt + 1}): {review['feedback']}\n"
            )
            if not self.dry_run:
                plan_content = self._generate_plan(feedback=review["feedback"])
                plan_path.write_text(plan_content, encoding="utf-8")

        return False

    # ------------------------------------------------------------------
    # Stages 1–6
    # ------------------------------------------------------------------

    def _run_stage(self, stage_key: str, stage_name: str, gate_key: str) -> bool:
        max_retries = self.spec.get("quality_thresholds", {}).get("max_retry_cycles", 3)
        self.io.append_status(f"\n## {stage_name}\n**Started:** {utcnow()}\n")
        self.io.set_stage_state(stage_key, "running", started_at=utcnow())

        agent = self.agents[stage_key]
        gate_number = int(gate_key.split("-")[1])

        # Run the stage
        try:
            output_path = agent.run(spec=self.spec, dry_run=self.dry_run)
        except Exception as exc:
            self.io.set_stage_state(stage_key, "failed", completed_at=utcnow(), error=str(exc))
            self._halt(f"{stage_name} agent raised an unhandled exception: {exc}")
            return False

        self.io.append_status(f"Stage output: {output_path}\n")

        # QA gate loop
        for attempt in range(max_retries + 1):
            gate_checks = self.gate_runner.run_checks(gate_number, self.spec)
            self.io.append_status(gate_checks["summary"] + "\n")

            review = self.qa.review_gate(
                gate_number=gate_number,
                spec=self.spec,
                stage_output_path=output_path,
                rubric_key=stage_key,
                gate_checks=gate_checks,
            )
            self._persist_gate_review(gate_number, review, attempt=attempt)

            if review["verdict"] == "PASS":
                self.io.append_status(
                    f"{gate_key} PASSED (score: {review['score']:.2f}, "
                    f"attempt: {attempt + 1})\n"
                )
                self.io.set_stage_state(
                    stage_key,
                    "passed",
                    completed_at=utcnow(),
                    score=review["score"],
                    attempt=attempt + 1,
                    output_path=str(output_path.relative_to(self.project_dir)),
                )
                return True

            if review["verdict"] == "FAIL" or attempt == max_retries:
                self.io.set_stage_state(
                    stage_key,
                    "failed",
                    completed_at=utcnow(),
                    score=review.get("score", 0.0),
                    attempt=attempt + 1,
                    feedback=review.get("feedback", ""),
                    output_path=str(output_path.relative_to(self.project_dir)),
                )
                self._halt(
                    f"{gate_key} FAILED after {attempt + 1} attempt(s).\n"
                    f"Last score: {review['score']:.2f}\n"
                    f"Failing dimensions: {json.dumps(review.get('dimension_scores', {}), indent=2)}\n"
                    f"Feedback: {review['feedback']}"
                )
                return False

            # REVISE: send targeted feedback back to the stage agent
            self.io.append_status(
                f"{gate_key} REVISE (attempt {attempt + 1}/{max_retries}): "
                f"{review['feedback']}\n"
            )
            self.io.set_stage_state(
                stage_key,
                "revising",
                attempt=attempt + 1,
                score=review.get("score", 0.0),
                feedback=review.get("feedback", ""),
                output_path=str(output_path.relative_to(self.project_dir)),
            )
            try:
                output_path = agent.revise(
                    feedback=review["feedback"],
                    output_path=output_path,
                    spec=self.spec,
                    dry_run=self.dry_run,
                )
            except Exception as exc:
                self.io.set_stage_state(stage_key, "failed", completed_at=utcnow(), error=str(exc))
                self._halt(f"{stage_name} revision raised an unhandled exception: {exc}")
                return False

        return False  # unreachable, but satisfies type checker

    # ------------------------------------------------------------------
    # Plan generation
    # ------------------------------------------------------------------

    def _generate_plan(self, feedback: str = "") -> str:
        """Call the planner LLM to generate plan.md content."""
        from agents.planner import PlannerAgent
        planner = PlannerAgent(self.project_dir)
        return planner.generate(spec=self.spec, feedback=feedback, dry_run=self.dry_run)

    # ------------------------------------------------------------------
    # Resume logic
    # ------------------------------------------------------------------

    def _resume_from_state(self) -> bool:
        """Resume from structured machine state in status.json."""
        state = self.io.read_state()
        if not state:
            self.io.append_status("No status.json found; restarting from Gate 0.\n")
            return self._run_gate_zero() and self._run_remaining_stages(0)

        if state.get("pipeline_status") == "completed":
            self.io.append_status("Pipeline already marked completed in status.json.\n")
            return True

        stages = state.get("stages", {})
        if stages.get("plan", {}).get("status") != "passed":
            self.io.append_status("Plan stage not passed in status.json; resuming from Gate 0.\n")
            return self._run_gate_zero() and self._run_remaining_stages(0)

        stage_keys = [s[0] for s in self.STAGES]
        next_index = 0
        for i, key in enumerate(stage_keys):
            if stages.get(key, {}).get("status") == "passed":
                next_index = i + 1
            else:
                break

        if next_index >= len(self.STAGES):
            self._log_success()
            return True

        self.io.append_status(
            f"Resuming from status.json at stage {next_index + 1}/{len(self.STAGES)}: {stage_keys[next_index]}.\n"
        )
        return self._run_remaining_stages(next_index)

    def _run_remaining_stages(self, start_index: int) -> bool:
        for stage_key, stage_name, gate_key in self.STAGES[start_index:]:
            if not self._run_stage(stage_key, stage_name, gate_key):
                return False
        self._log_success()
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _persist_gate_review(self, gate_number: int, review: dict, attempt: int = 0) -> None:
        suffix = f"-attempt-{attempt}" if attempt > 0 else ""
        review_path = (
            self.project_dir / "qa-reviews" / f"gate-{gate_number}-review{suffix}.md"
        )
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(self._format_review(gate_number, review), encoding="utf-8")

    def _format_review(self, gate_number: int, review: dict) -> str:
        lines = [
            f"# Gate {gate_number} QA Review",
            f"**Timestamp:** {utcnow()}",
            f"**Verdict:** {review['verdict']}",
            f"**Composite Score:** {review.get('score', 0.0):.2f}",
            "",
            "## Dimension Scores",
        ]
        for dim, score in review.get("dimension_scores", {}).items():
            lines.append(f"- {dim}: {score:.2f}")
        lines += [
            "",
            "## Feedback",
            review.get("feedback", ""),
        ]
        return "\n".join(lines)

    def _log_run_start(self) -> None:
        started_at = utcnow()
        self.io.initialize_status(
            f"# Content Factory Run Log\n\n"
            f"**Started:** {started_at}\n"
            f"**Project:** {self.project_dir}\n"
            f"**Dry Run:** {self.dry_run}\n\n"
        )
        self.io.initialize_state({
            "started_at": started_at,
            "project": str(self.project_dir),
            "dry_run": self.dry_run,
            "pipeline_status": "running",
            "stages": {},
        })

    def _log_success(self) -> None:
        finished_at = utcnow()
        self.io.append_status(
            f"\n## PIPELINE COMPLETE\n"
            f"**Finished:** {finished_at}\n"
            f"**Status:** ALL GATES PASSED\n"
            f"**Output:** {self.project_dir / 'output'}\n"
        )
        self.io.update_state(pipeline_status="completed", finished_at=finished_at)
        print(f"\n✓ Content Factory pipeline complete. Output in: {self.project_dir / 'output'}")

    def _halt(self, reason: str) -> None:
        halted_at = utcnow()
        self.io.append_status(
            f"\n## PIPELINE HALTED\n"
            f"**Timestamp:** {halted_at}\n"
            f"**Reason:**\n\n{reason}\n"
        )
        self.io.update_state(pipeline_status="halted", halted_at=halted_at, halt_reason=reason)
        print(f"\n✗ Pipeline halted. See status.md for details.\n\nReason: {reason}")


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Content Factory — fully autonomous digital product pipeline"
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="Path to the project directory (must contain spec.md). Default: current directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate spec and plan without making any LLM calls or writing output files.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a previously halted run from the last completed stage.",
    )
    parser.add_argument(
        "--brief",
        default="",
        help="Short product brief used to generate spec.md before running the pipeline.",
    )
    parser.add_argument(
        "--brief-file",
        default="",
        help="Path to a markdown/text file containing the product brief.",
    )
    parser.add_argument(
        "--regenerate-spec",
        action="store_true",
        help="Regenerate spec.md from the provided brief even if spec.md already exists.",
    )

    args = parser.parse_args()
    project_dir = Path(args.project_dir).resolve()

    if not project_dir.is_dir():
        print(f"Error: '{project_dir}' is not a directory.")
        sys.exit(1)

    brief_text = args.brief
    if args.brief_file:
        brief_path = Path(args.brief_file).expanduser().resolve()
        if not brief_path.exists():
            print(f"Error: brief file '{brief_path}' does not exist.")
            sys.exit(1)
        brief_text = brief_path.read_text(encoding="utf-8")

    if args.regenerate_spec and not brief_text.strip():
        print("Error: --regenerate-spec requires --brief or --brief-file.")
        sys.exit(1)

    orchestrator = Orchestrator(
        project_dir=project_dir,
        dry_run=args.dry_run,
        resume=args.resume,
        brief=brief_text,
        regenerate_spec=args.regenerate_spec,
    )
    success = orchestrator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
