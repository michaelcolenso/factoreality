"""Base class for all Content Factory pipeline agents."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .local_llm import LocalLLM


class BaseAgent:
    """
    Shared behaviour for every pipeline agent.

    Each subclass implements:
      run(spec, dry_run) -> Path      — execute the stage, return output path
      revise(feedback, output_path, spec, dry_run) -> Path  — targeted fix on REVISE verdict
    """

    #: Override in subclass — readable name for log messages
    name: str = "BaseAgent"

    #: Model to use for this agent (can be overridden per-agent or via env)
    default_model: str = "claude-opus-4-6"

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.model = os.environ.get("CONTENT_FACTORY_MODEL", self.default_model)

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------

    def run(self, spec: dict, dry_run: bool = False) -> Path:
        raise NotImplementedError(f"{self.name}.run() must be implemented")

    def revise(
        self,
        feedback: str,
        output_path: Path,
        spec: dict,
        dry_run: bool = False,
    ) -> Path:
        raise NotImplementedError(f"{self.name}.revise() must be implemented")

    # ------------------------------------------------------------------
    # LLM call helper
    # ------------------------------------------------------------------

    def call_llm(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 8192,
    ) -> str:
        """
        Call the Anthropic Claude API and return the text response.

        Requires ANTHROPIC_API_KEY in the environment.
        """
        use_local = os.environ.get("CONTENT_FACTORY_LOCAL_LLM", "").lower() in {"1", "true", "yes"}
        if use_local or not os.environ.get("ANTHROPIC_API_KEY"):
            return LocalLLM().generate(system_prompt=system_prompt, user_message=user_message, max_tokens=max_tokens)

        import anthropic  # lazy import — only needed at runtime

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    # ------------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------------

    def read_file(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def write_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def read_spec(self) -> str:
        return self.read_file(self.project_dir / "spec.md")

    def read_plan(self) -> str:
        plan_path = self.project_dir / "plan.md"
        return self.read_file(plan_path) if plan_path.exists() else ""
