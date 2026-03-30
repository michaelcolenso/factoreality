"""Stage 4: Editorial & QA agent.

Performs grammar, consistency, fact-checking, readability, and flow passes.
Produces draft/draft-edited.md and editorial/editorial-notes.md.
"""

from __future__ import annotations

from pathlib import Path

from .base import BaseAgent

DRAFT_START = "<<<EDITED_DRAFT_START>>>"
DRAFT_END = "<<<EDITED_DRAFT_END>>>"
NOTES_START = "<<<EDITORIAL_NOTES_START>>>"
NOTES_END = "<<<EDITORIAL_NOTES_END>>>"

SYSTEM_PROMPT = f"""You are the Editor for the Content Factory pipeline.

You are performing a full editorial pass on a draft digital knowledge product.
Your inputs are the product spec and the first draft.

Perform these passes in order:

### Pass 1 — Copyedit
Fix all spelling, grammar, and punctuation errors. Flag any that require
substantive rewriting rather than a simple correction.

### Pass 2 — Consistency Audit
- Ensure the same term is used for the same concept throughout.
- Ensure capitalization of proper nouns, product names, and headings is consistent.
- Ensure list formatting (bullets vs. numbers, punctuation at list item ends) is consistent.
- Note all terminology decisions in editorial-notes.md.

### Pass 3 — Fact-Check
- Flag every statistic and external claim with a citation check marker: [VERIFY: ...]
- For any claim that cannot be traced to a source in the research brief,
  rewrite to remove the unverifiable claim rather than leave it in.
- Record all removed claims in editorial-notes.md with the original text.

### Pass 4 — Readability
- Score each section for Flesch-Kincaid grade level (estimate if no tool available).
- Rewrite any sentence scoring above the target grade level.
- Break up sentences longer than 25 words where possible without losing meaning.

### Pass 5 — Flow
- Add or improve transition sentences between sections.
- Check that each section opening delivers on the promise of the previous transition.
- Smooth any abrupt register shifts (sudden changes from formal to informal).

Rules:
- Do not change the structure (section order or headings) — that was locked at Gate 2.
- Do not add content not already in the draft.
- Do not change the voice or tone unless it deviates from the spec.
- Scope changes to the minimum needed to pass editorial QA.

Return your response using these exact sentinels and nothing else outside them:
{DRAFT_START}
[full edited draft markdown]
{DRAFT_END}
{NOTES_START}
[notes and flags]
{NOTES_END}
"""

REVISE_SYSTEM_PROMPT = f"""You are the Editor for the Content Factory pipeline.

Your edited draft was reviewed and returned with specific feedback.
Apply only the changes needed to address the reviewer's feedback.
Do not re-edit sections that passed review.

Return your response using these exact sentinels and nothing else outside them:
{DRAFT_START}
[revised draft]
{DRAFT_END}
{NOTES_START}
[updated notes]
{NOTES_END}
"""


class EditorialAgent(BaseAgent):
    name = "EditorialAgent"
    default_model = "claude-opus-4-6"

    DRAFT_OUT = "draft/draft-edited.md"
    NOTES_OUT = "editorial/editorial-notes.md"

    def run(self, spec: dict, dry_run: bool = False) -> Path:
        draft_out = self.project_dir / self.DRAFT_OUT
        notes_out = self.project_dir / self.NOTES_OUT

        if dry_run:
            self.write_file(draft_out, "(dry-run: edited draft would appear here)")
            self.write_file(notes_out, "# Editorial Notes (dry-run stub)\n\nNo issues found.")
            return draft_out

        spec_text = self.read_spec()
        draft_path = self.project_dir / "draft/draft.md"
        draft_text = self.read_file(draft_path) if draft_path.exists() else ""

        result = self.call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_message=(
                f"Spec:\n\n{spec_text}\n\n"
                f"Draft:\n\n{draft_text}\n"
            ),
            max_tokens=16384,
        )

        edited_draft, editorial_notes = self._split_result(result)
        self.write_file(draft_out, edited_draft)
        self.write_file(notes_out, editorial_notes)
        return draft_out

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
                f"Current edited draft:\n\n{current}\n"
            ),
            max_tokens=16384,
        )

        edited_draft, editorial_notes = self._split_result(result)
        self.write_file(output_path, edited_draft)
        notes_out = self.project_dir / self.NOTES_OUT
        self.write_file(notes_out, editorial_notes)
        return output_path

    def _split_result(self, result: str) -> tuple[str, str]:
        """Split LLM response into (edited_draft, editorial_notes)."""
        if all(marker in result for marker in (DRAFT_START, DRAFT_END, NOTES_START, NOTES_END)):
            draft = result.split(DRAFT_START, 1)[1].split(DRAFT_END, 1)[0].strip()
            notes = result.split(NOTES_START, 1)[1].split(NOTES_END, 1)[0].strip()
            return draft, notes or "# Editorial Notes\n\nNo issues flagged."

        # Legacy fallback for older outputs
        marker = "# EDITORIAL NOTES"
        if marker in result:
            parts = result.split(marker, 1)
            draft = parts[0].replace("# EDITED DRAFT", "").strip()
            notes = (marker + parts[1]).strip()
            return draft, notes

        return result.replace("# EDITED DRAFT", "").strip(), "# Editorial Notes\n\nNo issues flagged."
