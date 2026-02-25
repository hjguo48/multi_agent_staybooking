"""Coordinator agent implementation for Hub-and-Spoke routing."""

from __future__ import annotations

from typing import Any

from core.models import AgentMessage, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class CoordinatorAgent(BaseAgent):
    """Route tasks to specialist agents based on shared project state."""

    def __init__(
        self,
        role: str,
        system_prompt: str,
        tools: list[str] | None = None,
        *,
        max_qa_retries: int = 1,
        qa_fallback_role: str = "backend_dev",
    ) -> None:
        super().__init__(role=role, system_prompt=system_prompt, tools=tools)
        self.max_qa_retries = max_qa_retries
        self.qa_fallback_role = qa_fallback_role
        self.qa_retry_count = 0

    def _qa_gate_passed(self, context: ProjectState) -> bool:
        qa_artifact = context.get_latest_artifact("qa_report")
        if qa_artifact is None or not isinstance(qa_artifact.content, dict):
            return False

        summary = qa_artifact.content.get("summary", {})
        if not isinstance(summary, dict):
            return False

        pass_rate = float(summary.get("test_pass_rate", 0.0))
        critical_bugs = int(summary.get("critical_bugs", 1))
        return pass_rate >= 0.85 and critical_bugs == 0

    def _latest_version(self, context: ProjectState, key: str) -> int:
        artifact = context.get_latest_artifact(key)
        return artifact.version if artifact is not None else 0

    def _decide_next_role(self, context: ProjectState) -> tuple[str | None, str]:
        if context.requirements is None:
            return "pm", "requirements missing"
        if context.architecture is None:
            return "architect", "architecture missing"
        if context.backend_code is None:
            return "backend_dev", "backend implementation missing"
        if context.frontend_code is None:
            return "frontend_dev", "frontend implementation missing"
        if context.qa_report is None:
            return "qa", "qa validation pending"
        if context.deployment is not None:
            return None, "deployment completed"

        if self._qa_gate_passed(context):
            return "devops", "qa gate passed"

        qa_version = self._latest_version(context, "qa_report")
        backend_version = self._latest_version(context, "backend_code")
        frontend_version = self._latest_version(context, "frontend_code")

        if max(backend_version, frontend_version) > qa_version:
            return "qa", "re-run qa after code changes"

        if self.qa_retry_count < self.max_qa_retries:
            self.qa_retry_count += 1
            return self.qa_fallback_role, "qa gate failed, request rework"

        return None, "qa gate failed after retry budget"

    def act(self, context: ProjectState) -> dict[str, Any]:
        next_role, reason = self._decide_next_role(context)
        usage = {"tokens": 180, "api_calls": 1}

        if next_role is None:
            return {
                "messages": [
                    AgentMessage(
                        sender=self.role,
                        receiver="orchestrator",
                        content=f"Coordinator stop: {reason}",
                        msg_type=MessageType.STATUS,
                        metadata={"phase": "complete", "reason": reason},
                    )
                ],
                "usage": usage,
                "stop": True,
            }

        return {
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver=next_role,
                    content=f"Coordinator route -> {next_role}: {reason}",
                    msg_type=MessageType.TASK,
                    metadata={"next_role": next_role, "route_reason": reason},
                )
            ],
            "usage": usage,
        }
