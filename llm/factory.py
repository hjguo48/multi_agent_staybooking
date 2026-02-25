"""LLM profile loader and client factory."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .client import AnthropicClaudeClient, BaseLLMClient, MockLLMClient


@dataclass(frozen=True)
class LLMProfile:
    """Serializable LLM runtime profile."""

    name: str
    provider: str
    model: str
    enabled: bool = True
    api_key_env: str = ""
    temperature: float = 0.2
    max_output_tokens: int = 2048
    timeout_seconds: float = 30.0
    max_retries: int = 2


@dataclass(frozen=True)
class LLMRegistry:
    """Collection of LLM profiles."""

    default: str
    profiles: dict[str, LLMProfile]

    def get(self, name: str | None = None) -> LLMProfile:
        key = (name or self.default).strip().lower()
        if key not in self.profiles:
            raise KeyError(f"Unknown LLM profile: {name}")
        return self.profiles[key]


def load_llm_registry(path: Path) -> LLMRegistry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("LLM config root must be an object")

    default = str(payload.get("default", "")).strip().lower()
    profiles_payload = payload.get("profiles")
    if not isinstance(profiles_payload, dict):
        raise ValueError("profiles must be an object")

    profiles: dict[str, LLMProfile] = {}
    for key, value in profiles_payload.items():
        name = str(key).strip().lower()
        if not isinstance(value, dict):
            raise ValueError(f"profile '{name}' must be an object")
        profile = LLMProfile(
            name=name,
            provider=str(value.get("provider", "")).strip().lower(),
            model=str(value.get("model", "")).strip(),
            enabled=bool(value.get("enabled", True)),
            api_key_env=str(value.get("api_key_env", "")).strip(),
            temperature=float(value.get("temperature", 0.2)),
            max_output_tokens=int(value.get("max_output_tokens", 2048)),
            timeout_seconds=float(value.get("timeout_seconds", 30.0)),
            max_retries=int(value.get("max_retries", 2)),
        )
        profiles[name] = profile

    if default not in profiles:
        raise ValueError(f"default profile '{default}' missing")

    return LLMRegistry(default=default, profiles=profiles)


def _build_from_profile(profile: LLMProfile) -> tuple[BaseLLMClient | None, str]:
    if not profile.enabled:
        return None, "profile disabled"

    if profile.provider == "mock":
        return MockLLMClient(), "mock profile enabled"

    if profile.provider == "anthropic":
        if not profile.api_key_env:
            return None, "missing api_key_env in profile"
        api_key = os.getenv(profile.api_key_env, "").strip()
        if not api_key:
            return None, f"missing env var: {profile.api_key_env}"
        client = AnthropicClaudeClient(
            api_key=api_key,
            timeout_seconds=profile.timeout_seconds,
            max_retries=profile.max_retries,
        )
        return client, "anthropic client ready"

    return None, f"unsupported provider: {profile.provider}"


def create_llm_client(
    registry: LLMRegistry,
    *,
    profile_name: str | None = None,
) -> tuple[BaseLLMClient | None, LLMProfile, str]:
    profile = registry.get(profile_name)
    client, reason = _build_from_profile(profile)
    return client, profile, reason
