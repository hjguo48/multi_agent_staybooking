#!/usr/bin/env python3
"""Unified entry point for experiment tasks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_WEEK1_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week1_baseline.json"
)
DEFAULT_WEEK2_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week2_smoke.json"
)
DEFAULT_WEEK3_STEP1_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week3_step1_orchestrator.json"
)
DEFAULT_WEEK3_STEP2_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week3_step2_sequential.json"
)
DEFAULT_WEEK4_HUB_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week4_hub_spoke.json"
)
DEFAULT_WEEK5_PEER_REVIEW_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week5_peer_review.json"
)
DEFAULT_WEEK6_ITERATIVE_FEEDBACK_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week6_iterative_feedback.json"
)
DEFAULT_WEEK7_GRANULARITY_SWITCH_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week7_granularity_switch.json"
)
DEFAULT_WEEK8_EVALUATION_V1_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week8_evaluation_v1.json"
)
DEFAULT_WEEK9_PILOT_CONFIG = (
    PROJECT_ROOT / "configs" / "experiment_configs" / "week9_pilot.json"
)


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    status: str
    started_at: str
    ended_at: str
    stdout: str
    stderr: str


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_path(path_value: str | Path) -> Path:
    path_obj = Path(path_value)
    if path_obj.is_absolute():
        return path_obj
    return (PROJECT_ROOT / path_obj).resolve()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def expand_command(command: list[str]) -> list[str]:
    expanded: list[str] = []
    for token in command:
        if token == "${PYTHON}":
            expanded.append(sys.executable)
            continue
        expanded.append(token)
    return expanded


def run_step(step: dict[str, Any]) -> StepResult:
    command = expand_command(step["command"])
    started_at = now_utc()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )
    ended_at = now_utc()
    status = "success" if completed.returncode == 0 else "failed"
    return StepResult(
        name=step["name"],
        command=command,
        returncode=completed.returncode,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def write_report(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def execute_from_config(config_path: Path) -> int:
    config = load_config(config_path)
    pipeline_name = config.get("name", "unnamed_pipeline")
    steps = config.get("steps", [])
    report_path = resolve_path(
        config.get("report_path", "outputs/week1/week1_pipeline_report.json")
    )

    if not steps:
        print(f"Config has no steps: {config_path}")
        return 2

    results: list[StepResult] = []
    overall_status = "success"
    for step in steps:
        step_name = step.get("name", "unnamed_step")
        print(f"[RUN] {step_name}")
        result = run_step(step)
        results.append(result)
        print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        if result.returncode != 0:
            overall_status = "failed"
            break

    report = {
        "pipeline": pipeline_name,
        "config_path": str(config_path),
        "executed_at": now_utc(),
        "status": overall_status,
        "steps": [
            {
                "name": r.name,
                "command": r.command,
                "returncode": r.returncode,
                "status": r.status,
                "started_at": r.started_at,
                "ended_at": r.ended_at,
                "stdout": r.stdout,
                "stderr": r.stderr,
            }
            for r in results
        ],
    }
    write_report(report_path, report)
    print(f"[REPORT] {report_path}")

    return 0 if overall_status == "success" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run experiment tasks.")
    parser.add_argument(
        "--task",
        choices=[
            "week1",
            "week2-smoke",
            "week3-step1",
            "week3-step2",
            "week4-hub",
            "week5-peer-review",
            "week6-iterative-feedback",
            "week7-granularity-switch",
            "week8-evaluation-v1",
            "week9-pilot",
            "verify-baseline",
            "extract-ground-truth",
            "validate-prompts"
        ],
        default="week1",
        help="Task to execute",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Optional pipeline config JSON path for week task runs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.task == "verify-baseline":
        return subprocess.call(
            [sys.executable, str(PROJECT_ROOT / "evaluation" / "verify_baseline_lock.py")],
            cwd=PROJECT_ROOT,
        )
    if args.task == "extract-ground-truth":
        return subprocess.call(
            [sys.executable, str(PROJECT_ROOT / "evaluation" / "extract_ground_truth.py")],
            cwd=PROJECT_ROOT,
        )
    if args.task == "validate-prompts":
        return subprocess.call(
            [sys.executable, str(PROJECT_ROOT / "evaluation" / "validate_prompt_contracts.py")],
            cwd=PROJECT_ROOT,
        )
    if args.task == "week3-step1":
        config_path = (
            resolve_path(args.config) if args.config else DEFAULT_WEEK3_STEP1_CONFIG
        )
        return execute_from_config(config_path)
    if args.task == "week3-step2":
        config_path = (
            resolve_path(args.config) if args.config else DEFAULT_WEEK3_STEP2_CONFIG
        )
        return execute_from_config(config_path)
    if args.task == "week4-hub":
        config_path = (
            resolve_path(args.config) if args.config else DEFAULT_WEEK4_HUB_CONFIG
        )
        return execute_from_config(config_path)
    if args.task == "week5-peer-review":
        config_path = (
            resolve_path(args.config)
            if args.config
            else DEFAULT_WEEK5_PEER_REVIEW_CONFIG
        )
        return execute_from_config(config_path)
    if args.task == "week6-iterative-feedback":
        config_path = (
            resolve_path(args.config)
            if args.config
            else DEFAULT_WEEK6_ITERATIVE_FEEDBACK_CONFIG
        )
        return execute_from_config(config_path)
    if args.task == "week7-granularity-switch":
        config_path = (
            resolve_path(args.config)
            if args.config
            else DEFAULT_WEEK7_GRANULARITY_SWITCH_CONFIG
        )
        return execute_from_config(config_path)
    if args.task == "week8-evaluation-v1":
        config_path = (
            resolve_path(args.config)
            if args.config
            else DEFAULT_WEEK8_EVALUATION_V1_CONFIG
        )
        return execute_from_config(config_path)
    if args.task == "week9-pilot":
        config_path = (
            resolve_path(args.config)
            if args.config
            else DEFAULT_WEEK9_PILOT_CONFIG
        )
        return execute_from_config(config_path)
    if args.task == "week2-smoke":
        config_path = resolve_path(args.config) if args.config else DEFAULT_WEEK2_CONFIG
        return execute_from_config(config_path)
    config_path = resolve_path(args.config) if args.config else DEFAULT_WEEK1_CONFIG
    return execute_from_config(config_path)


if __name__ == "__main__":
    raise SystemExit(main())
