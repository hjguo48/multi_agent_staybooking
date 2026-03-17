"""Architect agent implementation (rule-driven baseline)."""

from __future__ import annotations

import json
from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class ArchitectAgent(BaseAgent):
    """Generate architecture artifacts from requirements."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        proj = context.project_config or {}
        mod = context.module_config or {}

        project_name = proj.get("project_name", "Project")
        module_name = mod.get("module_name", "module")
        module_id = mod.get("module_id", "module")
        module_desc = mod.get("description", f"{module_name} implementation")

        be_cfg = proj.get("backend", {})
        fe_cfg = proj.get("frontend", {})
        base_url = be_cfg.get("base_url", "http://localhost:8080")

        # Fallback api_contract: empty endpoints — LLM designs them from requirements
        fallback_api_contract = {
            "base_url": base_url,
            "endpoints": [],
        }

        # --- Read from PM's requirements artifact (Option A: true content passing) ---
        req_art = context.get_latest_artifact("requirements")
        if req_art is not None and isinstance(req_art.content, dict):
            req_content = req_art.content
            pm_fr_raw = req_content.get("functional_requirements", [])
            pm_nfr_raw = req_content.get("non_functional_requirements", [])
            pm_api_hints = req_content.get("api_contracts", [])
            pm_data_model_raw = req_content.get("data_model", {})
        else:
            pm_fr_raw = mod.get("functional_requirements", [])
            pm_nfr_raw = mod.get("non_functional_requirements", [])
            pm_api_hints = []
            pm_data_model_raw = {}

        # Format functional requirements (PM may return structured dicts or plain strings)
        def _fmt_fr(fr: object) -> str:
            if isinstance(fr, str):
                return f"- {fr}"
            title = fr.get("title", fr.get("id", ""))
            desc = fr.get("description", fr.get("user_story", str(fr)))
            criteria = fr.get("acceptance_criteria", [])
            lines = [f"- {title}: {desc}"]
            for c in criteria[:3]:
                lines.append(f"  * {c}")
            return "\n".join(lines)

        fr_lines = (
            "\n".join(_fmt_fr(fr) for fr in pm_fr_raw)
            if pm_fr_raw else f"Implement the {module_name} module."
        )
        nfr_lines = "\n".join(
            f"- {nfr}" if isinstance(nfr, str) else f"- {nfr.get('description', str(nfr))}"
            for nfr in pm_nfr_raw
        )

        # Build database_schema from PM's data_model (entities with field context)
        if isinstance(pm_data_model_raw, list):
            pm_entities = pm_data_model_raw
        elif isinstance(pm_data_model_raw, dict):
            pm_entities = pm_data_model_raw.get("entities", [])
        else:
            pm_entities = []

        if pm_entities:
            db_tables = [
                {"name": ent.get("entity_name", ent.get("name", str(ent))) if isinstance(ent, dict) else str(ent)}
                for ent in pm_entities
            ]
        else:
            # Fall back to module_config entity names
            mod_entities = mod.get("data_model", {}).get("entities", [])
            db_tables = [
                {"name": ent.get("name", ent) if isinstance(ent, dict) else str(ent)}
                for ent in mod_entities
            ] if mod_entities else []

        # Optional PM api hints section for Architect context
        pm_api_section = ""
        if pm_api_hints:
            hint_paths = [
                h.get("path_pattern", h.get("path", ""))
                for h in pm_api_hints if isinstance(h, dict)
            ]
            hint_paths = [p for p in hint_paths if p]
            if hint_paths:
                pm_api_section = (
                    "\nPM REQUIREMENTS ANALYSIS — suggested endpoint patterns (for context; adapt freely):\n"
                    + "\n".join(f"  - {p}" for p in hint_paths)
                    + "\n"
                )

        # Build openapi_spec paths: starts empty; LLM will populate
        fallback_architecture = {
            "tech_stack": {
                "backend": {
                    "language": f"{be_cfg.get('language', 'Java')} {be_cfg.get('language_version', '')}".strip(),
                    "framework": f"{be_cfg.get('framework', 'Spring Boot')} {be_cfg.get('framework_version', '')}".strip(),
                },
                "frontend": {
                    "framework": f"{fe_cfg.get('framework', 'React')} {fe_cfg.get('framework_version', '')}".strip(),
                },
                "database": {"primary": "PostgreSQL"},
                "infrastructure": {"container": "Docker"},
            },
            "modules": [
                {
                    "name": f"{module_id}-module",
                    "responsibility": module_desc,
                    "dependencies": [],
                }
            ],
            "database_schema": {"tables": db_tables},
            "openapi_spec": {"paths": {}},
            "deployment": {
                "containers": proj.get("infrastructure", {}).get("services", ["backend", "frontend", "postgres"]),
                "networking": {"mode": "bridge"},
            },
            "api_contract": fallback_api_contract,
        }

        architecture, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                f"Generate architecture design JSON for {project_name} {module_name} scope.\n"
                f"Module description: {module_desc}\n"
                "\nFunctional requirements:\n"
                + fr_lines
                + ("\n\nNon-functional constraints:\n" + nfr_lines if nfr_lines else "")
                + (pm_api_section)
                + "\n\nInclude: tech_stack, modules, database_schema, openapi_spec, deployment, api_contract.\n"
                "\n"
                "IMPORTANT: You are the Architect. Design the api_contract endpoints from scratch "
                "based on the functional requirements above. Choose REST paths, HTTP methods, "
                "request/response fields, and auth requirements yourself.\n"
                "\n"
                "api_contract is a machine-readable endpoint list consumed by the frontend agent.\n"
                "It MUST follow this exact format:\n"
                "{\n"
                f'  "base_url": "{base_url}",\n'
                '  "endpoints": [\n'
                '    {\n'
                '      "method": "POST",\n'
                '      "path": "/your/designed/path",\n'
                '      "request_fields": ["field1", "field2"],\n'
                '      "response_fields": ["result_field"],\n'
                '      "auth_required": false,\n'
                '      "description": "What this endpoint does"\n'
                '    }\n'
                '  ]\n'
                "}\n"
                "The frontend agent will use api_contract to align its fetch() calls with the "
                "exact paths and field names the backend implements."
            ),
            fallback_payload=fallback_architecture,
            fallback_usage={"tokens": 520, "api_calls": 1},
            required_keys=[
                "tech_stack",
                "modules",
                "database_schema",
                "openapi_spec",
                "deployment",
                "api_contract",
            ],
            extra_output_constraints=[
                "- api_contract.endpoints must be a list with at least 1 entry.",
                "- Each endpoint must have: method, path, request_fields, response_fields, auth_required.",
                "- path values must start with '/' and match what the backend will actually implement.",
                "- Design endpoints to satisfy the functional requirements; do NOT copy pre-existing paths.",
            ],
        )

        # Extract api_contract; fall back to empty default if missing or malformed.
        raw_contract = architecture.get("api_contract", {})
        if not isinstance(raw_contract, dict) or "endpoints" not in raw_contract:
            raw_contract = fallback_api_contract
        api_contract = raw_contract

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
                },
                {
                    "store_key": "api_contract",
                    "artifact": Artifact(
                        artifact_id="api-contract-v1",
                        artifact_type="api_contract",
                        producer=self.role,
                        content=api_contract,
                        metadata={"generation": generation_meta},
                    ),
                },
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="backend_dev",
                    content=(
                        "Architecture and API contract ready. "
                        "Backend must implement the endpoints in api_contract exactly. "
                        "Frontend will align to the same contract."
                    ),
                    msg_type=MessageType.TASK,
                    artifacts=["architecture-doc:v1", "api-contract-v1"],
                )
            ],
            "usage": usage,
        }
