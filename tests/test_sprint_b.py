import tempfile
import unittest
from pathlib import Path

from agents.assembler import AssemblerAgent
from agents.content import ContentAgent
from agents.editorial import EditorialAgent


class ContentAssemblyTests(unittest.TestCase):
    def test_assemble_sections_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            agent = ContentAgent(project_dir)
            section_dir = project_dir / "draft" / "sections"
            section_dir.mkdir(parents=True)
            a = section_dir / "01-intro.md"
            b = section_dir / "02-body.md"
            a.write_text("# Intro\n\nAlpha\n", encoding="utf-8")
            b.write_text("# Body\n\nBeta\n", encoding="utf-8")

            assembled = agent._assemble_sections([a, b])
            self.assertEqual(assembled, "# Intro\n\nAlpha\n\n# Body\n\nBeta\n")


class EditorialSplitTests(unittest.TestCase):
    def test_split_result_prefers_explicit_sentinels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            agent = EditorialAgent(Path(tmp))
            raw = """
<<<EDITED_DRAFT_START>>>
# Draft
Clean text.
<<<EDITED_DRAFT_END>>>
<<<EDITORIAL_NOTES_START>>>
# Notes
One note.
<<<EDITORIAL_NOTES_END>>>
"""
            draft, notes = agent._split_result(raw)
            self.assertEqual(draft, "# Draft\nClean text.")
            self.assertEqual(notes, "# Notes\nOne note.")


class AssemblerSpecDrivenTests(unittest.TestCase):
    def test_collect_deliverables_prefers_spec_requested_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            output_dir = project_dir / "output"
            assets_dir = project_dir / "assets"
            output_dir.mkdir()
            assets_dir.mkdir()

            (output_dir / "formatted.pdf").write_text("pdf", encoding="utf-8")
            (output_dir / "notes.md").write_text("notes", encoding="utf-8")
            (assets_dir / "resource-links.pdf").write_text("links", encoding="utf-8")

            agent = AssemblerAgent(project_dir)
            spec = {
                "hard_constraints": {"formats": ["PDF", "MD"]},
                "deliverables": ["45-page PDF ebook", "Resource links document"],
            }

            deliverables = agent._collect_deliverables(spec)
            names = [p.name for p in deliverables]
            self.assertIn("formatted.pdf", names)
            self.assertIn("resource-links.pdf", names)


if __name__ == "__main__":
    unittest.main()
