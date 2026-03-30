"""Stage 3: Content Generation agent.

Writes the full draft section by section following the locked outline.
Produces draft/draft.md.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import BaseAgent

SYSTEM_PROMPT = """You are the Writer for the Content Factory pipeline.

You are writing a section of a digital knowledge product. Your inputs are:
1. The product spec (tone, voice, audience, constraints)
2. The locked outline (structure you must follow exactly)
3. The research brief (sources, data, examples to incorporate)
4. The section assignment (which section to write now)

Rules:
- Write ONLY the assigned section. Do not write other sections.
- Hit the word count target within ±10%. Do not pad or truncate.
- Use the exact tone, voice, and reading level specified in the spec.
- Incorporate the data points, examples, and citations assigned to this section
  in the outline. Do not fabricate data not in the research brief.
- No placeholder text. Every sentence must be real, specific content.
- Cite every statistic and claim with inline citation: [Source Name](URL).
- Write for the deliverable format (print PDF), not for a chat window.
- End each section with a transition sentence to the next section (except the last).
"""

REVISE_SYSTEM_PROMPT = """You are the Writer for the Content Factory pipeline.

Your draft was reviewed and returned with specific feedback.
Fix exactly the issues identified. Do not rewrite sections that were not flagged.
Preserve all passing content exactly as written.
"""


class ContentAgent(BaseAgent):
    name = "ContentAgent"
    default_model = "claude-sonnet-4-6"

    OUTPUT_PATH = "draft/draft.md"
    SECTION_DIR = "draft/sections"

    def run(self, spec: dict, dry_run: bool = False) -> Path:
        out = self.project_dir / self.OUTPUT_PATH
        if dry_run:
            self.write_file(out, self._stub(spec))
            return out

        spec_text = self.read_spec()
        outline_path = self.project_dir / "outline/outline.md"
        research_path = self.project_dir / "research/research-brief.md"

        outline_text = self.read_file(outline_path) if outline_path.exists() else ""
        research_text = self.read_file(research_path) if research_path.exists() else ""

        sections = self._parse_sections(outline_text)
        section_paths: list[Path] = []
        section_dir = self.project_dir / self.SECTION_DIR
        section_dir.mkdir(parents=True, exist_ok=True)

        for i, section in enumerate(sections):
            section_content = self.call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_message=(
                    f"Spec:\n\n{spec_text}\n\n"
                    f"Full Outline:\n\n{outline_text}\n\n"
                    f"Research Brief:\n\n{research_text}\n\n"
                    f"Write section {i + 1} of {len(sections)}: {section['title']}\n"
                    f"Target word count: {section.get('word_count', 2000)} words\n"
                    f"Section details from outline:\n{section['content']}"
                ),
                max_tokens=4096,
            )
            section_path = section_dir / f"{i + 1:02d}-{self._slugify(section['title'])}.md"
            self.write_file(section_path, section_content.strip() + "\n")
            section_paths.append(section_path)

        full_draft = self._assemble_sections(section_paths)
        self.write_file(out, full_draft)
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
        outline_text = self.read_file(self.project_dir / "outline/outline.md")

        content = self.call_llm(
            system_prompt=REVISE_SYSTEM_PROMPT,
            user_message=(
                f"Spec:\n\n{spec_text}\n\n"
                f"Outline:\n\n{outline_text}\n\n"
                f"Reviewer feedback:\n{feedback}\n\n"
                f"Current draft:\n\n{current}"
            ),
            max_tokens=16384,
        )
        self.write_file(output_path, content)
        return output_path

    def _parse_sections(self, outline_text: str) -> list[dict]:
        """Extract section metadata from the outline."""
        sections = []
        current = None
        word_count_pattern = re.compile(r"\*\*Word Count Allocation:\*\*\s*(\d[\d,]*)")

        for line in outline_text.split("\n"):
            if line.startswith("### "):
                if current:
                    sections.append(current)
                title = line.lstrip("#").strip()
                current = {"title": title, "content": "", "word_count": 2000}
            elif current is not None:
                current["content"] += line + "\n"
                m = word_count_pattern.search(line)
                if m:
                    current["word_count"] = int(m.group(1).replace(",", ""))

        if current:
            sections.append(current)

        return sections

    def _assemble_sections(self, section_paths: list[Path]) -> str:
        """Assemble the draft deterministically from section files."""
        assembled: list[str] = []
        for path in section_paths:
            text = self.read_file(path).strip()
            if text:
                assembled.append(text)
        return "\n\n".join(assembled).strip() + "\n"

    def _slugify(self, text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        return slug or "section"

    def _stub(self, spec: dict) -> str:
        product_type = spec.get("product_type", "ebook")
        topic = spec.get("topic_angle", "the specified topic")
        return f"""# Draft (dry-run stub)

## Introduction

This {product_type} covers {topic}. [Content would be generated here based on
the locked outline and research brief.]

## Chapter 1

[Section content would appear here, written to the exact word count specified
in the outline, incorporating data from the research brief.]

## Chapter 2

[Section content continues here.]

## Chapter 3

[Section content continues here.]

## Conclusion

[Conclusion and next steps would appear here.]
"""
