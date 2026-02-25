"""Peer Review topology implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from core import AgentMessage, MessageType, ReviewStatus
from core.orchestrator import TurnResult

from .base import BaseTopology

DEFAULT_PEER_REVIEW_BUILD_ROLES = [
    "pm",
    "architect",
    "backend_dev",
    "frontend_dev",
]


@dataclass
class PeerReviewTopology(BaseTopology):
    """Run development roles with bounded peer-review revision loops."""

    reviewer_role: str = "reviewer"
    build_roles: list[str] = field(
        default_factory=lambda: list(DEFAULT_PEER_REVIEW_BUILD_ROLES)
    )
    review_targets: dict[str, str] = field(
        default_factory=lambda: {
            "backend_dev": "backend_code",
            "frontend_dev": "frontend_code",
        }
    )
    qa_role: str = "qa"
    devops_role: str = "devops"
    max_revisions_per_target: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.max_revisions_per_target < 0:
            raise ValueError("max_revisions_per_target must be >= 0")

    def plan_roles(self) -> list[str]:
        return [*self.build_roles, self.reviewer_role, self.qa_role, self.devops_role]

    def _send_review_message(
        self,
        producer_role: str,
        artifact_key: str,
        review_status: ReviewStatus,
        revision_round: int,
        comments: list[str],
    ) -> None:
        self.orchestrator.route_message(
            AgentMessage(
                sender=self.reviewer_role,
                receiver=producer_role,
                content=f"{artifact_key} review={review_status.value}; round={revision_round}",
                msg_type=MessageType.REVIEW,
                metadata={
                    "artifact_key": artifact_key,
                    "review_status": review_status.value,
                    "revision_round": revision_round,
                    "comments": comments,
                },
            )
        )

    def _append_review_turn(
        self,
        results: list[TurnResult],
        review_status: ReviewStatus,
        stop: bool = False,
        error: str | None = None,
    ) -> None:
        results.append(
            TurnResult(
                agent_role=self.reviewer_role,
                success=review_status == ReviewStatus.APPROVED,
                stop=stop,
                error=error,
            )
        )

    def _run_developer_with_review(
        self,
        results: list[TurnResult],
        producer_role: str,
        artifact_key: str,
    ) -> bool:
        revisions = 0
        reviewer = self.orchestrator.get_agent(self.reviewer_role)

        while True:
            attempts = self.run_role(producer_role)
            results.extend(attempts)
            producer_result = attempts[-1]
            if self.should_stop(producer_result):
                return False

            artifact = self.orchestrator.state.get_latest_artifact(artifact_key)
            if artifact is None:
                self._append_review_turn(
                    results,
                    review_status=ReviewStatus.REVISION_NEEDED,
                    stop=self.fail_fast,
                    error=f"missing artifact for key={artifact_key}",
                )
                return not self.fail_fast

            review_result = reviewer.review(artifact)
            self._send_review_message(
                producer_role=producer_role,
                artifact_key=artifact_key,
                review_status=review_result.status,
                revision_round=revisions,
                comments=review_result.comments,
            )
            self._append_review_turn(
                results,
                review_status=review_result.status,
            )

            if review_result.status == ReviewStatus.APPROVED:
                return True

            if revisions >= self.max_revisions_per_target:
                self._append_review_turn(
                    results,
                    review_status=ReviewStatus.REVISION_NEEDED,
                    stop=self.fail_fast,
                    error=(
                        f"revision budget exhausted for {producer_role}: "
                        f"max_revisions={self.max_revisions_per_target}"
                    ),
                )
                return not self.fail_fast

            revisions += 1
            self.orchestrator.state.increment_iteration()

    def run(self, kickoff_content: str) -> list[TurnResult]:
        if not self.build_roles:
            return []
        if self.should_skip(self.reviewer_role):
            return []

        self.orchestrator.kickoff(self.build_roles[0], kickoff_content)
        results: list[TurnResult] = []
        aborted = False

        for role in self.build_roles:
            if self.should_skip(role):
                continue

            artifact_key = self.review_targets.get(role)
            if artifact_key:
                should_continue = self._run_developer_with_review(
                    results=results,
                    producer_role=role,
                    artifact_key=artifact_key,
                )
                if not should_continue:
                    aborted = True
                    break
                continue

            attempts = self.run_role(role)
            results.extend(attempts)
            final_result = attempts[-1]
            if self.should_stop(final_result):
                return results

        if aborted:
            return results

        for role in [self.qa_role, self.devops_role]:
            if self.should_skip(role):
                continue
            attempts = self.run_role(role)
            results.extend(attempts)
            if self.should_stop(attempts[-1]):
                break

        return results
