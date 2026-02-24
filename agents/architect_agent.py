"""Architect agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class ArchitectAgent(BaseAgent):
    """Generate architecture artifacts from requirements."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        architecture = {
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
            "usage": {"tokens": 520, "api_calls": 1},
        }
