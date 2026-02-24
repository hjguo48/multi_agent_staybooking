#!/usr/bin/env python3
"""Validate prompt files against schema-linked contract requirements."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


@dataclass
class ContractCheck:
    agent: str
    check_name: str
    passed: bool
    details: str


def resolve_path(path_value: str) -> Path:
    raw = Path(path_value)
    if raw.is_absolute():
        return raw

    cwd_candidate = (Path.cwd() / raw).resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    return (PROJECT_ROOT / raw).resolve()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_file_exists(agent: str, label: str, path: Path) -> ContractCheck:
    return ContractCheck(
        agent=agent,
        check_name=f"{label}_exists",
        passed=path.exists(),
        details=str(path),
    )


def check_schema_keys(
    agent: str,
    schema_payload: dict[str, Any],
    required_schema_keys: list[str],
) -> list[ContractCheck]:
    results: list[ContractCheck] = []
    schema_props = schema_payload.get("properties", {})
    schema_required = set(schema_payload.get("required", []))
    for key in required_schema_keys:
        has_prop = key in schema_props
        is_required = key in schema_required
        passed = has_prop and is_required
        details = f"prop={has_prop}, required={is_required}, key={key}"
        results.append(
            ContractCheck(
                agent=agent,
                check_name=f"schema_key_{key}",
                passed=passed,
                details=details,
            )
        )
    return results


def check_prompt_tokens(agent: str, prompt_text: str, tokens: list[str]) -> list[ContractCheck]:
    results: list[ContractCheck] = []
    normalized_text = prompt_text.lower()
    for token in tokens:
        token_exists = token.lower() in normalized_text
        results.append(
            ContractCheck(
                agent=agent,
                check_name=f"prompt_contains::{token}",
                passed=token_exists,
                details=f"token={token}",
            )
        )
    return results


def run_validation(contract_path: Path) -> tuple[int, dict[str, Any]]:
    payload = load_json(contract_path)
    contracts = payload.get("contracts", [])
    checks: list[ContractCheck] = []

    for item in contracts:
        agent = item["agent"]
        prompt_path = resolve_path(item["prompt_path"])
        schema_path = resolve_path(item["schema_path"])

        prompt_exists = check_file_exists(agent, "prompt_file", prompt_path)
        schema_exists = check_file_exists(agent, "schema_file", schema_path)
        checks.extend([prompt_exists, schema_exists])

        if not prompt_exists.passed or not schema_exists.passed:
            continue

        prompt_text = prompt_path.read_text(encoding="utf-8")
        schema_payload = load_json(schema_path)
        checks.extend(
            check_schema_keys(agent, schema_payload, item.get("required_schema_keys", []))
        )
        checks.extend(check_prompt_tokens(agent, prompt_text, item.get("must_contain", [])))

    all_passed = all(check.passed for check in checks)
    report = {
        "status": "success" if all_passed else "failed",
        "contract_path": str(contract_path),
        "total_checks": len(checks),
        "passed_checks": sum(1 for check in checks if check.passed),
        "failed_checks": sum(1 for check in checks if not check.passed),
        "checks": [asdict(check) for check in checks],
    }
    return (0 if all_passed else 1), report


def write_report(report: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate prompt/schema contracts.")
    parser.add_argument(
        "--contract-file",
        default="configs/prompt_contracts.json",
        help="Path to prompt contracts JSON",
    )
    parser.add_argument(
        "--report-file",
        default="outputs/week2/prompt_contract_report.json",
        help="Path to output report JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract_path = resolve_path(args.contract_file)
    report_path = resolve_path(args.report_file)
    code, report = run_validation(contract_path)
    write_report(report, report_path)

    for check in report["checks"]:
        marker = "PASS" if check["passed"] else "FAIL"
        print(f"[{marker}] {check['agent']}::{check['check_name']} - {check['details']}")
    print(f"Prompt contract report: {report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
