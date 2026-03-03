"""Architect agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent

_FALLBACK_API_CONTRACT = {
    "base_url": "http://localhost:8080",
    "endpoints": [
        {
            "method": "POST",
            "path": "/authenticate/register",
            "request_fields": ["username", "password", "role"],
            "response_fields": ["message"],
            "auth_required": False,
            "description": "Register a new user (role: GUEST or HOST)",
        },
        {
            "method": "POST",
            "path": "/authenticate/login",
            "request_fields": ["username", "password"],
            "response_fields": ["token"],
            "auth_required": False,
            "description": "Authenticate and return a signed JWT token",
        },
    ],
}


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
                "tables": [{"name": "users", "columns": ["id", "username", "password_hash", "role"]}]
            },
            "openapi_spec": {
                "paths": {
                    "/authenticate/register": {"post": {"summary": "Register user"}},
                    "/authenticate/login": {"post": {"summary": "Login user"}},
                }
            },
            "deployment": {
                "containers": ["backend", "frontend", "postgres"],
                "networking": {"mode": "bridge"},
            },
            "api_contract": _FALLBACK_API_CONTRACT,
        }
        architecture, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                "Generate architecture design JSON for StayBooking auth-first scope.\n"
                "Include: tech_stack, modules, database_schema, openapi_spec, deployment, api_contract.\n"
                "\n"
                "api_contract is a machine-readable endpoint list consumed by the frontend agent.\n"
                "It MUST follow this exact format:\n"
                "{\n"
                '  "base_url": "http://localhost:8080",\n'
                '  "endpoints": [\n'
                "    {\n"
                '      "method": "POST",\n'
                '      "path": "/authenticate/register",\n'
                '      "request_fields": ["username", "password", "role"],\n'
                '      "response_fields": ["message"],\n'
                '      "auth_required": false,\n'
                '      "description": "Register a new user"\n'
                "    },\n"
                "    {\n"
                '      "method": "POST",\n'
                '      "path": "/authenticate/login",\n'
                '      "request_fields": ["username", "password"],\n'
                '      "response_fields": ["token"],\n'
                '      "auth_required": false,\n'
                '      "description": "Authenticate and return JWT"\n'
                "    }\n"
                "  ]\n"
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
                "- api_contract.endpoints must be a list with at least 2 entries.",
                "- Each endpoint must have: method, path, request_fields, response_fields, auth_required.",
                "- path values must start with '/' and match what the backend will actually implement.",
            ],
        )

        # Extract api_contract; fall back to hardcoded default if missing or malformed.
        raw_contract = architecture.get("api_contract", {})
        if not isinstance(raw_contract, dict) or "endpoints" not in raw_contract:
            raw_contract = _FALLBACK_API_CONTRACT
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
