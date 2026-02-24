"""Sequential topology implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import BaseTopology

DEFAULT_SEQUENTIAL_ROLES = [
    "pm",
    "architect",
    "backend_dev",
    "frontend_dev",
    "qa",
    "devops",
]


@dataclass
class SequentialTopology(BaseTopology):
    """Run agents in strict PM->Architect->Backend->Frontend->QA->DevOps order."""

    roles: list[str] = field(default_factory=lambda: list(DEFAULT_SEQUENTIAL_ROLES))

    def plan_roles(self) -> list[str]:
        return list(self.roles)
