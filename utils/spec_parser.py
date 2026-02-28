"""Parse spec.md into a structured dict for use by all pipeline agents."""

from __future__ import annotations

import re
from pathlib import Path


class SpecParser:
    """
    Parses the human-authored spec.md into a structured dict.

    The parser is intentionally lenient — a missing optional field returns
    a sensible default rather than raising. Only truly required fields
    (product_type, topic_angle) raise ValueError if absent.
    """

    REQUIRED_FIELDS = {"product_type", "topic_angle"}

    def __init__(self, spec_path: Path) -> None:
        self.spec_path = spec_path

    def parse(self) -> dict:
        if not self.spec_path.exists():
            raise FileNotFoundError(f"spec.md not found at {self.spec_path}")

        text = self.spec_path.read_text(encoding="utf-8")
        spec = self._extract(text)

        # Validate required fields
        missing = self.REQUIRED_FIELDS - set(spec.keys())
        if missing:
            raise ValueError(
                f"spec.md is missing required fields: {missing}. "
                f"See templates/spec_template.md."
            )

        return spec

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    def _extract(self, text: str) -> dict:
        spec: dict = {}

        spec["product_type"] = self._extract_field(text, "Product Type")
        spec["topic_angle"] = self._extract_field(text, "Topic & Angle") or self._extract_field(text, "Topic and Angle")
        spec["target_audience"] = self._extract_section(text, "Target Audience")
        spec["tone_and_voice"] = self._extract_section(text, "Tone & Voice") or self._extract_section(text, "Tone and Voice")
        spec["competitive_landscape"] = self._extract_section(text, "Competitive Landscape")
        spec["hard_constraints"] = self._parse_hard_constraints(text)
        spec["deliverables"] = self._extract_list(text, "Deliverables")
        spec["quality_thresholds"] = self._parse_quality_thresholds(text)
        spec["done_when"] = self._extract_checklist(text, "Done When")
        spec["raw"] = text

        # Remove None values for cleaner dicts
        return {k: v for k, v in spec.items() if v is not None and v != "" and v != {} and v != []}

    def _extract_field(self, text: str, heading: str) -> str | None:
        """Extract single-line value under a ## heading."""
        pattern = re.compile(
            rf"^##\s+{re.escape(heading)}\s*\n(.+?)(?=^##|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(text)
        if not m:
            return None
        value = m.group(1).strip()
        # Strip placeholder brackets
        if value.startswith("[") and value.endswith("]"):
            return None
        # Take the first non-empty, non-comment line
        for line in value.split("\n"):
            line = line.strip()
            if line and not line.startswith("["):
                return line
        return None

    def _extract_section(self, text: str, heading: str) -> str | None:
        """Extract multi-line section content under a ## heading."""
        pattern = re.compile(
            rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(text)
        if not m:
            return None
        return m.group(1).strip() or None

    def _extract_list(self, text: str, heading: str) -> list[str]:
        """Extract numbered or bulleted list items under a ## heading."""
        section = self._extract_section(text, heading) or ""
        items = []
        for line in section.split("\n"):
            line = line.strip()
            m = re.match(r"^[\d\.\-\*]\s*(.+)$", line)
            if m:
                item = m.group(1).strip()
                if not item.startswith("["):
                    items.append(item)
        return items

    def _extract_checklist(self, text: str, heading: str) -> list[str]:
        """Extract checkbox items under a ## heading."""
        section = self._extract_section(text, heading) or ""
        items = []
        for line in section.split("\n"):
            m = re.match(r"^\s*-\s*\[[ x]\]\s*(.+)$", line)
            if m:
                items.append(m.group(1).strip())
        return items

    def _parse_hard_constraints(self, text: str) -> dict:
        section = self._extract_section(text, "Hard Constraints") or ""
        constraints: dict = {}

        # Word count
        wc_m = re.search(r"Length.*?(\d[\d,]*)\s*[\-–to]+\s*(\d[\d,]*)\s*word", section, re.IGNORECASE)
        if wc_m:
            constraints["min_words"] = int(wc_m.group(1).replace(",", ""))
            constraints["max_words"] = int(wc_m.group(2).replace(",", ""))

        # Section count
        sec_m = re.search(r"Sections.*?(\d+)\s*[\-–/to]+\s*(\d+)", section, re.IGNORECASE)
        if sec_m:
            constraints["min_sections"] = int(sec_m.group(1))
            constraints["max_sections"] = int(sec_m.group(2))

        # Formats
        fmt_m = re.search(r"Formats?[:\s]+(.+?)$", section, re.MULTILINE | re.IGNORECASE)
        if fmt_m:
            formats = [f.strip() for f in fmt_m.group(1).split(",") if f.strip()]
            if formats:
                constraints["formats"] = formats

        return constraints

    def _parse_quality_thresholds(self, text: str) -> dict:
        section = self._extract_section(text, "Quality Thresholds") or ""
        thresholds: dict = {}

        confidence_m = re.search(r"Minimum gate confidence[:\s]+([0-9.]+)", section, re.IGNORECASE)
        if confidence_m:
            thresholds["min_gate_confidence"] = float(confidence_m.group(1))
        else:
            thresholds["min_gate_confidence"] = 0.8

        retry_m = re.search(r"Max retry cycles(?: per gate)?[:\s]+(\d+)", section, re.IGNORECASE)
        if retry_m:
            thresholds["max_retry_cycles"] = int(retry_m.group(1))
        else:
            thresholds["max_retry_cycles"] = 3

        readability_m = re.search(r"Readability target[:\s]+(.+?)$", section, re.MULTILINE | re.IGNORECASE)
        if readability_m:
            thresholds["readability_target"] = readability_m.group(1).strip()

        return thresholds
