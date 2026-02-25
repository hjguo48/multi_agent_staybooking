"""Hub-and-Spoke topology implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.models import AgentMessage, MessageType
from core.orchestrator import TurnResult

from .base import BaseTopology

DEFAULT_HUB_SPOKE_ROLES = [
    "pm",
    "architect",
    "backend_dev",
    "frontend_dev",
    "qa",
    "devops",
]


@dataclass
class HubAndSpokeTopology(BaseTopology):
    """Route all work through a coordinator role."""

    coordinator_role: str = "coordinator"
    spoke_roles: list[str] = field(default_factory=lambda: list(DEFAULT_HUB_SPOKE_ROLES))
    max_cycles: int = 32

    def plan_roles(self) -> list[str]:
        return [self.coordinator_role, *self.spoke_roles]

    def _latest_coordinator_route(self) -> str | None:
        for message in reversed(self.orchestrator.state.message_log.messages):
            if (
                message.sender == self.coordinator_role
                and message.msg_type == MessageType.TASK
                and message.receiver in self.spoke_roles
            ):
                return message.receiver
        return None

    def _send_spoke_status(self, role: str, result: TurnResult) -> None:
        self.orchestrator.route_message(
            AgentMessage(
                sender=role,
                receiver=self.coordinator_role,
                content=f"Spoke turn finished: success={result.success}, stop={result.stop}",
                msg_type=MessageType.STATUS,
                metadata={
                    "role": role,
                    "success": result.success,
                    "stop": result.stop,
                    "error": result.error,
                },
            )
        )

    def run(self, kickoff_content: str) -> list[TurnResult]:
        if self.should_skip(self.coordinator_role):
            return []

        self.orchestrator.kickoff(self.coordinator_role, kickoff_content)
        results: list[TurnResult] = []

        for _ in range(self.max_cycles):
            coordinator_attempts = self.run_role(self.coordinator_role)
            results.extend(coordinator_attempts)
            coordinator_result = coordinator_attempts[-1]
            if self.should_stop(coordinator_result):
                break

            next_role = self._latest_coordinator_route()
            if next_role is None:
                break
            if self.should_skip(next_role):
                continue

            spoke_attempts = self.run_role(next_role)
            results.extend(spoke_attempts)
            spoke_result = spoke_attempts[-1]
            self._send_spoke_status(next_role, spoke_result)

            if spoke_result.success:
                self.orchestrator.state.increment_iteration()
            if self.should_stop(spoke_result):
                break

        return results
