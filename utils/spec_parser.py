"""Parse spec.md into a structured dict for use by all pipeline agents."""

from __future__ import annotations

import json
import re
from pathlib import Path


class SpecParser:
    """
    Parses the human-authored spec.md into a structured dict.

    Sprint C tightens validation around the fields that materially affect pipeline
    quality: product_type, topic_angle, hard constraints, deliverables, target audience,
    tone/voice, and quality thresholds.
    """

    REQUIRED_FIELDS = {"product_type", "topic_angle"}
    STRONGLY_RECOMMENDED_FIELDS = {"target_audience", "tone_and_voice", "deliverables"}

    def __init__(self, spec_path: Path) -> None:
        self.spec_path = spec_path
        self.profiles = self._load_product_profiles()

    def parse(self) -> dict:
        if not self.spec_path.exists():
            raise FileNotFoundError(f"spec.md not found at {self.spec_path}")

        text = self.spec_path.read_text(encoding="utf-8")
        spec = self._extract(text)

        missing = self.REQUIRED_FIELDS - set(spec.keys())
        if missing:
            raise ValueError(
                f"spec.md is missing required fields: {missing}. "
                f"See templates/spec_template.md."
            )

        self._validate_product_type(spec)
        self._validate_strong_fields(spec)
        self._validate_constraints(spec)
        self._apply_profile_defaults(spec)
        self._validate_quality_thresholds(spec)

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

        return {k: v for k, v in spec.items() if v is not None and v != "" and v != {} and v != []}

    def _extract_field(self, text: str, heading: str) -> str | None:
        pattern = re.compile(
            rf"^##\s+{re.escape(heading)}\s*\n(.+?)(?=^##|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(text)
        if not m:
            return None
        value = m.group(1).strip()
        if value.startswith("[") and value.endswith("]"):
            return None
        for line in value.split("\n"):
            line = line.strip()
            if line and not line.startswith("["):
                return line
        return None

    def _extract_section(self, text: str, heading: str) -> str | None:
        pattern = re.compile(
            rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(text)
        if not m:
            return None
        return m.group(1).strip() or None

    def _extract_list(self, text: str, heading: str) -> list[str]:
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

        wc_m = re.search(r"Length.*?(\d[\d,]*)\s*[\-–to]+\s*(\d[\d,]*)\s*word", section, re.IGNORECASE)
        if wc_m:
            constraints["min_words"] = int(wc_m.group(1).replace(",", ""))
            constraints["max_words"] = int(wc_m.group(2).replace(",", ""))

        sec_m = re.search(r"Sections.*?(\d+)\s*[\-–/to]+\s*(\d+)", section, re.IGNORECASE)
        if sec_m:
            constraints["min_sections"] = int(sec_m.group(1))
            constraints["max_sections"] = int(sec_m.group(2))

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

        retry_m = re.search(r"Max retry cycles(?: per gate)?[:\s]+(\d+)", section, re.IGNORECASE)
        if retry_m:
            thresholds["max_retry_cycles"] = int(retry_m.group(1))

        readability_m = re.search(r"Readability target[:\s]+(.+?)$", section, re.MULTILINE | re.IGNORECASE)
        if readability_m:
            thresholds["readability_target"] = readability_m.group(1).strip()

        return thresholds

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _load_product_profiles(self) -> dict:
        candidates = [
            self.spec_path.parent / "templates" / "product_profiles.json",
            Path(__file__).resolve().parents[1] / "templates" / "product_profiles.json",
        ]
        for profiles_path in candidates:
            if profiles_path.exists():
                return json.loads(profiles_path.read_text(encoding="utf-8"))
        return {}

    def _validate_product_type(self, spec: dict) -> None:
        product_type = spec["product_type"]
        if product_type not in self.profiles:
            raise ValueError(
                f"Unknown product_type '{product_type}'. Expected one of: {', '.join(sorted(self.profiles))}."
            )

    def _validate_strong_fields(self, spec: dict) -> None:
        missing = [field for field in self.STRONGLY_RECOMMENDED_FIELDS if field not in spec]
        if missing:
            raise ValueError(
                f"spec.md is missing required production fields: {missing}. "
                f"Provide audience, tone/voice, and at least one deliverable."
            )

    def _validate_constraints(self, spec: dict) -> None:
        constraints = spec.get("hard_constraints", {})
        if "min_words" in constraints and "max_words" in constraints:
            if constraints["min_words"] > constraints["max_words"]:
                raise ValueError("Hard Constraints invalid: min_words cannot exceed max_words.")
        if "min_sections" in constraints and "max_sections" in constraints:
            if constraints["min_sections"] > constraints["max_sections"]:
                raise ValueError("Hard Constraints invalid: min_sections cannot exceed max_sections.")

    def _apply_profile_defaults(self, spec: dict) -> None:
        profile = self.profiles.get(spec["product_type"], {})
        thresholds = spec.setdefault("quality_thresholds", {})
        thresholds.setdefault("min_gate_confidence", profile.get("quality_threshold", 0.8))
        thresholds.setdefault("max_retry_cycles", 3)

        constraints = spec.setdefault("hard_constraints", {})
        typical_words = profile.get("typical_word_count")
        if typical_words and "min_words" not in constraints and "max_words" not in constraints:
            constraints["min_words"], constraints["max_words"] = typical_words
        profile_deliverables = profile.get("deliverables")
        if not spec.get("deliverables") and profile_deliverables:
            spec["deliverables"] = profile_deliverables

    def _validate_quality_thresholds(self, spec: dict) -> None:
        thresholds = spec.get("quality_thresholds", {})
        confidence = thresholds.get("min_gate_confidence", 0.8)
        if not (0.0 < confidence <= 1.0):
            raise ValueError("Minimum gate confidence must be between 0.0 and 1.0.")
        retries = thresholds.get("max_retry_cycles", 3)
        if retries < 0:
            raise ValueError("Max retry cycles per gate cannot be negative.")
