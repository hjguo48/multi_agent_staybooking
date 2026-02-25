"""Peer reviewer agent implementation for review-loop topologies."""

from __future__ import annotations

from typing import Any

from core import Artifact, ReviewResult, ReviewStatus
from core.project_state import ProjectState

from .base_agent import BaseAgent


class PeerReviewerAgent(BaseAgent):
    """Provide deterministic review decisions for code artifacts."""

    def __init__(
        self,
        role: str,
        system_prompt: str,
        tools: list[str] | None = None,
        *,
        enforce_second_pass: bool = True,
        review_targets: set[str] | None = None,
    ) -> None:
        super().__init__(role=role, system_prompt=system_prompt, tools=tools)
        self.enforce_second_pass = enforce_second_pass
        self.review_targets = review_targets or {"backend_code", "frontend_code"}

    def act(self, context: ProjectState) -> dict[str, Any]:
        return {}

    def review(self, artifact: Artifact) -> ReviewResult:
        if artifact.artifact_type not in self.review_targets:
            return ReviewResult(
                status=ReviewStatus.APPROVED,
                comments=[f"{artifact.artifact_type} does not require peer review gate."],
                reviewer=self.role,
            )

        if self.enforce_second_pass and artifact.version == 1:
            return ReviewResult(
                status=ReviewStatus.REVISION_NEEDED,
                comments=["Initial submission needs revision for production-readiness checks."],
                blocking_issues=[f"{artifact.artifact_type}:v1 requires one revision round"],
                reviewer=self.role,
            )

        return ReviewResult(
            status=ReviewStatus.APPROVED,
            comments=[f"{artifact.artifact_type}:v{artifact.version} approved"],
            reviewer=self.role,
        )
