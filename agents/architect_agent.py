"""Architect agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class ArchitectAgent(BaseAgent):
    """Generate architecture artifacts from requirements."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        fallback_architecture = {
            "tech_stack": {
                "backend": {"language": "Java 17", "framework": "Spring Boot 3.x"},
                "frontend": {"framework": "React 18"},
                "database": {"primary": "PostgreSQL 15"},
                "infrastructure": {"container": "Docker"},
            },
            "modules": [
                {
                    "name": "auth-module",
                    "responsibility": "User registration, login, and JWT handling",
                    "dependencies": [],
                }
            ],
            "database_schema": {
                "tables": [{"name": "users", "columns": ["id", "username", "password_hash"]}]
            },
            "openapi_spec": {
                "paths": {
                    "/auth/register": {"post": {"summary": "Register user"}},
                    "/auth/login": {"post": {"summary": "Login user"}},
                }
            },
            "deployment": {
                "containers": ["backend", "frontend", "postgres"],
                "networking": {"mode": "bridge"},
            },
        }
        architecture, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                "Generate architecture design JSON for StayBooking auth-first scope. "
                "Include tech stack, modules, database schema, OpenAPI paths, and deployment."
            ),
            fallback_payload=fallback_architecture,
            fallback_usage={"tokens": 520, "api_calls": 1},
            required_keys=[
                "tech_stack",
                "modules",
                "database_schema",
                "openapi_spec",
                "deployment",
            ],
        )
        return {
            "state_updates": {"architecture": {"artifact_ref": "architecture:v1"}},
            "artifacts": [
                {
                    "store_key": "architecture",
                    "artifact": Artifact(
                        artifact_id="architecture-doc",
                        artifact_type="architecture",
                        producer=self.role,
                        content=architecture,
                        metadata={"generation": generation_meta},
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="backend_dev",
                    content="Architecture ready for backend implementation.",
                    msg_type=MessageType.TASK,
                    artifacts=["architecture-doc:v1"],
                )
            ],
            "usage": usage,
        }
