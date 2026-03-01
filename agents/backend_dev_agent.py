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
            "src/main/java/com/staybooking/auth/UserAlreadyExistsException.java": (
                "package com.staybooking.auth;\n"
                "\n"
                "public class UserAlreadyExistsException extends RuntimeException {\n"
                "    public UserAlreadyExistsException(String username) {\n"
                "        super(\"User already exists: \" + username);\n"
                "    }\n"
                "}\n"
            )
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
                "Generate a backend auth module code_bundle JSON for the StayBooking project using scaffold-overlay mode.\n"
                "\n"
                "SCAFFOLD CONTEXT:\n"
                "- Spring Boot 3.4.1, Gradle, Java 17\n"
                "- Root package: com.staybooking (StaybookingApplication.java already exists there)\n"
                "- Available dependencies: spring-boot-starter-web, spring-boot-starter-data-jpa,\n"
                "  spring-boot-starter-security, jjwt-api:0.11.5 (+jjwt-impl +jjwt-jackson), postgresql\n"
                "- NO existing entity, repository, service, or controller classes — design everything from scratch.\n"
                "\n"
                "FUNCTIONAL REQUIREMENTS:\n"
                "- POST /authenticate/register — register user with BCrypt-hashed password\n"
                "- POST /authenticate/login — validate credentials, return signed JWT\n"
                "- Spring Security config: disable CSRF, permit /authenticate/**, require auth elsewhere\n"
                "- Implement UserDetailsService loading from JPA repository\n"
                "\n"
                "YOUR DESIGN DECISIONS:\n"
                "- Choose sub-package names under com.staybooking (e.g., com.staybooking.auth, com.staybooking.model)\n"
                "- Choose entity field names, DTO structure, exception names\n"
                "- Choose JWT implementation approach (key format, claims, expiry)\n"
                "\n"
                "FILE RULES:\n"
                "- Generate 4-6 Java files; every file you reference must be in code_bundle\n"
                "- Every file MUST start with: package com.staybooking.<subpackage>;\n"
                "- Every file MUST include all necessary import statements\n"
                "- Every referenced class must be defined in the bundle OR be a standard Spring/Java library class\n"
                "- Use constructor injection only (NO @Autowired field injection)\n"
                "- Do NOT add new Gradle dependencies\n"
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
                "- Generate 4-6 files; limit changed_files accordingly.",
                "- code_bundle keys must exactly match changed_files.",
                "- Every file path must be under src/main/java/com/staybooking/<subpackage>/.",
                "- Every Java file MUST begin with 'package com.staybooking.<subpackage>;'.",
                "- Every Java file MUST include complete import statements before the class declaration.",
                "- Every class referenced must be defined in the bundle OR imported from Spring/Java stdlib.",
                "- Do NOT use field injection (@Autowired on fields); use constructor injection only.",
                "- Do NOT add new Gradle dependencies.",
                "- Return JSON only, no markdown fences or explanations.",
            ],
            retry_on_invalid_json=True,
            json_retry_attempts=2,
            max_output_tokens_override=6000,
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
