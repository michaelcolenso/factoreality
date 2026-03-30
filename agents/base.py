"""Base class for all Content Factory pipeline agents."""

from __future__ import annotations

from pathlib import Path

from utils.model_router import ModelRouter


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
        config = ModelRouter.resolve(self.name, self.default_model)
        self.provider = config.provider
        self.model = config.model

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
        """Call the configured provider and return the text response."""
        provider = self.provider
        selected_model = model or self.model

        if provider == "anthropic":
            import anthropic  # lazy import — only needed at runtime

            client = anthropic.Anthropic()
            response = client.messages.create(
                model=selected_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text

        if provider == "openai":
            try:
                from openai import OpenAI  # type: ignore
            except ImportError as exc:
                raise RuntimeError(
                    "OpenAI provider selected but `openai` package is not installed. "
                    "Add it to requirements.txt to use CONTENT_FACTORY_PROVIDER=openai."
                ) from exc

            client = OpenAI()
            response = client.responses.create(
                model=selected_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_output_tokens=max_tokens,
            )
            return getattr(response, "output_text", "")

        raise RuntimeError(
            f"Unsupported provider: {provider!r}. Supported providers: anthropic, openai."
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
