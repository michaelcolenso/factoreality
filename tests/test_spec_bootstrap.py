import json
import tempfile
import unittest
from pathlib import Path

from orchestrator import Orchestrator
from agents.qa_reviewer import QAReviewerAgent
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


class QAReviewerParsingTests(unittest.TestCase):
    def test_invalid_json_fails_hard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reviewer = QAReviewerAgent(Path(tmp))
            rubric = [{"name": "Completeness", "critical": True}]
            result = reviewer._parse_response("not-json", 0.8, rubric)
            self.assertEqual(result["verdict"], "FAIL")
            self.assertIn("could not be parsed as JSON", result["feedback"])

    def test_pass_is_downgraded_when_critical_dimension_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reviewer = QAReviewerAgent(Path(tmp))
            rubric = [
                {"name": "Completeness", "critical": True},
                {"name": "Readability", "critical": False},
            ]
            payload = json.dumps({
                "verdict": "PASS",
                "score": 0.91,
                "dimension_scores": {"Completeness": 0.4, "Readability": 0.95},
                "feedback": "Fix completeness.",
                "passing_dimensions": ["Readability"],
                "failing_dimensions": ["Completeness"],
            })
            result = reviewer._parse_response(payload, 0.8, rubric)
            self.assertEqual(result["verdict"], "REVISE")


class StateFileTests(unittest.TestCase):
    def test_log_run_start_creates_status_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            orchestrator = Orchestrator(project_dir=Path(tmp), dry_run=True)
            orchestrator._log_run_start()
            state_path = Path(tmp) / "status.json"
            self.assertTrue(state_path.exists())
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["pipeline_status"], "running")
            self.assertEqual(state["stages"], {})

    def test_resume_uses_structured_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "spec.md").write_text(
                "## Product Type\nebook\n\n## Topic & Angle\nA\n",
                encoding="utf-8",
            )
            orchestrator = Orchestrator(project_dir=project_dir, dry_run=True, resume=True)
            orchestrator.io.initialize_state({
                "pipeline_status": "running",
                "stages": {
                    "plan": {"status": "passed"},
                    "research": {"status": "passed"},
                    "outline": {"status": "passed"},
                },
            })
            orchestrator.spec = {"quality_thresholds": {"max_retry_cycles": 1}}

            called = []

            def fake_run_remaining(start_index: int) -> bool:
                called.append(start_index)
                return True

            orchestrator._run_remaining_stages = fake_run_remaining  # type: ignore[method-assign]
            ok = orchestrator._resume_from_state()

            self.assertTrue(ok)
            self.assertEqual(called, [2])


if __name__ == "__main__":
    unittest.main()
