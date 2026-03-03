"""Product Manager agent implementation (rule-driven baseline)."""

from __future__ import annotations

import json
from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class ProductManagerAgent(BaseAgent):
    """Generate structured requirements from a project brief."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        proj = context.project_config or {}
        mod = context.module_config or {}

        project_name = proj.get("project_name", "Project")
        module_name = mod.get("module_name", "module")
        module_desc = mod.get("description", f"{module_name} module")

        # functional_requirements: now a list of plain user-story strings
        fr_raw = mod.get("functional_requirements", [])
        fr_list = [
            fr if isinstance(fr, str) else fr.get("user_story", str(fr))
            for fr in fr_raw
        ] or [f"Implement the {module_name} module."]

        nfr_raw = mod.get("non_functional_requirements", [])
        nfr_list = [
            nfr if isinstance(nfr, str) else nfr.get("description", str(nfr))
            for nfr in nfr_raw
        ]

        fr_text = "\n".join(f"- {fr}" for fr in fr_list)
        nfr_text = "\n".join(f"- {nfr}" for nfr in nfr_list)

        # Fallback: api_contracts and data_model are left empty — Architect designs them
        fallback_requirements = {
            "project_name": project_name,
            "functional_requirements": fr_list,
            "non_functional_requirements": nfr_list,
            "api_contracts": [],
            "data_model": {"entities": [], "relationships": []},
        }

        requirements, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                f"Generate requirements for the {module_name} module of {project_name}.\n"
                f"Module description: {module_desc}\n"
                "\nFunctional requirements from product brief:\n"
                + fr_text
                + ("\n\nNon-functional constraints:\n" + nfr_text if nfr_text else "")
                + "\n\nProduce a requirements document with: functional_requirements, "
                "non_functional_requirements, api_contracts (derive from requirements — do NOT "
                "copy pre-defined endpoints), and data_model (identify entities from requirements). "
                "The Architect will design the actual API endpoints and database schema."
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
