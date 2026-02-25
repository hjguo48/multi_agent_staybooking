#!/usr/bin/env python3
"""Week 8 evaluation pipeline v1.

Computes:
- requirement/API/entity coverage
- code quality proxy score
- architecture quality proxy score
- deployability score
- efficiency stats and normalized efficiency
- weighted composite score Q

Also performs runtime-backed validation:
- materialize generated backend/frontend code bundles to disk
- execute backend/frontend build+test checks
- execute lightweight deploy checks
- fold runtime pass rates into code_quality/deploy_score
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week8"
TARGETS_CONFIG = PROJECT_ROOT / "configs" / "evaluation_targets" / "week8_v1_targets.json"
MATERIALIZATION_MODE = "pure_generated"  # pure_generated | template_overlay
STRICT_RUNTIME_SCORING = True
VALIDATION_TIMEOUT_SECONDS = 180.0
VALIDATOR_RUN_BACKEND_TESTS = True
VALIDATOR_RUN_FRONTEND_CHECKS = False
VALIDATOR_RUN_FRONTEND_TESTS = False

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import RunMetrics, ScoreWeights, apply_composite_scores, evaluate_run
from tools import ArtifactMaterializer, BuildDeployValidator


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


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


def sanitize_run_name(name: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return token or "run"


def resolve_template_path(raw_path: Any) -> Path | None:
    text = str(raw_path or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve()
    if resolved.exists():
        return resolved
    return None


def resolve_template_roots(ground_truth: dict[str, Any]) -> tuple[Path | None, Path | None]:
    sources = ground_truth.get("sources", {})
    if not isinstance(sources, dict):
        return None, None
    backend = sources.get("backend", {})
    frontend = sources.get("frontend", {})
    backend_path = backend.get("path") if isinstance(backend, dict) else None
    frontend_path = frontend.get("path") if isinstance(frontend, dict) else None
    return resolve_template_path(backend_path), resolve_template_path(frontend_path)


def select_templates(
    ground_truth: dict[str, Any], mode: str
) -> tuple[Path | None, Path | None, list[CheckResult]]:
    if mode == "pure_generated":
        return None, None, [
            CheckResult(
                name="backend_template_disabled",
                passed=True,
                details="materialization_mode=pure_generated",
            ),
            CheckResult(
                name="frontend_template_disabled",
                passed=True,
                details="materialization_mode=pure_generated",
            ),
        ]

    if mode != "template_overlay":
        raise ValueError(
            f"invalid MATERIALIZATION_MODE={mode}; expected pure_generated or template_overlay"
        )

    backend_template, frontend_template = resolve_template_roots(ground_truth)
    return backend_template, frontend_template, [
        CheckResult(
            name="backend_template_exists",
            passed=backend_template is not None,
            details=to_repo_rel(backend_template)
            if backend_template
            else "missing backend template path",
        ),
        CheckResult(
            name="frontend_template_exists",
            passed=frontend_template is not None,
            details=to_repo_rel(frontend_template)
            if frontend_template
            else "missing frontend template path",
        ),
    ]


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
    ground_truth: dict[str, Any],
    run_targets: list[dict[str, str]],
    *,
    backend_template: Path | None,
    frontend_template: Path | None,
    materialized_output_root: Path,
    workspace_run_prefix: str,
    strict_runtime_scoring: bool,
    validation_timeout_seconds: float = VALIDATION_TIMEOUT_SECONDS,
) -> tuple[list[RunMetrics], list[CheckResult], list[dict[str, Any]]]:
    metrics: list[RunMetrics] = []
    checks: list[CheckResult] = []
    runtime_validation: list[dict[str, Any]] = []
    materializer = ArtifactMaterializer(materialized_output_root)

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

        runtime_entry: dict[str, Any] = {"run_name": name, "state_path": to_repo_rel(state_path)}
        workspace_run_name = f"{workspace_run_prefix}_{sanitize_run_name(name)}"

        try:
            materialized = materializer.materialize(
                run_name=workspace_run_name,
                state_payload=payload,
                backend_template=backend_template,
                frontend_template=frontend_template,
            )
            runtime_entry["materialization"] = materialized.to_dict()

            files_written = (
                len(materialized.backend_files_written) + len(materialized.frontend_files_written)
            )
            checks.append(
                CheckResult(
                    name=f"{name}_materialization_has_files",
                    passed=files_written > 0,
                    details=f"files_written={files_written}",
                )
            )

            validator = BuildDeployValidator(
                backend_root=Path(materialized.backend_root),
                frontend_root=Path(materialized.frontend_root),
                timeout_seconds=validation_timeout_seconds,
                run_backend_tests=VALIDATOR_RUN_BACKEND_TESTS,
                run_frontend_checks=VALIDATOR_RUN_FRONTEND_CHECKS,
                run_frontend_tests=VALIDATOR_RUN_FRONTEND_TESTS,
            )
            validation_result = validator.run(payload)
            runtime_entry["validation"] = validation_result

            scores = validation_result.get("scores", {})
            build_pass_rate = float(scores.get("build_test_pass_rate", 0.0))
            build_executed_steps = int(scores.get("build_test_executed_steps", 0))
            deploy_pass_rate = float(scores.get("deploy_pass_rate", 0.0))
            deploy_executed_steps = int(scores.get("deploy_executed_steps", 0))
            deploy_real_pass_rate = float(scores.get("deploy_real_pass_rate", 0.0))
            deploy_real_executed_steps = int(scores.get("deploy_real_executed_steps", 0))

            original_code_quality = metric.code_quality
            original_deploy_score = metric.deploy_score

            if strict_runtime_scoring:
                metric.code_quality = clamp01(min(metric.code_quality, build_pass_rate))
                metric.deploy_score = clamp01(min(metric.deploy_score, deploy_real_pass_rate))
            else:
                if build_executed_steps > 0:
                    metric.code_quality = clamp01(min(metric.code_quality, build_pass_rate))
                if deploy_executed_steps > 0:
                    metric.deploy_score = clamp01(min(metric.deploy_score, deploy_pass_rate))

            runtime_entry["score_adjustment"] = {
                "strict_runtime_scoring": strict_runtime_scoring,
                "original_code_quality": original_code_quality,
                "runtime_build_pass_rate": build_pass_rate,
                "adjusted_code_quality": metric.code_quality,
                "original_deploy_score": original_deploy_score,
                "runtime_deploy_pass_rate": deploy_pass_rate,
                "runtime_deploy_real_pass_rate": deploy_real_pass_rate,
                "adjusted_deploy_score": metric.deploy_score,
                "build_executed_steps": build_executed_steps,
                "deploy_executed_steps": deploy_executed_steps,
                "deploy_real_executed_steps": deploy_real_executed_steps,
            }

            checks.append(
                CheckResult(
                    name=f"{name}_runtime_validation_executed",
                    passed=True,
                    details=(
                        f"build_pass_rate={build_pass_rate:.4f} (steps={build_executed_steps}), "
                        f"deploy_pass_rate={deploy_pass_rate:.4f} (steps={deploy_executed_steps})"
                    ),
                )
            )
        except Exception as exc:
            runtime_entry["error"] = str(exc)
            checks.append(
                CheckResult(
                    name=f"{name}_runtime_validation_executed",
                    passed=False,
                    details=f"materialize/validate failed: {exc}",
                )
            )

        runtime_validation.append(runtime_entry)

    return metrics, checks, runtime_validation


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
    backend_template, frontend_template, checks = select_templates(
        ground_truth, MATERIALIZATION_MODE
    )

    metrics, eval_checks, runtime_validation = evaluate_targets(
        ground_truth,
        run_targets,
        backend_template=backend_template,
        frontend_template=frontend_template,
        materialized_output_root=OUTPUT_DIR / "generated_workspaces",
        workspace_run_prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"),
        strict_runtime_scoring=STRICT_RUNTIME_SCORING,
    )
    checks.extend(eval_checks)

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
            "materialization_mode": MATERIALIZATION_MODE,
            "strict_runtime_scoring": STRICT_RUNTIME_SCORING,
            "runtime_validation_options": {
                "timeout_seconds": VALIDATION_TIMEOUT_SECONDS,
                "run_backend_tests": VALIDATOR_RUN_BACKEND_TESTS,
                "run_frontend_checks": VALIDATOR_RUN_FRONTEND_CHECKS,
                "run_frontend_tests": VALIDATOR_RUN_FRONTEND_TESTS,
            },
            "runs": [metric.to_dict() for metric in metrics],
            "runtime_validation": runtime_validation,
            "ranking": ranking,
            "checks": [asdict(check) for check in checks],
        },
    )
    return (0 if status == "success" else 1), checks, report_path


def main() -> int:
    code, checks, report_path = run_evaluation()
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        line = f"[{marker}] {check.name}: {check.details}"
        try:
            print(line)
        except UnicodeEncodeError:
            console_encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            print(
                line.encode(console_encoding, errors="replace").decode(
                    console_encoding, errors="replace"
                )
            )
    print(f"Evaluation report: {report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
