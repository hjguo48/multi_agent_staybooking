"""Base agent contract used by all specialist roles."""

from __future__ import annotations

import copy
import json
import re
from abc import ABC, abstractmethod
from typing import Any

from core import AgentMessage, Artifact, MessageLog, ProjectState, ReviewResult, ReviewStatus
from llm import BaseLLMClient, LLMProfile, LLMRequest, LLMResponse


class BaseAgent(ABC):
    """Unified interface for all multi-agent roles."""

    def __init__(
        self,
        role: str,
        system_prompt: str,
        tools: list[str] | None = None,
        llm_client: BaseLLMClient | None = None,
        llm_profile: LLMProfile | None = None,
    ) -> None:
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.memory = MessageLog()
        self.llm_client = llm_client
        self.llm_profile = llm_profile

    def receive(self, message: AgentMessage) -> None:
        """Process incoming message and append to local memory."""
        self.memory.append(message)

    @abstractmethod
    def act(self, context: ProjectState) -> dict[str, Any]:
        """Generate output artifacts/messages for the current turn."""

    def review(self, artifact: Artifact) -> ReviewResult:
        """Default review behavior; specialized agents may override."""
        return ReviewResult(
            status=ReviewStatus.APPROVED,
            comments=[f"{self.role} review passed for {artifact.artifact_id}"],
            reviewer=self.role,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "system_prompt": self.system_prompt,
            "tools": self.tools,
            "memory_size": len(self.memory.messages),
            "llm_enabled": self.llm_client is not None,
            "llm_profile": self.llm_profile.name if self.llm_profile else None,
        }

    def _context_snapshot(self, context: ProjectState) -> dict[str, Any]:
        artifact_versions = {
            key: len(items)
            for key, items in context.artifact_store.artifact_versions.items()
        }
        return {
            "role": self.role,
            "state_fields_present": {
                "requirements": context.requirements is not None,
                "architecture": context.architecture is not None,
                "backend_code": context.backend_code is not None,
                "frontend_code": context.frontend_code is not None,
                "qa_report": context.qa_report is not None,
                "deployment": context.deployment is not None,
            },
            "artifact_versions": artifact_versions,
            "iteration": context.iteration,
            "message_count": len(context.message_log.messages),
            "latest_message": (
                context.message_log.messages[-1].to_dict()
                if context.message_log.messages
                else None
            ),
        }

    @staticmethod
    def _extract_json_payload(raw_text: str) -> dict[str, Any] | None:
        text = raw_text.strip()
        if not text:
            return None

        candidates: list[str] = [text]

        fenced_matches = re.findall(
            r"```(?:json)?\s*(\{[\s\S]*?\})\s*```",
            text,
            flags=re.IGNORECASE,
        )
        candidates.extend(fenced_matches)

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidates.append(text[start : end + 1])

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    def _llm_json_or_fallback(
        self,
        *,
        context: ProjectState,
        task_instruction: str,
        fallback_payload: dict[str, Any],
        fallback_usage: dict[str, int],
        required_keys: list[str],
        extra_output_constraints: list[str] | None = None,
        retry_on_invalid_json: bool = False,
        json_retry_attempts: int = 1,
        max_output_tokens_override: int | None = None,
    ) -> tuple[dict[str, Any], dict[str, int], dict[str, Any]]:
        if self.llm_client is None or self.llm_profile is None:
            return copy.deepcopy(fallback_payload), dict(fallback_usage), {"source": "rule"}

        snapshot = self._context_snapshot(context)
        max_output_tokens = (
            max_output_tokens_override
            if max_output_tokens_override is not None
            else self.llm_profile.max_output_tokens
        )
        constraints = [
            "- Return ONLY one JSON object.",
            "- Do not wrap in markdown fences.",
            f"- Required top-level keys: {required_keys}",
        ]
        if extra_output_constraints:
            constraints.extend(extra_output_constraints)

        user_prompt = (
            f"Task:\n{task_instruction}\n\n"
            "Context snapshot:\n"
            f"{json.dumps(snapshot, ensure_ascii=True)}\n\n"
            "Output constraints:\n"
            + "\n".join(constraints)
            + "\n"
        )
        request = LLMRequest(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            model=self.llm_profile.model,
            temperature=self.llm_profile.temperature,
            max_output_tokens=max_output_tokens,
            response_format="json_object",
            metadata={"role": self.role, "task": task_instruction},
        )

        usage = {"tokens": 0, "api_calls": 0}

        def _call_llm(req: LLMRequest) -> tuple[LLMResponse | None, Exception | None]:
            try:
                resp = self.llm_client.generate(req)
            except Exception as exc:
                return None, exc
            usage["tokens"] += max(resp.total_tokens, 0)
            usage["api_calls"] += 1
            return resp, None

        def _fallback(reason: str) -> tuple[dict[str, Any], dict[str, int], dict[str, Any]]:
            fallback_usage_payload = (
                dict(usage) if usage["api_calls"] > 0 else dict(fallback_usage)
            )
            return (
                copy.deepcopy(fallback_payload),
                fallback_usage_payload,
                {"source": "rule_fallback", "reason": reason},
            )

        def _validate_payload(resp: LLMResponse) -> tuple[dict[str, Any] | None, str | None]:
            parsed_payload = self._extract_json_payload(resp.content)
            if parsed_payload is None:
                if resp.output_tokens >= max_output_tokens:
                    return None, "invalid_json_truncated_output"
                return None, "invalid_json"
            missing_keys = [key for key in required_keys if key not in parsed_payload]
            if missing_keys:
                return None, f"missing_keys:{missing_keys}"
            return parsed_payload, None

        response, error = _call_llm(request)
        if error is not None:
            return _fallback(f"llm_error:{error}")
        assert response is not None

        parsed, failure_reason = _validate_payload(response)
        if parsed is not None:
            return parsed, dict(usage), {
                "source": "llm",
                "provider": response.provider,
                "model": response.model,
            }

        if retry_on_invalid_json:
            retry_count = max(int(json_retry_attempts), 1)
            for retry_index in range(1, retry_count + 1):
                retry_prompt = (
                    f"Task:\n{task_instruction}\n\n"
                    f"The previous response failed validation ({failure_reason or 'invalid_json'}).\n"
                    "Return a compact JSON object that strictly follows the constraints.\n\n"
                    "Output constraints:\n"
                    + "\n".join(constraints)
                    + "\n"
                    "- Keep output concise to avoid truncation.\n"
                    "- Keep code_bundle small and minimal.\n"
                )
                retry_request = LLMRequest(
                    system_prompt=self.system_prompt,
                    user_prompt=retry_prompt,
                    model=self.llm_profile.model,
                    temperature=self.llm_profile.temperature,
                    max_output_tokens=max_output_tokens,
                    response_format="json_object",
                    metadata={
                        "role": self.role,
                        "task": task_instruction,
                        "retry": retry_index,
                    },
                )
                retry_response, retry_error = _call_llm(retry_request)
                if retry_error is not None:
                    return _fallback(f"llm_error_retry:{retry_error}")
                assert retry_response is not None
                parsed, failure_reason = _validate_payload(retry_response)
                if parsed is not None:
                    return parsed, dict(usage), {
                        "source": "llm",
                        "provider": retry_response.provider,
                        "model": retry_response.model,
                        "retry_count": retry_index,
                    }
            return _fallback(f"{failure_reason or 'invalid_json'}_after_retry")

        return _fallback(failure_reason or "invalid_json")
