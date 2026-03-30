"""Model/provider routing for Content Factory agents."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str


class ModelRouter:
    """Resolve provider/model settings for a given agent.

    Precedence (highest first):
    1. CONTENT_FACTORY_MODEL_<AGENT_NAME>
    2. CONTENT_FACTORY_MODEL
    3. agent default model

    Provider selection:
    1. CONTENT_FACTORY_PROVIDER_<AGENT_NAME>
    2. CONTENT_FACTORY_PROVIDER
    3. inferred from model name
    4. anthropic
    """

    @staticmethod
    def resolve(agent_name: str, default_model: str) -> ModelConfig:
        normalized = agent_name.upper().replace("-", "_")
        model = (
            os.environ.get(f"CONTENT_FACTORY_MODEL_{normalized}")
            or os.environ.get("CONTENT_FACTORY_MODEL")
            or default_model
        )
        provider = (
            os.environ.get(f"CONTENT_FACTORY_PROVIDER_{normalized}")
            or os.environ.get("CONTENT_FACTORY_PROVIDER")
            or ModelRouter._infer_provider(model)
        )
        return ModelConfig(provider=provider, model=model)

    @staticmethod
    def _infer_provider(model: str) -> str:
        lower = model.lower()
        if lower.startswith(("gpt-", "openai/")):
            return "openai"
        if lower.startswith(("claude-", "anthropic/")):
            return "anthropic"
        return "anthropic"
