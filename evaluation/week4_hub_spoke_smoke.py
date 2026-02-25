#!/usr/bin/env python3
"""Week 4 smoke run for Hub-and-Spoke topology."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week4"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents import (
    ArchitectAgent,
    BackendDeveloperAgent,
    CoordinatorAgent,
    DevOpsAgent,
    FrontendDeveloperAgent,
    ProductManagerAgent,
    QAAgent,
)
from core.models import MessageType
from core.orchestrator import Orchestrator
from topologies.hub_spoke import DEFAULT_HUB_SPOKE_ROLES, HubAndSpokeTopology


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
    orchestrator.register_agent(CoordinatorAgent("coordinator", "coordinator prompt", []))
    orchestrator.register_agent(ProductManagerAgent("pm", "pm prompt", []))
    orchestrator.register_agent(ArchitectAgent("architect", "architect prompt", []))
    orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend prompt", []))
    orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend prompt", []))
    orchestrator.register_agent(QAAgent("qa", "qa prompt", []))
    orchestrator.register_agent(DevOpsAgent("devops", "devops prompt", []))

    topology = HubAndSpokeTopology(orchestrator=orchestrator)
    turn_results = topology.run("Build auth module through coordinator-mediated routing.")
    state = orchestrator.state

    state_path = OUTPUT_DIR / "week4_hub_spoke_state.json"
    report_path = OUTPUT_DIR / "week4_hub_spoke_report.json"
    state.save_json(state_path)

    deployment_artifact = state.get_latest_artifact("deployment")
    coordinator_turns = [result for result in turn_results if result.agent_role == "coordinator"]
    spoke_turns = [result for result in turn_results if result.agent_role != "coordinator"]
    spoke_order = [result.agent_role for result in spoke_turns]
    coordinator_task_messages = [
        message
        for message in state.message_log.messages
        if message.sender == "coordinator"
        and message.msg_type == MessageType.TASK
        and message.receiver in DEFAULT_HUB_SPOKE_ROLES
    ]

    checks = [
        CheckResult(
            name="turn_count",
            passed=len(turn_results) == 12,
            details=f"turn_count={len(turn_results)}",
        ),
        CheckResult(
            name="turn_pattern",
            passed=(
                len(coordinator_turns) == 6
                and len(spoke_turns) == 6
                and spoke_order == DEFAULT_HUB_SPOKE_ROLES
            ),
            details=(
                f"coordinator_turns={len(coordinator_turns)}, "
                f"spoke_order={spoke_order}"
            ),
        ),
        CheckResult(
            name="all_turns_success",
            passed=all(result.success for result in turn_results),
            details="all turn results should be success",
        ),
        CheckResult(
            name="coordinator_routing_messages",
            passed=len(coordinator_task_messages) == 6,
            details=f"coordinator_task_messages={len(coordinator_task_messages)}",
        ),
        CheckResult(
            name="state_fields_populated",
            passed=all(
                [
                    state.requirements is not None,
                    state.architecture is not None,
                    state.backend_code is not None,
                    state.frontend_code is not None,
                    state.qa_report is not None,
                    state.deployment is not None,
                ]
            ),
            details="all lifecycle state fields populated",
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
            passed=state.total_tokens == 4170 and state.total_api_calls == 12,
            details=f"tokens={state.total_tokens}, api_calls={state.total_api_calls}",
        ),
        CheckResult(
            name="iteration_counter",
            passed=state.iteration == 6,
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
