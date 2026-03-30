"""Stage 6: Assembly & Export agent.

Collects all deliverables, normalizes filenames, creates a manifest/README,
and bundles everything into a delivery ZIP package.
"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

from .base import BaseAgent


class AssemblerAgent(BaseAgent):
    name = "AssemblerAgent"

    OUTPUT_PATH = "output"

    def run(self, spec: dict, dry_run: bool = False) -> Path:
        output_dir = self.project_dir / self.OUTPUT_PATH
        output_dir.mkdir(parents=True, exist_ok=True)

        if dry_run:
            readme = output_dir / "README.md"
            self.write_file(readme, self._stub_readme(spec))
            return output_dir

        deliverables = self._collect_deliverables(spec)
        manifest = self._build_manifest(deliverables, spec)

        readme_path = output_dir / "README.md"
        self.write_file(readme_path, manifest)

        # Create ZIP archive if there are multiple deliverables
        if len(deliverables) > 1:
            self._create_zip(output_dir, deliverables, spec)

        # Write a JSON manifest for programmatic consumption
        json_manifest = {
            "generated": datetime.utcnow().isoformat() + "Z",
            "product_type": spec.get("product_type", "unknown"),
            "topic": spec.get("topic_angle", "unknown"),
            "expected_deliverables": spec.get("deliverables", []),
            "files": [
                {
                    "filename": p.name,
                    "size_bytes": p.stat().st_size,
                    "path": str(p.relative_to(self.project_dir)),
                }
                for p in deliverables
                if p.exists()
            ],
        }
        manifest_json_path = output_dir / "manifest.json"
        manifest_json_path.write_text(json.dumps(json_manifest, indent=2), encoding="utf-8")

        return output_dir

    def revise(
        self,
        feedback: str,
        output_path: Path,
        spec: dict,
        dry_run: bool = False,
    ) -> Path:
        # Assembly revisions are scripted; re-run the assembly
        return self.run(spec, dry_run=dry_run)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _collect_deliverables(self, spec: dict) -> list[Path]:
        """Find all output files that should be included in the final package.

        Prioritize deliverables and formats explicitly requested by the spec.
        """
        output_dir = self.project_dir / "output"
        assets_dir = self.project_dir / "assets"
        deliverable_specs = self._normalize_deliverables(spec.get("deliverables", []))
        allowed_formats = self._allowed_extensions(spec)

        candidates = [
            p for p in output_dir.iterdir()
            if p.is_file() and p.stat().st_size > 0 and p.name not in {"README.md", "manifest.json"}
        ] if output_dir.exists() else []
        asset_candidates = [
            p for p in assets_dir.rglob("*") if p.is_file() and p.stat().st_size > 0
        ] if assets_dir.exists() else []

        selected: list[Path] = []
        used: set[Path] = set()

        for deliverable in deliverable_specs:
            match = self._match_deliverable(deliverable, candidates, asset_candidates, allowed_formats)
            if match and match not in used:
                selected.append(match)
                used.add(match)

        if not selected:
            for p in candidates:
                if p.suffix.lower() in allowed_formats and p not in used:
                    selected.append(p)
                    used.add(p)

        # Include relevant supporting assets only if the spec suggests them.
        for deliverable in deliverable_specs:
            if deliverable["kind"] != "supporting":
                continue
            match = self._match_deliverable(deliverable, candidates, asset_candidates, allowed_formats | self._asset_extensions())
            if match and match not in used:
                selected.append(match)
                used.add(match)

        return selected

    def _normalize_deliverables(self, deliverables: list[str]) -> list[dict]:
        normalized = []
        for i, item in enumerate(deliverables):
            text = item.strip()
            lower = text.lower()
            kind = "primary" if i == 0 else "supporting"
            if any(word in lower for word in ("worksheet", "template", "checklist", "resource", "bonus", "supporting")):
                kind = "supporting"
            normalized.append({"raw": text, "keywords": self._keywords(text), "kind": kind})
        return normalized

    def _allowed_extensions(self, spec: dict) -> set[str]:
        formats = spec.get("hard_constraints", {}).get("formats", [])
        allowed: set[str] = set()
        for fmt in formats:
            token = fmt.strip().lower().lstrip(".")
            if token in {"pdf", "docx", "pptx", "xlsx", "md"}:
                allowed.add(f".{token}")
        return allowed or {".pdf", ".md", ".docx"}

    def _asset_extensions(self) -> set[str]:
        return {".pdf", ".md", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".png", ".jpg", ".jpeg"}

    def _match_deliverable(
        self,
        deliverable: dict,
        candidates: list[Path],
        asset_candidates: list[Path],
        allowed_formats: set[str],
    ) -> Path | None:
        pool = candidates + asset_candidates
        ranked: list[tuple[int, Path]] = []
        for path in pool:
            if path.suffix.lower() not in allowed_formats:
                continue
            score = self._deliverable_match_score(deliverable, path)
            if score > 0:
                ranked.append((score, path))
        ranked.sort(key=lambda item: (-item[0], item[1].name))
        return ranked[0][1] if ranked else None

    def _deliverable_match_score(self, deliverable: dict, path: Path) -> int:
        score = 0
        name_tokens = set(self._keywords(path.stem))
        if deliverable["kind"] == "primary" and path.parent.name == "output":
            score += 3
        if path.suffix.lower() in {".pdf", ".docx", ".md"}:
            score += 1
        for keyword in deliverable["keywords"]:
            if keyword in name_tokens:
                score += 2
        if not deliverable["keywords"] and path.parent.name == "output":
            score += 1
        return score

    def _keywords(self, text: str) -> list[str]:
        return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2]

    def _build_manifest(self, deliverables: list[Path], spec: dict) -> str:
        product_type = spec.get("product_type", "Digital Product")
        topic = spec.get("topic_angle", "")
        expected = spec.get("deliverables", [])

        lines = [
            f"# Package Contents",
            f"",
            f"**Product:** {topic}",
            f"**Type:** {product_type}",
            f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d')}",
            f"",
            f"## Expected Deliverables",
            f"",
        ]

        if expected:
            for item in expected:
                lines.append(f"- {item}")
        else:
            lines.append("- No explicit deliverables listed in spec.md")

        lines += ["", "## Files", ""]

        for p in deliverables:
            size_kb = p.stat().st_size // 1024 if p.exists() else 0
            lines.append(f"- `{p.name}` ({size_kb} KB)")

        lines += [
            "",
            "## Usage",
            "",
            "Open the primary deliverable first, then use any supporting assets as referenced in the spec.",
            "",
            "---",
            "*Generated by Content Factory*",
        ]
        return "\n".join(lines)

    def _create_zip(
        self, output_dir: Path, deliverables: list[Path], spec: dict
    ) -> Path:
        topic_slug = (
            spec.get("topic_angle", "product")
            .lower()
            .replace(" ", "-")[:40]
        )
        zip_path = output_dir / f"{topic_slug}-package.zip"
        readme_path = output_dir / "README.md"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if readme_path.exists():
                zf.write(readme_path, readme_path.name)
            for p in deliverables:
                if p.exists() and p != zip_path:
                    zf.write(p, p.name)

        return zip_path

    def _stub_readme(self, spec: dict) -> str:
        return (
            f"# Package Contents (dry-run stub)\n\n"
            f"**Product type:** {spec.get('product_type', 'unknown')}\n\n"
            "Files would be listed here after a full pipeline run.\n"
        )
