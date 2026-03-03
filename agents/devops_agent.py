"""DevOps agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import Artifact
from core.project_state import ProjectState

from .base_agent import BaseAgent


class DevOpsAgent(BaseAgent):
    """Generate deployment report artifact."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        proj = context.project_config or {}
        mod = context.module_config or {}

        module_id = mod.get("module_id", "module")
        be = proj.get("backend", {})
        fe = proj.get("frontend", {})
        infra = proj.get("infrastructure", {})

        project_name = proj.get("project_name", "Project")
        services = infra.get("services", ["backend", "frontend", "postgres"])

        default_health_urls = {
            "backend": be.get("base_url", "http://localhost:8080"),
            "frontend": f"http://localhost:{fe.get('dev_server_port', 3000)}",
        }
        health_urls = infra.get("health_check_urls", default_health_urls)

        # Build health_checks dict (service -> simulated HTTP status)
        health_checks = {svc: 200 for svc in health_urls}

        # Build access_urls from health_urls
        access_urls = dict(health_urls)

        fallback_deployment = {
            "status": "success",
            "mode": "local-simulated",
            "services": services,
            "health_checks": health_checks,
            "access_urls": access_urls,
        }
        deployment, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                f"Generate deployment report JSON for {project_name} run. "
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
                        artifact_id=f"deployment-report-{module_id}",
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
