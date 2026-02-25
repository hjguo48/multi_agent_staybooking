"""Frontend developer agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class FrontendDeveloperAgent(BaseAgent):
    """Generate frontend code artifact for auth flows."""

    def act(self, context: ProjectState) -> dict[str, Any]:
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
                "Generate frontend code artifact JSON for StayBooking auth pages. "
                "Include changed files, code bundle strings, build notes, and UI notes."
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
