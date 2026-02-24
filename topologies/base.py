"""Shared topology runtime abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from core.orchestrator import Orchestrator, TurnResult


@dataclass
class BaseTopology(ABC):
    """Base workflow controller for scheduling agent turns."""

    orchestrator: Orchestrator
    max_retries_per_role: int = 0
    fail_fast: bool = True
    skipped_roles: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.max_retries_per_role < 0:
            raise ValueError("max_retries_per_role must be >= 0")

    @abstractmethod
    def plan_roles(self) -> list[str]:
        """Return role execution order for this topology run."""

    def should_skip(self, role: str) -> bool:
        """Decide whether a role should be skipped."""
        return role in self.skipped_roles

    def kickoff_receiver(self, roles: list[str]) -> str | None:
        """Pick first runnable role to receive kickoff task."""
        for role in roles:
            if not self.should_skip(role):
                return role
        return None

    def run(self, kickoff_content: str) -> list[TurnResult]:
        """Execute topology roles with shared retry/skip/fail-fast controls."""
        roles = self.plan_roles()
        receiver = self.kickoff_receiver(roles)
        if receiver is None:
            return []

        self.orchestrator.kickoff(receiver, kickoff_content)

        results: list[TurnResult] = []
        for role in roles:
            if self.should_skip(role):
                continue

            attempt_results = self.run_role(role)
            results.extend(attempt_results)

            final_result = attempt_results[-1]
            if self.should_stop(final_result):
                break

        return results

    def run_role(self, role: str) -> list[TurnResult]:
        """Run one role with retry handling."""
        attempts: list[TurnResult] = []
        max_attempts = self.max_retries_per_role + 1
        for _ in range(max_attempts):
            result = self.orchestrator.run_turn(role)
            attempts.append(result)
            if result.success or result.stop:
                break
        return attempts

    def should_stop(self, result: TurnResult) -> bool:
        """Stop workflow on explicit stop signal or fail-fast failure."""
        if result.stop:
            return True
        return (not result.success) and self.fail_fast
