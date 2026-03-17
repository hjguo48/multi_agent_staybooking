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

    def act_qa_verdict(self, context: ProjectState) -> dict[str, Any]:
        """Called when QA rework iteration cap is reached.

        PM reviews the final QA report and iteration history, then emits a
        structured pass/fail verdict that is stored as a ``pm_qa_verdict``
        artifact.  The verdict does NOT stop the pipeline — DevOps still runs
        afterward — but it is recorded in state for research metrics.
        """
        mod = context.module_config or {}
        module_id = mod.get("module_id", "module")
        module_name = mod.get("module_name", module_id)

        qa_art = context.get_latest_artifact("qa_report")
        qa_summary: dict[str, Any] = {}
        bug_reports: list[Any] = []
        if qa_art is not None and isinstance(qa_art.content, dict):
            qa_summary = qa_art.content.get("summary", {}) or {}
            bug_reports = qa_art.content.get("bug_reports", []) or []

        pass_rate = float(qa_summary.get("test_pass_rate", 0.0))
        critical = int(qa_summary.get("critical_bugs", 0))
        major = int(qa_summary.get("major_bugs", 0))
        iterations_used = context.iteration

        # Rule-based fallback verdict (used when LLM is unavailable)
        if critical > 0:
            fallback_decision = "reject"
            fallback_reason = f"critical_bugs={critical} remain after {iterations_used} rework rounds"
        elif major > 2:
            fallback_decision = "reject"
            fallback_reason = f"major_bugs={major} exceed threshold after {iterations_used} rework rounds"
        elif pass_rate >= 0.85:
            fallback_decision = "accept"
            fallback_reason = f"pass_rate={pass_rate:.2f} meets threshold; proceeding to deployment"
        else:
            fallback_decision = "accept_with_warnings"
            fallback_reason = (
                f"pass_rate={pass_rate:.2f} below ideal but no critical bugs; "
                f"accepting after {iterations_used} rework rounds"
            )

        fallback_verdict = {
            "decision": fallback_decision,
            "reason": fallback_reason,
            "iterations_used": iterations_used,
            "qa_summary": qa_summary,
            "module_id": module_id,
        }

        bug_summary = "\n".join(
            f"- [{b.get('severity','?')}] {b.get('file','?')}: {b.get('description','')}"
            for b in bug_reports[:5]
            if isinstance(b, dict)
        ) or "(no bug reports)"

        verdict, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                f"As PM, make a final pass/fail decision for the {module_name} module "
                f"after {iterations_used} QA rework round(s).\n"
                "\nFINAL QA REPORT SUMMARY:\n"
                f"  test_pass_rate: {pass_rate}\n"
                f"  critical_bugs:  {critical}\n"
                f"  major_bugs:     {major}\n"
                "\nREMAINING BUGS:\n"
                + bug_summary
                + "\n\n"
                "Return a verdict JSON with:\n"
                '- decision: "accept", "accept_with_warnings", or "reject"\n'
                "- reason: one-sentence justification\n"
                f"- iterations_used: {iterations_used}\n"
                "- qa_summary: the qa summary object above\n"
                f'- module_id: "{module_id}"\n'
                "\nRules:\n"
                "- reject if critical_bugs > 0\n"
                "- reject if major_bugs > 2 AND pass_rate < 0.7\n"
                "- accept_with_warnings if pass_rate >= 0.7 but < 0.85\n"
                "- accept if pass_rate >= 0.85 and critical_bugs == 0"
            ),
            fallback_payload=fallback_verdict,
            fallback_usage={"tokens": 300, "api_calls": 1},
            required_keys=["decision", "reason", "iterations_used"],
            extra_output_constraints=[
                '- decision must be one of: "accept", "accept_with_warnings", "reject".',
                "- Return JSON only.",
            ],
            max_output_tokens_override=400,
        )

        artifact = Artifact(
            artifact_id=f"pm-qa-verdict-{module_id}",
            artifact_type="pm_qa_verdict",
            producer=self.role,
            content=verdict,
            metadata={"generation": generation_meta},
        )
        context.register_artifact("pm_qa_verdict", artifact)

        decision = str(verdict.get("decision", "unknown"))
        context.add_message(
            AgentMessage(
                sender=self.role,
                receiver="devops",
                content=f"PM QA verdict for {module_name}: {decision}. {verdict.get('reason', '')}",
                msg_type=MessageType.APPROVAL if decision != "reject" else MessageType.FEEDBACK,
                artifacts=[f"pm-qa-verdict-{module_id}:v1"],
            )
        )

        return {"verdict": verdict, "usage": usage}
