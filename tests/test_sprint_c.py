import os
import tempfile
import unittest
from pathlib import Path

from agents.base import BaseAgent
from utils.model_router import ModelRouter
from utils.spec_parser import SpecParser


class DummyAgent(BaseAgent):
    name = "ResearchAgent"
    default_model = "claude-sonnet-4-6"

    def run(self, spec: dict, dry_run: bool = False) -> Path:
        raise NotImplementedError

    def revise(self, feedback: str, output_path: Path, spec: dict, dry_run: bool = False) -> Path:
        raise NotImplementedError


class ModelRouterTests(unittest.TestCase):
    def test_agent_specific_model_override_wins(self) -> None:
        old_general = os.environ.get("CONTENT_FACTORY_MODEL")
        old_specific = os.environ.get("CONTENT_FACTORY_MODEL_RESEARCHAGENT")
        try:
            os.environ["CONTENT_FACTORY_MODEL"] = "claude-opus-4-6"
            os.environ["CONTENT_FACTORY_MODEL_RESEARCHAGENT"] = "gpt-5"
            config = ModelRouter.resolve("ResearchAgent", "claude-sonnet-4-6")
            self.assertEqual(config.model, "gpt-5")
            self.assertEqual(config.provider, "openai")
        finally:
            if old_general is None:
                os.environ.pop("CONTENT_FACTORY_MODEL", None)
            else:
                os.environ["CONTENT_FACTORY_MODEL"] = old_general
            if old_specific is None:
                os.environ.pop("CONTENT_FACTORY_MODEL_RESEARCHAGENT", None)
            else:
                os.environ["CONTENT_FACTORY_MODEL_RESEARCHAGENT"] = old_specific

    def test_base_agent_uses_router(self) -> None:
        old_model = os.environ.get("CONTENT_FACTORY_MODEL_RESEARCHAGENT")
        try:
            os.environ["CONTENT_FACTORY_MODEL_RESEARCHAGENT"] = "claude-opus-4-6"
            agent = DummyAgent(Path("."))
            self.assertEqual(agent.model, "claude-opus-4-6")
            self.assertEqual(agent.provider, "anthropic")
        finally:
            if old_model is None:
                os.environ.pop("CONTENT_FACTORY_MODEL_RESEARCHAGENT", None)
            else:
                os.environ["CONTENT_FACTORY_MODEL_RESEARCHAGENT"] = old_model


class SpecParserValidationTests(unittest.TestCase):
    def _write_spec(self, tmp: str, extra: str = "") -> Path:
        spec_path = Path(tmp) / "spec.md"
        spec_path.write_text(
            f"""## Product Type
ebook

## Topic & Angle
Test angle

## Target Audience
- Who: founder
- Needs: clarity

## Tone & Voice
- Style: authoritative
- Reading level: grade 8

## Hard Constraints
- Length: 8,000-10,000 words
- Sections: 5-7
- Formats: PDF, DOCX

## Deliverables
1. 45-page PDF ebook
2. Resource links document

## Quality Thresholds
- Minimum gate confidence: 0.85
- Max retry cycles per gate: 3
{extra}
""",
            encoding="utf-8",
        )
        return spec_path

    def test_unknown_product_type_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.md"
            spec_path.write_text(
                """## Product Type
weird-thing

## Topic & Angle
Test angle

## Target Audience
People

## Tone & Voice
Clear

## Deliverables
1. thing
""",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                SpecParser(spec_path).parse()

    def test_invalid_constraint_ranges_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = self._write_spec(tmp)
            spec_path.write_text(
                spec_path.read_text(encoding="utf-8").replace("8,000-10,000", "10,000-8,000"),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                SpecParser(spec_path).parse()

    def test_profile_defaults_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.md"
            spec_path.write_text(
                """## Product Type
report

## Topic & Angle
Test angle

## Target Audience
Analysts

## Tone & Voice
Authoritative

## Deliverables
1. PDF report
""",
                encoding="utf-8",
            )
            parser = SpecParser(spec_path)
            parser.profiles = {
                "report": {
                    "quality_threshold": 0.9,
                    "typical_word_count": [5000, 20000],
                }
            }
            parsed = parser.parse()
            self.assertEqual(parsed["quality_thresholds"]["min_gate_confidence"], 0.9)
            self.assertEqual(parsed["hard_constraints"]["min_words"], 5000)
            self.assertEqual(parsed["hard_constraints"]["max_words"], 20000)


if __name__ == "__main__":
    unittest.main()
