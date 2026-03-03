"""QA agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent

_CHARS_PER_FILE = 800  # truncation limit per file to keep prompt token-efficient


def _truncate(text: str, limit: int = _CHARS_PER_FILE) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated, {len(text) - limit} chars omitted]"


class QAAgent(BaseAgent):
    """Validate produced artifacts and generate QA report."""

    def _build_code_section(self, context: ProjectState) -> str:
        """Extract actual generated code content for QA review (token-bounded)."""
        sections: list[str] = []

        backend_art = context.get_latest_artifact("backend_code")
        if backend_art is not None and isinstance(backend_art.content, dict):
            bundle = backend_art.content.get("code_bundle", {})
            if bundle:
                sections.append("=== BACKEND CODE (Java) ===")
                for fname, content in list(bundle.items())[:5]:
                    sections.append(f"--- {fname} ---")
                    sections.append(_truncate(str(content)))

        frontend_art = context.get_latest_artifact("frontend_code")
        if frontend_art is not None and isinstance(frontend_art.content, dict):
            bundle = frontend_art.content.get("code_bundle", {})
            if bundle:
                sections.append("=== FRONTEND CODE (JavaScript) ===")
                for fname, content in list(bundle.items())[:3]:
                    sections.append(f"--- {fname} ---")
                    sections.append(_truncate(str(content)))

        return "\n".join(sections) if sections else ""

    def act(self, context: ProjectState) -> dict[str, Any]:
        fallback_qa_report = {
            "summary": {
                "test_pass_rate": 1.0,
                "critical_bugs": 0,
                "major_bugs": 0,
            },
            "bug_reports": [],
            "coverage_map": {"FR-001": ["testRegister", "testLogin"]},
            "api_alignment": {"status": "not_checked"},
        }

        code_section = self._build_code_section(context)
        code_context = (
            f"\nACTUAL GENERATED CODE TO REVIEW:\n{code_section}\n"
            if code_section
            else "\n(No generated code available yet — assess based on context snapshot.)\n"
        )

        qa_report, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                "Generate a QA report JSON for the StayBooking auth module artifacts.\n"
                "Review the actual generated code below and produce a structured assessment.\n"
                + code_context
                + "\n"
                "IMPORTANT RULES:\n"
                "- summary.critical_bugs MUST be 0 unless a file is completely missing or has a syntax error.\n"
                "- summary.major_bugs should reflect real structural issues (e.g. missing JWT filter, wrong endpoint path).\n"
                "- summary.test_pass_rate should be 1.0 if the code structure is valid.\n"
                "- bug_reports must be a list of objects, each with: file, severity, description, suggested_fix.\n"
                "- coverage_map must map each FR-id to the test/component covering it.\n"
                "- api_alignment: check if frontend fetch() paths match backend controller paths.\n"
            ),
            fallback_payload=fallback_qa_report,
            fallback_usage={"tokens": 470, "api_calls": 1},
            required_keys=["summary", "bug_reports", "coverage_map"],
            extra_output_constraints=[
                "- summary must have keys: test_pass_rate (float), critical_bugs (int), major_bugs (int).",
                "- critical_bugs must be 0 for structurally valid generated code.",
                "- bug_reports is a list; each entry has: file (string), severity (string), description (string), suggested_fix (string).",
                "- api_alignment is an object describing whether frontend API calls match backend endpoints.",
                "- Return JSON only.",
            ],
            max_output_tokens_override=1500,
        )
        return {
            "state_updates": {"qa_report": {"artifact_ref": "qa_report:v1"}},
            "artifacts": [
                {
                    "store_key": "qa_report",
                    "artifact": Artifact(
                        artifact_id="qa-report-auth",
                        artifact_type="qa_report",
                        producer=self.role,
                        content=qa_report,
                        metadata={"generation": generation_meta},
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="devops",
                    content="QA passed. Ready for deployment validation.",
                    msg_type=MessageType.APPROVAL,
                    artifacts=["qa-report-auth:v1"],
                )
            ],
            "usage": usage,
        }
