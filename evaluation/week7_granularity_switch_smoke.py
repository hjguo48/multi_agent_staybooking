#!/usr/bin/env python3
"""Week 7 smoke run for config-driven task granularity switch."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week7"
GRANULARITY_CONFIG = PROJECT_ROOT / "configs" / "granularity_profiles.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents import (
    ArchitectAgent,
    BackendDeveloperAgent,
    DevOpsAgent,
    FrontendDeveloperAgent,
    ProductManagerAgent,
    QAAgent,
)
from core import GranularityProfile, load_granularity_registry
from core.orchestrator import Orchestrator
from topologies.sequential import SequentialTopology


@dataclass
class ScenarioSummary:
    granularity: str
    turn_count: int
    role_order: list[str]
    total_tokens: int
    total_api_calls: int
    state_snapshot: str
    report_snapshot: str


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def register_default_agents(orchestrator: Orchestrator) -> None:
    orchestrator.register_agent(ProductManagerAgent("pm", "pm prompt", []))
    orchestrator.register_agent(ArchitectAgent("architect", "architect prompt", []))
    orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend prompt", []))
    orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend prompt", []))
    orchestrator.register_agent(QAAgent("qa", "qa prompt", []))
    orchestrator.register_agent(DevOpsAgent("devops", "devops prompt", []))


def assert_state_shape(profile: GranularityProfile, state: Any) -> tuple[bool, str]:
    missing_required: list[str] = []
    present_forbidden: list[str] = []

    for field_name in profile.expected_state_fields:
        if getattr(state, field_name, None) is None:
            missing_required.append(field_name)

    for field_name in profile.forbidden_state_fields:
        if getattr(state, field_name, None) is not None:
            present_forbidden.append(field_name)

    if missing_required or present_forbidden:
        return (
            False,
            (
                f"missing_required={missing_required}, "
                f"present_forbidden={present_forbidden}"
            ),
        )
    return True, "state shape matches profile constraints"


def run_profile(profile: GranularityProfile) -> tuple[ScenarioSummary, list[CheckResult], int]:
    orchestrator = Orchestrator()
    register_default_agents(orchestrator)

    if profile.topology != "sequential":
        raise ValueError(f"Unsupported topology for week7 smoke: {profile.topology}")

    topology = SequentialTopology(orchestrator=orchestrator, roles=profile.roles)
    turn_results = topology.run(profile.kickoff_content)
    state = orchestrator.state

    state_path = OUTPUT_DIR / f"week7_{profile.name}_state.json"
    profile_report_path = OUTPUT_DIR / f"week7_{profile.name}_report.json"
    state.save_json(state_path)

    state_shape_ok, state_shape_detail = assert_state_shape(profile, state)

    checks = [
        CheckResult(
            name=f"{profile.name}_turn_count",
            passed=len(turn_results) == len(profile.roles),
            details=f"turn_count={len(turn_results)}, expected={len(profile.roles)}",
        ),
        CheckResult(
            name=f"{profile.name}_role_order",
            passed=[result.agent_role for result in turn_results] == profile.roles,
            details=f"roles={[result.agent_role for result in turn_results]}",
        ),
        CheckResult(
            name=f"{profile.name}_all_turns_success",
            passed=all(result.success for result in turn_results),
            details="all turn results should be success",
        ),
        CheckResult(
            name=f"{profile.name}_state_shape",
            passed=state_shape_ok,
            details=state_shape_detail,
        ),
        CheckResult(
            name=f"{profile.name}_usage_count",
            passed=state.total_api_calls == len(profile.roles),
            details=(
                f"api_calls={state.total_api_calls}, "
                f"expected={len(profile.roles)}, tokens={state.total_tokens}"
            ),
        ),
    ]

    profile_status = 0 if all(item.passed for item in checks) else 1
    write_json(
        profile_report_path,
        {
            "granularity": profile.name,
            "status": "success" if profile_status == 0 else "failed",
            "checks": [asdict(item) for item in checks],
            "turn_results": [asdict(result) for result in turn_results],
            "state_snapshot": str(state_path),
        },
    )

    summary = ScenarioSummary(
        granularity=profile.name,
        turn_count=len(turn_results),
        role_order=[result.agent_role for result in turn_results],
        total_tokens=state.total_tokens,
        total_api_calls=state.total_api_calls,
        state_snapshot=str(state_path),
        report_snapshot=str(profile_report_path),
    )
    return summary, checks, profile_status


def run_smoke() -> tuple[int, list[CheckResult], Path]:
    registry = load_granularity_registry(GRANULARITY_CONFIG)
    summaries: list[ScenarioSummary] = []
    all_checks: list[CheckResult] = []
    status = 0

    for granularity in ["layer", "module", "feature"]:
        profile = registry.get_profile(granularity)
        summary, checks, profile_status = run_profile(profile)
        summaries.append(summary)
        all_checks.extend(checks)
        if profile_status != 0:
            status = 1

    summary_path = OUTPUT_DIR / "week7_granularity_switch_report.json"
    write_json(
        summary_path,
        {
            "status": "success" if status == 0 else "failed",
            "config": str(GRANULARITY_CONFIG),
            "profiles_run": [item.granularity for item in summaries],
            "summary": [asdict(item) for item in summaries],
            "checks": [asdict(item) for item in all_checks],
        },
    )
    return status, all_checks, summary_path


def main() -> int:
    code, checks, summary_path = run_smoke()
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.details}")
    print(f"Summary report: {summary_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
