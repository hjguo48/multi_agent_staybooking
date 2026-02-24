"""Base agent contract used by all specialist roles."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core import AgentMessage, Artifact, MessageLog, ProjectState, ReviewResult, ReviewStatus


class BaseAgent(ABC):
    """Unified interface for all multi-agent roles."""

    def __init__(
        self,
        role: str,
        system_prompt: str,
        tools: list[str] | None = None,
    ) -> None:
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.memory = MessageLog()

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
        }
