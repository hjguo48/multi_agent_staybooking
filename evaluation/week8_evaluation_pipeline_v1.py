#!/usr/bin/env python3
"""Week 8 evaluation pipeline v1.

Computes:
- requirement/API/entity coverage
- code quality proxy score
- architecture quality proxy score
- deployability score
- efficiency stats and normalized efficiency
- weighted composite score Q
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week8"
TARGETS_CONFIG = PROJECT_ROOT / "configs" / "evaluation_targets" / "week8_v1_targets.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import RunMetrics, ScoreWeights, apply_composite_scores, evaluate_run


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def to_repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_targets(config_path: Path) -> tuple[Path, ScoreWeights, list[dict[str, str]]]:
    payload = load_json(config_path)
    ground_truth_path = PROJECT_ROOT / payload["ground_truth_path"]
    weight_payload = payload.get("weights", {})
    weights = ScoreWeights(
        rcr=float(weight_payload.get("rcr", 0.30)),
        code_quality=float(weight_payload.get("code_quality", 0.20)),
        arch_score=float(weight_payload.get("arch_score", 0.20)),
        deploy_score=float(weight_payload.get("deploy_score", 0.20)),
        efficiency=float(weight_payload.get("efficiency", 0.10)),
    )
    runs = payload.get("runs", [])
    if not isinstance(runs, list):
        raise ValueError("targets config 'runs' must be a list")
    normalized_runs: list[dict[str, str]] = []
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("each run entry must be an object")
        name = str(run.get("name", "")).strip()
        state_path = str(run.get("state_path", "")).strip()
        if not name or not state_path:
            raise ValueError("run entry must include non-empty name and state_path")
        normalized_runs.append({"name": name, "state_path": state_path})
    return ground_truth_path, weights, normalized_runs


def evaluate_targets(
    ground_truth: dict[str, Any], run_targets: list[dict[str, str]]
) -> tuple[list[RunMetrics], list[CheckResult]]:
    metrics: list[RunMetrics] = []
    checks: list[CheckResult] = []

    for run in run_targets:
        name = run["name"]
        state_path = PROJECT_ROOT / run["state_path"]
        if not state_path.exists():
            checks.append(
                CheckResult(
                    name=f"{name}_state_exists",
                    passed=False,
                    details=f"missing state file: {to_repo_rel(state_path)}",
                )
            )
            continue

        payload = load_json(state_path)
        metric = evaluate_run(
            run_name=name,
            state_payload=payload,
            ground_truth_payload=ground_truth,
            state_path=to_repo_rel(state_path),
        )
        metrics.append(metric)
        checks.append(
            CheckResult(
                name=f"{name}_state_exists",
                passed=True,
                details=f"loaded {to_repo_rel(state_path)}",
            )
        )

    return metrics, checks


def build_ranking(metrics: list[RunMetrics]) -> list[dict[str, Any]]:
    ranking: list[dict[str, Any]] = []
    for idx, metric in enumerate(
        sorted(metrics, key=lambda item: item.composite_score, reverse=True),
        start=1,
    ):
        ranking.append(
            {
                "rank": idx,
                "run_name": metric.run_name,
                "composite_score": metric.composite_score,
                "composite_score_pct": metric.composite_score * 100.0,
                "total_tokens": metric.total_tokens,
                "norm_efficiency": metric.norm_efficiency,
            }
        )
    return ranking


def run_evaluation() -> tuple[int, list[CheckResult], Path]:
    ground_truth_path, weights, run_targets = load_targets(TARGETS_CONFIG)
    if not ground_truth_path.exists():
        raise FileNotFoundError(f"Ground truth not found: {ground_truth_path}")

    ground_truth = load_json(ground_truth_path)
    metrics, checks = evaluate_targets(ground_truth, run_targets)

    checks.append(
        CheckResult(
            name="run_count",
            passed=len(metrics) > 0,
            details=f"evaluated_runs={len(metrics)}",
        )
    )

    apply_composite_scores(metrics, weights=weights)

    for metric in metrics:
        range_check = all(
            0.0 <= value <= 1.0
            for value in [
                metric.requirement_coverage,
                metric.api_coverage,
                metric.entity_coverage,
                metric.rcr,
                metric.code_quality,
                metric.arch_score,
                metric.deploy_score,
                metric.norm_efficiency,
                metric.composite_score,
            ]
        )
        checks.append(
            CheckResult(
                name=f"{metric.run_name}_metric_ranges",
                passed=range_check,
                details=(
                    f"rcr={metric.rcr:.4f}, code={metric.code_quality:.4f}, "
                    f"arch={metric.arch_score:.4f}, deploy={metric.deploy_score:.4f}, "
                    f"norm_eff={metric.norm_efficiency:.4f}, q={metric.composite_score:.4f}"
                ),
            )
        )

    ranking = build_ranking(metrics)
    ranking_sorted = (
        all(
            ranking[idx]["composite_score"] >= ranking[idx + 1]["composite_score"]
            for idx in range(len(ranking) - 1)
        )
        if ranking
        else False
    )
    checks.append(
        CheckResult(
            name="ranking_sorted_desc",
            passed=ranking_sorted,
            details=f"ranking_size={len(ranking)}",
        )
    )

    status = "success" if all(check.passed for check in checks) else "failed"
    report_path = OUTPUT_DIR / "week8_evaluation_report.json"
    write_json(
        report_path,
        {
            "status": status,
            "targets_config": to_repo_rel(TARGETS_CONFIG),
            "ground_truth_path": to_repo_rel(ground_truth_path),
            "weights": asdict(weights),
            "runs": [metric.to_dict() for metric in metrics],
            "ranking": ranking,
            "checks": [asdict(check) for check in checks],
        },
    )
    return (0 if status == "success" else 1), checks, report_path


def main() -> int:
    code, checks, report_path = run_evaluation()
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.details}")
    print(f"Evaluation report: {report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
