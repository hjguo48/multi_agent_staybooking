"""Iterative Feedback topology implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from core import AgentMessage, MessageType
from core.orchestrator import TurnResult

from .base import BaseTopology

DEFAULT_ITERATIVE_BUILD_ROLES = [
    "pm",
    "architect",
    "backend_dev",
    "frontend_dev",
]


@dataclass
class IterativeFeedbackTopology(BaseTopology):
    """Run QA-driven feedback loops with iteration cap and anti-loop controls."""

    build_roles: list[str] = field(default_factory=lambda: list(DEFAULT_ITERATIVE_BUILD_ROLES))
    qa_role: str = "qa"
    devops_role: str = "devops"
    max_feedback_iterations: int = 2
    max_stagnant_rounds: int = 1
    qa_pass_threshold: float = 0.85
    default_feedback_role: str = "backend_dev"
    feedback_role_map: dict[str, str] = field(
        default_factory=lambda: {
            "frontend": "frontend_dev",
            "ui": "frontend_dev",
            "backend": "backend_dev",
            "auth": "backend_dev",
        }
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.max_feedback_iterations < 0:
            raise ValueError("max_feedback_iterations must be >= 0")
        if self.max_stagnant_rounds < 0:
            raise ValueError("max_stagnant_rounds must be >= 0")
        if self.qa_pass_threshold < 0:
            raise ValueError("qa_pass_threshold must be >= 0")

    def plan_roles(self) -> list[str]:
        return [*self.build_roles, self.qa_role, self.devops_role]

    def _latest_version(self, artifact_key: str) -> int:
        artifact = self.orchestrator.state.get_latest_artifact(artifact_key)
        return artifact.version if artifact is not None else 0

    def _qa_gate_passed(self) -> bool:
        qa_artifact = self.orchestrator.state.get_latest_artifact("qa_report")
        if qa_artifact is None or not isinstance(qa_artifact.content, dict):
            return False
        summary = qa_artifact.content.get("summary", {})
        if not isinstance(summary, dict):
            return False

        pass_rate = float(summary.get("test_pass_rate", 0.0))
        critical_bugs = int(summary.get("critical_bugs", 1))
        return pass_rate >= self.qa_pass_threshold and critical_bugs == 0

    def _qa_signature(self) -> str:
        qa_artifact = self.orchestrator.state.get_latest_artifact("qa_report")
        if qa_artifact is None or not isinstance(qa_artifact.content, dict):
            return "qa:none"

        summary = qa_artifact.content.get("summary", {})
        pass_rate = summary.get("test_pass_rate", "na")
        critical_bugs = summary.get("critical_bugs", "na")
        major_bugs = summary.get("major_bugs", "na")

        bug_ids: list[str] = []
        bug_reports = qa_artifact.content.get("bug_reports", [])
        if isinstance(bug_reports, list):
            for item in bug_reports:
                if not isinstance(item, dict):
                    continue
                bug_id = str(item.get("bug_id", "")).strip()
                if bug_id:
                    bug_ids.append(bug_id)
        bug_ids.sort()
        return (
            f"qa:pass_rate={pass_rate}|critical={critical_bugs}|major={major_bugs}"
            f"|bugs={','.join(bug_ids)}"
        )

    def _select_feedback_role(self) -> str:
        qa_artifact = self.orchestrator.state.get_latest_artifact("qa_report")
        if qa_artifact is None or not isinstance(qa_artifact.content, dict):
            return self.default_feedback_role

        bug_reports = qa_artifact.content.get("bug_reports", [])
        if not isinstance(bug_reports, list):
            return self.default_feedback_role

        for bug in bug_reports:
            if not isinstance(bug, dict):
                continue
            category = str(bug.get("category", "")).lower()
            file_path = str(bug.get("file", "")).lower()
            probe = f"{category} {file_path}"
            for marker, role in self.feedback_role_map.items():
                if marker in probe:
                    return role
        return self.default_feedback_role

    def _append_control_turn(
        self,
        results: list[TurnResult],
        *,
        role: str,
        error: str,
    ) -> None:
        results.append(
            TurnResult(
                agent_role=role,
                success=False,
                stop=True,
                error=error,
            )
        )

    def _route_feedback_task(self, role: str, reason: str, iteration: int) -> None:
        self.orchestrator.route_message(
            AgentMessage(
                sender="orchestrator",
                receiver=role,
                content=f"Iterative feedback iteration={iteration}: {reason}",
                msg_type=MessageType.FEEDBACK,
                metadata={
                    "feedback_iteration": iteration,
                    "reason": reason,
                    "target_role": role,
                },
            )
        )

    def run(self, kickoff_content: str) -> list[TurnResult]:
        if not self.build_roles:
            return []

        first_role = next((role for role in self.build_roles if not self.should_skip(role)), None)
        if first_role is None:
            return []
        self.orchestrator.kickoff(first_role, kickoff_content)

        results: list[TurnResult] = []

        for role in self.build_roles:
            if self.should_skip(role):
                continue
            attempts = self.run_role(role)
            results.extend(attempts)
            if self.should_stop(attempts[-1]):
                return results

        feedback_iteration = 0
        stagnant_rounds = 0
        previous_failed_signature: str | None = None
        previous_failed_versions: tuple[int, int] | None = None

        while True:
            if self.should_skip(self.qa_role):
                break

            qa_attempts = self.run_role(self.qa_role)
            results.extend(qa_attempts)
            qa_result = qa_attempts[-1]
            if self.should_stop(qa_result):
                break

            if self._qa_gate_passed():
                if not self.should_skip(self.devops_role):
                    devops_attempts = self.run_role(self.devops_role)
                    results.extend(devops_attempts)
                break

            current_signature = self._qa_signature()
            current_versions = (
                self._latest_version("backend_code"),
                self._latest_version("frontend_code"),
            )

            if (
                previous_failed_signature == current_signature
                and previous_failed_versions == current_versions
            ):
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0

            if stagnant_rounds > self.max_stagnant_rounds:
                self._append_control_turn(
                    results,
                    role=self.qa_role,
                    error=(
                        "anti-loop triggered: repeated QA failure signature "
                        f"with unchanged code versions for {stagnant_rounds} rounds"
                    ),
                )
                break

            if feedback_iteration >= self.max_feedback_iterations:
                self._append_control_turn(
                    results,
                    role=self.qa_role,
                    error=(
                        "feedback iteration cap reached: "
                        f"max_feedback_iterations={self.max_feedback_iterations}"
                    ),
                )
                break

            feedback_iteration += 1
            self.orchestrator.state.increment_iteration()

            feedback_role = self._select_feedback_role()
            self._route_feedback_task(
                feedback_role,
                reason=f"qa gate failed ({current_signature})",
                iteration=feedback_iteration,
            )

            if not self.should_skip(feedback_role):
                feedback_attempts = self.run_role(feedback_role)
                results.extend(feedback_attempts)
                feedback_result = feedback_attempts[-1]
                if self.should_stop(feedback_result):
                    break

            previous_failed_signature = current_signature
            previous_failed_versions = current_versions

        return results
