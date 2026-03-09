import tempfile
import unittest
from pathlib import Path

from orchestrator import Orchestrator
from utils.spec_parser import SpecParser


class SpecParserQualityThresholdTests(unittest.TestCase):
    def test_accepts_max_retry_cycles_per_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.md"
            spec_path.write_text(
                """## Product Type
ebook

## Topic & Angle
Test angle

## Quality Thresholds
- Minimum gate confidence: 0.85
- Max retry cycles per gate: 5
""",
                encoding="utf-8",
            )
            parsed = SpecParser(spec_path).parse()
            self.assertEqual(parsed["quality_thresholds"]["max_retry_cycles"], 5)


class EnsureSpecExistsTests(unittest.TestCase):
    def test_regenerate_without_brief_halts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "spec.md").write_text("## Product Type\nebook\n\n## Topic & Angle\nA\n", encoding="utf-8")

            orchestrator = Orchestrator(project_dir=project_dir, regenerate_spec=True)
            ok = orchestrator._ensure_spec_exists()

            self.assertFalse(ok)
            status_text = (project_dir / "status.md").read_text(encoding="utf-8")
            self.assertIn("--regenerate-spec requires --brief or --brief-file", status_text)


class QAReviewerDryRunTests(unittest.TestCase):
    def test_review_gate_returns_pass_without_llm_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "spec.md").write_text(
                "## Product Type\nebook\n\n## Topic & Angle\nTest\n",
                encoding="utf-8",
            )
            stage_output = project_dir / "plan.md"
            stage_output.write_text("# Plan\n", encoding="utf-8")

            from agents.qa_reviewer import QAReviewerAgent

            reviewer = QAReviewerAgent(project_dir)
            result = reviewer.review_gate(
                gate_number=0,
                spec={"quality_thresholds": {"min_gate_confidence": 0.8}},
                stage_output_path=stage_output,
                rubric_key="plan",
                dry_run=True,
            )

            self.assertEqual(result["verdict"], "PASS")
            self.assertEqual(result["score"], 1.0)
            self.assertFalse(result["failing_dimensions"])


if __name__ == "__main__":
    unittest.main()
