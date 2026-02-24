"""Backend developer agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class BackendDeveloperAgent(BaseAgent):
    """Generate backend code artifact for auth module."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        code_bundle = {
            "src/main/java/com/example/auth/AuthController.java": (
                "package com.example.auth;\n"
                "public class AuthController {\n"
                "    // Minimal placeholder controller for week3 smoke\n"
                "}\n"
            ),
            "src/main/java/com/example/auth/AuthService.java": (
                "package com.example.auth;\n"
                "public class AuthService {\n"
                "    // Minimal placeholder service for week3 smoke\n"
                "}\n"
            ),
        }
        backend_artifact = {
            "module": "auth",
            "changed_files": list(code_bundle.keys()),
            "code_bundle": code_bundle,
            "build_notes": {"compile_status": "simulated_pass"},
            "test_notes": {"unit_tests": "simulated_pending"},
        }
        return {
            "state_updates": {"backend_code": {"artifact_ref": "backend_code:v1"}},
            "artifacts": [
                {
                    "store_key": "backend_code",
                    "artifact": Artifact(
                        artifact_id="backend-auth-module",
                        artifact_type="backend_code",
                        producer=self.role,
                        content=backend_artifact,
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="frontend_dev",
                    content="Backend auth module ready for frontend integration.",
                    msg_type=MessageType.TASK,
                    artifacts=["backend-auth-module:v1"],
                )
            ],
            "usage": {"tokens": 680, "api_calls": 1},
        }
