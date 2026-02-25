"""DevOps agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import Artifact
from core.project_state import ProjectState

from .base_agent import BaseAgent


class DevOpsAgent(BaseAgent):
    """Generate deployment report artifact."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        fallback_deployment = {
            "status": "success",
            "mode": "local-simulated",
            "services": ["backend", "frontend", "postgres"],
            "health_checks": {"backend": 200, "frontend": 200},
            "access_urls": {"frontend": "http://localhost:3000", "backend": "http://localhost:8080"},
        }
        deployment, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                "Generate deployment report JSON for StayBooking run. "
                "Include status, mode, services, health_checks, and access_urls."
            ),
            fallback_payload=fallback_deployment,
            fallback_usage={"tokens": 390, "api_calls": 1},
            required_keys=[
                "status",
                "mode",
                "services",
                "health_checks",
                "access_urls",
            ],
        )
        return {
            "state_updates": {"deployment": {"artifact_ref": "deployment:v1"}},
            "artifacts": [
                {
                    "store_key": "deployment",
                    "artifact": Artifact(
                        artifact_id="deployment-report-auth",
                        artifact_type="deployment",
                        producer=self.role,
                        content=deployment,
                        metadata={"generation": generation_meta},
                    ),
                }
            ],
            "messages": [],
            "usage": usage,
            "stop": True,
        }
