"""Base class for all Content Factory pipeline agents."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from utils.agentic_harness import AgenticHarness


class BaseAgent:
    """
    Shared behaviour for every pipeline agent.

    Each subclass implements:
      run(spec, dry_run) -> Path      — execute the stage, return output path
      revise(feedback, output_path, spec, dry_run) -> Path  — targeted fix on REVISE verdict

    The default execution mode is the local agentic harness. It records each
    delegated task and resolves it with deterministic local synthesis instead of
    calling an external LLM API. This keeps orchestration inside the harness that
    is running the repository.
    """

    #: Override in subclass — readable name for log messages
    name: str = "BaseAgent"

    #: Logical model label retained for task metadata; no external API is called.
    default_model: str = "agentic-harness"

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.provider = os.environ.get("CONTENT_FACTORY_PROVIDER", "harness")
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
    # Agentic harness task helper
    # ------------------------------------------------------------------

    def call_agent(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 8192,
    ) -> str:
        """Execute a stage task inside the local agentic harness.

        ``max_tokens`` is accepted for compatibility with the old external LLM API call sites,
        but it is metadata only in harness mode.
        """
        provider = self.provider
        selected_model = model or self.model

        if provider in {"harness", "fake"}:
            self._record_harness_task(system_prompt, user_message, selected_model, max_tokens)
            return AgenticHarness.respond(system_prompt=system_prompt, user_message=user_message)

        raise RuntimeError(
            f"Unsupported provider: {provider!r}. This project is designed to run inside "
            "the local agentic harness only; supported providers are: harness, fake."
        )

    def call_llm(
        self,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 8192,
    ) -> str:
        """Backward-compatible alias for older stage code.

        Despite the historical method name, this does not call an outside LLM API.
        """
        return self.call_agent(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            max_tokens=max_tokens,
        )

    def _record_harness_task(
        self,
        system_prompt: str,
        user_message: str,
        selected_model: str,
        max_tokens: int,
    ) -> None:
        harness_dir = self.project_dir / ".harness"
        harness_dir.mkdir(parents=True, exist_ok=True)
        task_log = harness_dir / "tasks.md"
        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        system_excerpt = system_prompt.strip().split("\n", 1)[0][:160]
        user_excerpt = user_message.strip().replace("\n", " ")[:240]
        with task_log.open("a", encoding="utf-8") as handle:
            handle.write(
                f"## {timestamp} — {self.name}\n"
                f"- Provider: {self.provider}\n"
                f"- Harness model label: {selected_model}\n"
                f"- Max token hint: {max_tokens}\n"
                f"- Task: {system_excerpt}\n"
                f"- Input excerpt: {user_excerpt}\n\n"
            )

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
