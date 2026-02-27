"""Backend developer agent implementation (rule-driven baseline)."""

from __future__ import annotations

import copy
from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class BackendDeveloperAgent(BaseAgent):
    """Generate backend code artifact for auth module."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        latest_backend_artifact = context.get_latest_artifact("backend_code")
        if latest_backend_artifact is not None:
            generation = latest_backend_artifact.metadata.get("generation", {})
            if isinstance(generation, dict) and generation.get("source") == "llm":
                cached_content = (
                    copy.deepcopy(latest_backend_artifact.content)
                    if isinstance(latest_backend_artifact.content, dict)
                    else {}
                )
                return {
                    "state_updates": {"backend_code": {"artifact_ref": "backend_code:v1"}},
                    "artifacts": [
                        {
                            "store_key": "backend_code",
                            "artifact": Artifact(
                                artifact_id="backend-auth-module",
                                artifact_type="backend_code",
                                producer=self.role,
                                content=cached_content,
                                metadata={
                                    "generation": {
                                        "source": "llm",
                                        "provider": generation.get("provider", ""),
                                        "model": generation.get("model", ""),
                                        "cached_from_version": latest_backend_artifact.version,
                                    }
                                },
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
                    "usage": {"tokens": 0, "api_calls": 0},
                }

        fallback_code_bundle = {
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
        fallback_backend_artifact = {
            "module": "auth",
            "changed_files": list(fallback_code_bundle.keys()),
            "code_bundle": fallback_code_bundle,
            "build_notes": {"compile_status": "simulated_pass"},
            "test_notes": {"unit_tests": "simulated_pending"},
        }
        backend_artifact, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                "Generate a minimal backend code artifact JSON for StayBooking auth module. "
                "Return concise Java/Spring-compatible stubs suitable for landing validation."
            ),
            fallback_payload=fallback_backend_artifact,
            fallback_usage={"tokens": 680, "api_calls": 1},
            required_keys=[
                "module",
                "changed_files",
                "code_bundle",
                "build_notes",
                "test_notes",
            ],
            extra_output_constraints=[
                "- Limit changed_files to at most 3 files.",
                "- code_bundle keys must exactly match changed_files.",
                "- Keep each file concise (<= 120 lines).",
                "- Avoid markdown and explanations; JSON data only.",
            ],
            retry_on_invalid_json=True,
            max_output_tokens_override=1800,
        )
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
                        metadata={"generation": generation_meta},
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
            "usage": usage,
        }
