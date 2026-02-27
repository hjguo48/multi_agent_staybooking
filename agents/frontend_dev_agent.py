"""Frontend developer agent implementation (rule-driven baseline)."""

from __future__ import annotations

import copy
from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class FrontendDeveloperAgent(BaseAgent):
    """Generate frontend code artifact for auth flows."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        latest_frontend_artifact = context.get_latest_artifact("frontend_code")
        if latest_frontend_artifact is not None:
            generation = latest_frontend_artifact.metadata.get("generation", {})
            if isinstance(generation, dict) and generation.get("source") == "llm":
                cached_content = (
                    copy.deepcopy(latest_frontend_artifact.content)
                    if isinstance(latest_frontend_artifact.content, dict)
                    else {}
                )
                return {
                    "state_updates": {"frontend_code": {"artifact_ref": "frontend_code:v1"}},
                    "artifacts": [
                        {
                            "store_key": "frontend_code",
                            "artifact": Artifact(
                                artifact_id="frontend-auth-module",
                                artifact_type="frontend_code",
                                producer=self.role,
                                content=cached_content,
                                metadata={
                                    "generation": {
                                        "source": "llm",
                                        "provider": generation.get("provider", ""),
                                        "model": generation.get("model", ""),
                                        "cached_from_version": latest_frontend_artifact.version,
                                    }
                                },
                            ),
                        }
                    ],
                    "messages": [
                        AgentMessage(
                            sender=self.role,
                            receiver="qa",
                            content="Frontend auth module ready for QA validation.",
                            msg_type=MessageType.TASK,
                            artifacts=["frontend-auth-module:v1"],
                        )
                    ],
                    "usage": {"tokens": 0, "api_calls": 0},
                }

        fallback_code_bundle = {
            "src/pages/LoginPage.jsx": (
                "export function LoginPage() {\n"
                "  return <div>Login Page Placeholder</div>;\n"
                "}\n"
            ),
            "src/services/authApi.js": (
                "export async function login(payload) {\n"
                "  return { token: 'mock-token', user: payload.username };\n"
                "}\n"
            ),
        }
        fallback_frontend_artifact = {
            "module": "auth",
            "changed_files": list(fallback_code_bundle.keys()),
            "code_bundle": fallback_code_bundle,
            "build_notes": {"build_status": "simulated_pass"},
            "ui_state_notes": {"loading_error_empty": "covered_in_placeholder"},
        }
        frontend_artifact, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                "Generate a minimal frontend code artifact JSON for StayBooking auth pages. "
                "Return concise React-compatible stubs suitable for landing validation."
            ),
            fallback_payload=fallback_frontend_artifact,
            fallback_usage={"tokens": 610, "api_calls": 1},
            required_keys=[
                "module",
                "changed_files",
                "code_bundle",
                "build_notes",
                "ui_state_notes",
            ],
            extra_output_constraints=[
                "- Limit changed_files to at most 2 files.",
                "- code_bundle keys must exactly match changed_files.",
                "- Keep each file concise (<= 40 lines).",
                "- Avoid markdown and explanations; JSON data only.",
            ],
            retry_on_invalid_json=True,
            json_retry_attempts=3,
            max_output_tokens_override=900,
        )
        return {
            "state_updates": {"frontend_code": {"artifact_ref": "frontend_code:v1"}},
            "artifacts": [
                {
                    "store_key": "frontend_code",
                    "artifact": Artifact(
                        artifact_id="frontend-auth-module",
                        artifact_type="frontend_code",
                        producer=self.role,
                        content=frontend_artifact,
                        metadata={"generation": generation_meta},
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="qa",
                    content="Frontend auth module ready for QA validation.",
                    msg_type=MessageType.TASK,
                    artifacts=["frontend-auth-module:v1"],
                )
            ],
            "usage": usage,
        }
