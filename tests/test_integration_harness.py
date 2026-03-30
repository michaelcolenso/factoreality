import json
import os
import tempfile
import unittest
from pathlib import Path

from orchestrator import Orchestrator
from agents.qa_reviewer import QAReviewerAgent


class FakeProviderIntegrationTests(unittest.TestCase):
    def test_full_pipeline_completes_with_fake_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "spec.md").write_text(
                """## Product Type
resource-guide

## Topic & Angle
A practical workflow for testing the content factory

## Target Audience
- Who: solo operators
- Needs: a reliable way to validate and ship digital products

## Tone & Voice
- Style: direct
- Reading level: grade 8

## Competitive Landscape
- Existing products: generic AI writing workflows
- Differentiation: gated, file-based execution

## Hard Constraints
- Length: 1200-1600 words
- Sections: 3-3
- Formats: markdown

## Deliverables
1. Main markdown guide

## Quality Thresholds
- Minimum gate confidence: 0.85
- Max retry cycles per gate: 2
- Readability target: Grade 8

## Done When
- [ ] Main guide exists as a final file
- [ ] No placeholder text anywhere
- [ ] All automated QA gates passed at or above confidence threshold
""",
                encoding="utf-8",
            )

            old_provider = os.environ.get("CONTENT_FACTORY_PROVIDER")
            try:
                os.environ["CONTENT_FACTORY_PROVIDER"] = "fake"
                orchestrator = Orchestrator(project_dir=project_dir)
                ok = orchestrator.run()
            finally:
                if old_provider is None:
                    os.environ.pop("CONTENT_FACTORY_PROVIDER", None)
                else:
                    os.environ["CONTENT_FACTORY_PROVIDER"] = old_provider

            self.assertTrue(ok)
            state = json.loads((project_dir / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(state["pipeline_status"], "completed")
            self.assertEqual(state["stages"]["plan"]["status"], "passed")
            self.assertEqual(state["stages"]["research"]["status"], "passed")
            self.assertTrue((project_dir / "research" / "research-brief.md").exists())
            self.assertTrue((project_dir / "outline" / "outline.md").exists())
            self.assertTrue((project_dir / "draft" / "draft.md").exists())
            self.assertTrue((project_dir / "draft" / "draft-edited.md").exists())
            self.assertTrue((project_dir / "output" / "formatted.md").exists())
            self.assertTrue((project_dir / "output" / "README.md").exists())
            self.assertTrue((project_dir / "output" / "manifest.json").exists())

    def test_qa_reviewer_can_summarize_directory_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            output_dir = project_dir / "output"
            output_dir.mkdir()
            (output_dir / "formatted.md").write_text("---\ntitle: x\n---\n", encoding="utf-8")
            reviewer = QAReviewerAgent(project_dir)
            summary = reviewer._read_stage_output(output_dir)
            self.assertIn("Directory listing for output", summary)
            self.assertIn("formatted.md", summary)


if __name__ == "__main__":
    unittest.main()
