"""Product Manager agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class ProductManagerAgent(BaseAgent):
    """Generate structured requirements from a project brief."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        fallback_requirements = {
            "project_name": "StayBooking",
            "functional_requirements": [
                {
                    "id": "FR-001",
                    "user_story": "As a guest, I want to register and login using JWT.",
                    "acceptance_criteria": [
                        "Given valid registration data, user account is created",
                        "Given valid credentials, JWT is returned on login",
                    ],
                    "priority": "Must",
                    "complexity": "Low",
                }
            ],
            "non_functional_requirements": [
                {"id": "NFR-001", "description": "Token-based authentication required"}
            ],
            "api_contracts": [
                {"endpoint": "/auth/register", "method": "POST", "auth_required": False},
                {"endpoint": "/auth/login", "method": "POST", "auth_required": False},
            ],
            "data_model": {
                "entities": ["User"],
                "relationships": [],
            },
        }
        requirements, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                "Generate requirements for a Java StayBooking auth slice. "
                "Include functional requirements, non-functional requirements, "
                "API contracts, and data model."
            ),
            fallback_payload=fallback_requirements,
            fallback_usage={"tokens": 420, "api_calls": 1},
            required_keys=[
                "project_name",
                "functional_requirements",
                "non_functional_requirements",
                "api_contracts",
                "data_model",
            ],
        )
        return {
            "state_updates": {"requirements": {"artifact_ref": "requirements:v1"}},
            "artifacts": [
                {
                    "store_key": "requirements",
                    "artifact": Artifact(
                        artifact_id="requirements-doc",
                        artifact_type="requirements",
                        producer=self.role,
                        content=requirements,
                        metadata={"generation": generation_meta},
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="architect",
                    content="Requirements ready for architecture design.",
                    msg_type=MessageType.TASK,
                    artifacts=["requirements-doc:v1"],
                )
            ],
            "usage": usage,
        }
