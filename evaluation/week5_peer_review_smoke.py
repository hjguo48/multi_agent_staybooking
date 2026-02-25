#!/usr/bin/env python3
"""Week 5 smoke run for Peer Review topology."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week5"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents import (
    ArchitectAgent,
    BackendDeveloperAgent,
    DevOpsAgent,
    FrontendDeveloperAgent,
    PeerReviewerAgent,
    ProductManagerAgent,
    QAAgent,
)
from core.models import MessageType, ReviewStatus
from core.orchestrator import Orchestrator
from topologies.peer_review import PeerReviewTopology


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_smoke() -> tuple[int, list[CheckResult], Path, Path]:
    orchestrator = Orchestrator()
    orchestrator.register_agent(ProductManagerAgent("pm", "pm prompt", []))
    orchestrator.register_agent(ArchitectAgent("architect", "architect prompt", []))
    orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend prompt", []))
    orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend prompt", []))
    orchestrator.register_agent(PeerReviewerAgent("reviewer", "reviewer prompt", []))
    orchestrator.register_agent(QAAgent("qa", "qa prompt", []))
    orchestrator.register_agent(DevOpsAgent("devops", "devops prompt", []))

    topology = PeerReviewTopology(orchestrator=orchestrator, max_revisions_per_target=1)
    turn_results = topology.run("Build auth module with peer-review gates.")
    state = orchestrator.state

    state_path = OUTPUT_DIR / "week5_peer_review_state.json"
    report_path = OUTPUT_DIR / "week5_peer_review_report.json"
    state.save_json(state_path)

    backend_artifact = state.get_latest_artifact("backend_code")
    frontend_artifact = state.get_latest_artifact("frontend_code")
    deployment_artifact = state.get_latest_artifact("deployment")
    review_messages = [
        message
        for message in state.message_log.messages
        if message.msg_type == MessageType.REVIEW
    ]
    reviewer_turns = [result for result in turn_results if result.agent_role == "reviewer"]
    revision_turns = [result for result in reviewer_turns if not result.success]
    approved_turns = [result for result in reviewer_turns if result.success]

    checks = [
        CheckResult(
            name="turn_count",
            passed=len(turn_results) == 12,
            details=f"turn_count={len(turn_results)}",
        ),
        CheckResult(
            name="review_loops_executed",
            passed=len(review_messages) >= 4 and len(reviewer_turns) >= 4,
            details=(
                f"review_messages={len(review_messages)}, "
                f"reviewer_turns={len(reviewer_turns)}"
            ),
        ),
        CheckResult(
            name="bounded_revision_behavior",
            passed=len(revision_turns) == 2 and len(approved_turns) == 2,
            details=(
                f"revision_turns={len(revision_turns)}, "
                f"approved_turns={len(approved_turns)}"
            ),
        ),
        CheckResult(
            name="artifact_versions_incremented",
            passed=(
                backend_artifact is not None
                and backend_artifact.version == 2
                and frontend_artifact is not None
                and frontend_artifact.version == 2
            ),
            details=(
                "backend_v="
                f"{backend_artifact.version if backend_artifact else 'None'}, "
                "frontend_v="
                f"{frontend_artifact.version if frontend_artifact else 'None'}"
            ),
        ),
        CheckResult(
            name="deployment_success",
            passed=(
                deployment_artifact is not None
                and deployment_artifact.content.get("status") == "success"
            ),
            details=(
                "deployment_status="
                f"{deployment_artifact.content.get('status') if deployment_artifact else 'None'}"
            ),
        ),
        CheckResult(
            name="usage_counters_accumulated",
            passed=state.total_tokens == 4380 and state.total_api_calls == 8,
            details=f"tokens={state.total_tokens}, api_calls={state.total_api_calls}",
        ),
        CheckResult(
            name="iteration_counter_for_revisions",
            passed=state.iteration == 2,
            details=f"iteration={state.iteration}",
        ),
    ]

    status = "success" if all(item.passed for item in checks) else "failed"
    write_json(
        report_path,
        {
            "status": status,
            "checks": [asdict(item) for item in checks],
            "turn_results": [asdict(result) for result in turn_results],
            "state_snapshot": str(state_path),
        },
    )
    return (0 if status == "success" else 1), checks, state_path, report_path


def main() -> int:
    code, checks, state_path, report_path = run_smoke()
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.details}")
    print(f"State snapshot: {state_path}")
    print(f"Report: {report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
