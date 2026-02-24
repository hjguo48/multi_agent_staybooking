#!/usr/bin/env python3
"""Verify local repositories match the locked baseline commits."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def git_value(repo: Path, args: list[str]) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def resolve_path(path_value: str, bases: list[Path]) -> Path:
    raw = Path(path_value)
    if raw.is_absolute():
        return raw

    for base in bases:
        candidate = (base / raw).resolve()
        if candidate.exists():
            return candidate

    return (bases[0] / raw).resolve()


def verify_repo(name: str, cfg: dict, lock_dir: Path) -> tuple[bool, str]:
    repo_path = resolve_path(
        cfg["local_path"],
        [Path.cwd(), PROJECT_ROOT, lock_dir],
    )
    if not repo_path.exists():
        return False, f"[{name}] missing path: {repo_path}"

    try:
        current_commit = git_value(repo_path, ["rev-parse", "HEAD"])
        current_branch = git_value(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        current_origin = git_value(repo_path, ["remote", "get-url", "origin"])
    except subprocess.CalledProcessError as exc:
        return False, f"[{name}] git command failed: {exc.output.strip()}"

    expected_commit = cfg["commit"]
    expected_branch = cfg["branch"]
    expected_origin = cfg["remote_origin"]

    errors = []
    if current_commit != expected_commit:
        errors.append(f"commit mismatch expected={expected_commit} actual={current_commit}")
    if current_branch != expected_branch:
        errors.append(f"branch mismatch expected={expected_branch} actual={current_branch}")
    if current_origin != expected_origin:
        errors.append(f"origin mismatch expected={expected_origin} actual={current_origin}")

    if errors:
        return False, f"[{name}] " + "; ".join(errors)

    return True, (
        f"[{name}] OK commit={current_commit} branch={current_branch} origin={current_origin}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify repository baseline lock.")
    parser.add_argument(
        "--lock-file",
        default="ground_truth/baseline_lock.json",
        help="Path to baseline lock JSON file",
    )
    args = parser.parse_args()

    lock_path = resolve_path(args.lock_file, [Path.cwd(), PROJECT_ROOT, SCRIPT_DIR])
    if not lock_path.exists():
        print(f"Lock file not found: {lock_path}")
        return 2

    lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
    repos = lock_data.get("repositories", {})
    if not repos:
        print("No repositories found in lock file.")
        return 2

    all_ok = True
    lock_dir = lock_path.parent
    for name, repo_cfg in repos.items():
        ok, message = verify_repo(name, repo_cfg, lock_dir)
        print(message)
        all_ok = all_ok and ok

    if all_ok:
        print("BASELINE_VERIFY: PASS")
        return 0

    print("BASELINE_VERIFY: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
