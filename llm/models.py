"""Shared LLM request/response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LLMRequest:
    """Normalized request payload for provider clients."""

    system_prompt: str
    user_prompt: str
    model: str
    temperature: float = 0.2
    max_output_tokens: int = 2048
    response_format: str = "json_object"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Normalized response payload for provider clients."""

    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw_response: dict[str, Any] | None = None

    @property
    def total_tokens(self) -> int:
        return max(self.input_tokens, 0) + max(self.output_tokens, 0)
