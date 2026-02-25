"""LLM provider clients with retry/timeouts."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import LLMRequest, LLMResponse


class LLMClientError(RuntimeError):
    """Raised when provider call fails and cannot be recovered."""


class BaseLLMClient(ABC):
    """Provider-agnostic LLM client interface."""

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate one response for a request."""


@dataclass
class AnthropicClaudeClient(BaseLLMClient):
    """Anthropic Claude Messages API client."""

    api_key: str
    timeout_seconds: float = 30.0
    max_retries: int = 2
    base_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_version: str = "2023-06-01"

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=self.base_url,
            method="POST",
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
            },
            data=body,
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
        return json.loads(raw)

    def generate(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model,
            "max_tokens": request.max_output_tokens,
            "temperature": request.temperature,
            "system": request.system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": request.user_prompt,
                }
            ],
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response_payload = self._post(payload)
                content_items = response_payload.get("content", [])
                text_chunks: list[str] = []
                if isinstance(content_items, list):
                    for item in content_items:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") == "text":
                            text_chunks.append(str(item.get("text", "")))
                usage = response_payload.get("usage", {})
                input_tokens = int(usage.get("input_tokens", 0))
                output_tokens = int(usage.get("output_tokens", 0))
                return LLMResponse(
                    content="\n".join(chunk for chunk in text_chunks if chunk).strip(),
                    provider="anthropic",
                    model=str(response_payload.get("model", request.model)),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    raw_response=response_payload,
                )
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                backoff = min(2 ** attempt, 4)
                time.sleep(backoff)
                continue
            except Exception as exc:  # pragma: no cover - safety net
                last_error = exc
                break

        raise LLMClientError(
            f"Anthropic generate failed after {self.max_retries + 1} attempts: {last_error}"
        )


@dataclass
class MockLLMClient(BaseLLMClient):
    """Deterministic fake client for tests and local pilot fallback."""

    response_text: str = "{}"
    provider_name: str = "mock"
    model_name: str = "mock-json-model"
    input_tokens: int = 50
    output_tokens: int = 80

    def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=self.response_text,
            provider=self.provider_name,
            model=request.model or self.model_name,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            raw_response={"request_metadata": request.metadata},
        )
