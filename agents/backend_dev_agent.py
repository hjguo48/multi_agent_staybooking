"""Backend developer agent implementation (rule-driven baseline)."""

from __future__ import annotations

import copy
import json
from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


def _qa_rework_needed(context: ProjectState) -> bool:
    """Return True when QA has reported failures that require a rework pass."""
    qa_art = context.get_latest_artifact("qa_report")
    if qa_art is None or not isinstance(qa_art.content, dict):
        return False
    summary = qa_art.content.get("summary", {})
    if not isinstance(summary, dict):
        return False
    pass_rate = float(summary.get("test_pass_rate", 1.0))
    critical = int(summary.get("critical_bugs", 0))
    major = int(summary.get("major_bugs", 0))
    return pass_rate < 0.85 or critical > 0 or major > 0


def _build_backend_qa_feedback(context: ProjectState) -> str:
    """Format QA bug reports as a feedback section for the backend task instruction."""
    qa_art = context.get_latest_artifact("qa_report")
    if qa_art is None or not isinstance(qa_art.content, dict):
        return ""
    bug_reports = qa_art.content.get("bug_reports", [])
    if not isinstance(bug_reports, list) or not bug_reports:
        return ""
    # Prefer backend-relevant bugs; fall back to all bugs if none found
    backend_bugs = [
        b for b in bug_reports
        if isinstance(b, dict) and (
            "src/main/java" in str(b.get("file", ""))
            or str(b.get("file", "")).lower().endswith(".java")
        )
    ] or [b for b in bug_reports if isinstance(b, dict)]
    lines = [
        "\n*** REVISION MODE ***",
        "Your previous implementation had QA failures listed below.",
        "Return a COMPLETE updated code_bundle that fixes ALL issues.\n",
        "QA BUG REPORTS TO FIX:",
    ]
    for bug in backend_bugs:
        sev = bug.get("severity", "")
        f = bug.get("file", "")
        desc = bug.get("description", "")
        fix = bug.get("suggested_fix", "")
        lines.append(f"- [{sev}] {f}: {desc}")
        if fix:
            lines.append(f"  Fix: {fix}")
    return "\n".join(lines) + "\n"


class BackendDeveloperAgent(BaseAgent):
    """Generate backend code artifact for the current module."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        proj = context.project_config or {}
        mod = context.module_config or {}

        be = proj.get("backend", {})

        module_id = mod.get("module_id", "module")
        module_name = mod.get("module_name", module_id)
        pkg_root = be.get("root_package", "com.example")
        subpkg = module_id  # LLM chooses actual sub-package; this is just a default hint
        deps_str = "\n  - ".join(be.get("dependencies", []))
        min_files, max_files = 4, 6

        # Functional requirements from module config (plain strings)
        fr_raw = mod.get("functional_requirements", [])
        fr_lines = "\n".join(
            f"- {fr}" if isinstance(fr, str) else f"- {fr.get('user_story', str(fr))}"
            for fr in fr_raw
        ) if fr_raw else f"Implement the {module_name} module."

        latest_backend_artifact = context.get_latest_artifact("backend_code")
        if latest_backend_artifact is not None:
            cached_module = (
                latest_backend_artifact.content.get("module", "")
                if isinstance(latest_backend_artifact.content, dict)
                else ""
            )
            generation = latest_backend_artifact.metadata.get("generation", {})
            if (
                isinstance(generation, dict)
                and generation.get("source") == "llm"
                and cached_module == module_id
                and not _qa_rework_needed(context)
            ):
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
                                artifact_id=f"backend-{module_id}-module",
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
                            content=f"Backend {module_name} module ready for frontend integration.",
                            msg_type=MessageType.TASK,
                            artifacts=[f"backend-{module_id}-module:v1"],
                        )
                    ],
                    "usage": {"tokens": 0, "api_calls": 0},
                }

        pkg_path = pkg_root.replace(".", "/")
        fallback_file_key = (
            f"{be.get('src_root', 'src/main/java')}/{pkg_path}/{subpkg}/ModuleException.java"
        )
        fallback_code_bundle = {
            fallback_file_key: (
                f"package {pkg_root}.{subpkg};\n"
                "\n"
                "public class ModuleException extends RuntimeException {\n"
                "    public ModuleException(String message) {\n"
                "        super(message);\n"
                "    }\n"
                "}\n"
            )
        }
        fallback_backend_artifact = {
            "module": module_id,
            "changed_files": list(fallback_code_bundle.keys()),
            "code_bundle": fallback_code_bundle,
            "build_notes": {"compile_status": "simulated_pass"},
            "test_notes": {"unit_tests": "simulated_pending"},
        }

        # Inject architecture and api_contract from upstream agents into the prompt.
        api_contract_art = context.get_latest_artifact("api_contract")
        api_contract = api_contract_art.content if api_contract_art is not None else {}
        endpoints = api_contract.get("endpoints", [])
        api_section = (
            "\nAPI CONTRACT FROM ARCHITECT (implement these exact endpoints):\n"
            + json.dumps(endpoints, indent=2)
            + "\n"
            if endpoints
            else "\n(No API contract yet — infer endpoints from functional requirements and architecture.)\n"
        )

        arch = context.architecture or {}
        db_schema = arch.get("database_schema", {})
        arch_section = (
            "\nDATABASE SCHEMA FROM ARCHITECT:\n"
            + json.dumps(db_schema, indent=2)
            + "\n"
            if db_schema
            else ""
        )

        src_root = be.get("src_root", "src/main/java")
        framework_line = (
            f"{be.get('framework', 'Spring Boot')} {be.get('framework_version', '')}, "
            f"{be.get('build_tool', 'Gradle')}, "
            f"{be.get('language', 'Java')} {be.get('language_version', '')}"
        ).strip(", ")

        qa_feedback_section = _build_backend_qa_feedback(context) if _qa_rework_needed(context) else ""

        backend_artifact, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                f"Generate a backend {module_id} module code_bundle JSON for the "
                f"{proj.get('project_name', 'project')} project using scaffold-overlay mode.\n"
                + qa_feedback_section
                + "\n"
                "SCAFFOLD CONTEXT:\n"
                f"- {framework_line}\n"
                f"- Root package: {pkg_root} ({be.get('main_class', 'Application')}.java already exists there)\n"
                f"- Available dependencies:\n  - {deps_str}\n"
                "- NO existing entity, repository, service, or controller classes — design everything from scratch.\n"
                + api_section
                + arch_section
                + "\n"
                "FUNCTIONAL REQUIREMENTS:\n"
                + fr_lines
                + "\n"
                "\n"
                "YOUR DESIGN DECISIONS:\n"
                f"- Choose sub-package names under {pkg_root} (suggested: {pkg_root}.{subpkg})\n"
                "- Choose entity field names, DTO structure, exception names\n"
                "- Choose JWT implementation approach (key format, claims, expiry) if applicable\n"
                "- Choose Spring Security filter/configuration approach if applicable\n"
                "\n"
                "FILE RULES:\n"
                f"- Generate {min_files}-{max_files} Java files; every file you reference must be in code_bundle\n"
                f"- Every file MUST start with: package {pkg_root}.<subpackage>;\n"
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
                f"- Generate {min_files}-{max_files} files; limit changed_files accordingly.",
                "- code_bundle keys must exactly match changed_files.",
                f"- Every file path must be under {src_root}/{pkg_path}/<subpackage>/.",
                f"- Every Java file MUST begin with 'package {pkg_root}.<subpackage>;'.",
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
                        artifact_id=f"backend-{module_id}-module",
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
                    content=f"Backend {module_name} module ready for frontend integration.",
                    msg_type=MessageType.TASK,
                    artifacts=[f"backend-{module_id}-module:v1"],
                )
            ],
            "usage": usage,
        }
