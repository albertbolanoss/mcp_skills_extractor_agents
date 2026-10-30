"""Generic, provider-agnostic model configuration."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class LLMProvider(StrEnum):
    """Supported LLM backend providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    PORTKEY = "portkey"


@dataclass(frozen=True, slots=True)
class ChatConfig:
    """Immutable configuration for a chat model, shared across providers.

    Common fields cover what every OpenAI-compatible provider needs. Anything
    provider-specific (e.g. Portkey's config id) goes in ``extra`` so the
    dataclass stays generic and new providers don't require schema changes.

    Attributes:
        provider: Which LLM backend to use.
        model: Model identifier as configured in the gateway.
        api_key: API key for the gateway.
        base_url: Gateway base URL.
        temperature: Sampling temperature.
        extra: Provider-specific options (e.g. ``{"config_id": "pc-..."}``).
    """

    provider: LLMProvider
    model: str
    api_key: str
    base_url: str
    temperature: float = 0.7
    extra: Mapping[str, Any] = field(default_factory=dict)
