"""Stage 5: Design & Formatting agent.

Applies document layout and exports to the target format(s) specified in spec.
Produces formatted files in the output/ directory.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .base import BaseAgent

SYSTEM_PROMPT = """You are the Formatter for the Content Factory pipeline.

Your task: convert an edited Markdown draft into a professionally formatted
document according to the product spec.

You will output a LaTeX or Pandoc-compatible Markdown document with full
formatting applied:
- Cover page
- Table of contents (auto-generated from headings)
- Consistent heading hierarchy (H1 = chapter, H2 = section, H3 = subsection)
- Consistent paragraph spacing and line length
- Headers and footers with product title and page numbers
- Any brand colors/fonts from the spec applied via LaTeX or CSS variables
- Callout boxes for key takeaways, warnings, or tips
- Numbered lists for sequential steps, bullets for non-sequential

If the spec calls for supplementary worksheets or checklists, output those as
separate Markdown files with a clear naming convention.

Output format:
- Primary deliverable: a single Markdown file with full formatting metadata
  in the front matter (YAML for Pandoc, or LaTeX preamble for direct LaTeX)
- One additional file per supplementary deliverable

Rules:
- Do not change any content — only apply formatting.
- If the spec has brand guidelines, apply them via the document preamble.
- Write the table of contents from the actual section headings — do not invent entries.
- Page count must fall within the spec's expected range.
"""

REVISE_SYSTEM_PROMPT = """You are the Formatter for the Content Factory pipeline.

Your formatted document was reviewed and returned with specific feedback.
Fix only the formatting issues identified. Do not touch the content.
"""


class FormatterAgent(BaseAgent):
    name = "FormatterAgent"
    default_model = "claude-sonnet-4-6"

    OUTPUT_PATH = "output/formatted.md"

    def run(self, spec: dict, dry_run: bool = False) -> Path:
        out = self.project_dir / self.OUTPUT_PATH
        if dry_run:
            self.write_file(out, self._stub_frontmatter(spec))
            return out

        spec_text = self.read_spec()
        draft_path = self.project_dir / "draft/draft-edited.md"
        draft_text = self.read_file(draft_path) if draft_path.exists() else ""

        result = self.call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_message=(
                f"Spec:\n\n{spec_text}\n\n"
                f"Edited draft to format:\n\n{draft_text}\n\n"
                "Return the fully formatted document with YAML front matter for Pandoc."
            ),
            max_tokens=16384,
        )

        self.write_file(out, result)

        # Attempt PDF export if pandoc is available
        self._try_export_pdf(out, spec)

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

        result = self.call_llm(
            system_prompt=REVISE_SYSTEM_PROMPT,
            user_message=(
                f"Spec:\n\n{spec_text}\n\n"
                f"Reviewer feedback:\n{feedback}\n\n"
                f"Current formatted document:\n\n{current}"
            ),
            max_tokens=16384,
        )
        self.write_file(output_path, result)
        self._try_export_pdf(output_path, spec)
        return output_path

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def _try_export_pdf(self, md_path: Path, spec: dict) -> Path | None:
        """Attempt to export to PDF using Pandoc. Returns PDF path or None."""
        try:
            pdf_path = md_path.with_suffix(".pdf")
            cmd = [
                "pandoc",
                str(md_path),
                "-o", str(pdf_path),
                "--pdf-engine=xelatex",
                "--toc",
                "--toc-depth=3",
                "--number-sections",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return pdf_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _stub_frontmatter(self, spec: dict) -> str:
        title = spec.get("topic_angle", "Digital Knowledge Product")
        product_type = spec.get("product_type", "ebook")
        return f"""---
title: "{title}"
author: "Content Factory"
date: "2026"
documentclass: article
geometry: "margin=1in"
fontsize: 11pt
toc: true
toc-depth: 3
numbersections: true
colorlinks: true
linkcolor: blue
---

# {title}

*(dry-run: formatted {product_type} content would appear here)*

This document was generated by the Content Factory pipeline.
"""
