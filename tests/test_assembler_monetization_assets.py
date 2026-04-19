import tempfile
import unittest
from pathlib import Path

from agents.assembler import AssemblerAgent


class AssemblerMonetizationAssetTests(unittest.TestCase):
    def test_run_writes_revenue_artifacts_and_includes_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            output_dir = project_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            # Simulate formatted output from Stage 5
            (output_dir / "formatted.md").write_text("# Final Product\n", encoding="utf-8")

            agent = AssemblerAgent(project_dir)
            spec = {
                "product_type": "ebook",
                "topic_angle": "Launch a micro-course in 7 days",
                "target_audience": "indie creators",
                "deliverables": ["Main markdown guide"],
                "hard_constraints": {"formats": ["md"]},
            }

            result = agent.run(spec)
            self.assertEqual(result, output_dir)

            expected = [
                "channel-publish-manifest.json",
                "offer-stack.md",
                "conversion-feedback-loop.md",
                "growth-engine.md",
                "metrics-template.csv",
                "manifest.json",
                "README.md",
            ]
            for name in expected:
                self.assertTrue((output_dir / name).exists(), f"missing: {name}")

            manifest_text = (output_dir / "README.md").read_text(encoding="utf-8")
            self.assertIn("## Monetization Assets", manifest_text)
            self.assertIn("growth engine brief", manifest_text)


if __name__ == "__main__":
    unittest.main()
