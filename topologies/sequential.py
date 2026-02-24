"""Sequential topology implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.orchestrator import Orchestrator, TurnResult

DEFAULT_SEQUENTIAL_ROLES = [
    "pm",
    "architect",
    "backend_dev",
    "frontend_dev",
    "qa",
    "devops",
]


@dataclass
class SequentialTopology:
    """Run agents in strict PM->Architect->Backend->Frontend->QA->DevOps order."""

    orchestrator: Orchestrator
    roles: list[str] = field(default_factory=lambda: list(DEFAULT_SEQUENTIAL_ROLES))

    def run(self, kickoff_content: str) -> list[TurnResult]:
        if not self.roles:
            return []
        self.orchestrator.kickoff(self.roles[0], kickoff_content)
        return self.orchestrator.run_sequence(self.roles)
