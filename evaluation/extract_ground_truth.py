#!/usr/bin/env python3
"""Extract benchmark artifacts from StayBooking backend/frontend repositories."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


HTTP_MAPPING_TO_METHOD = {
    "GetMapping": "GET",
    "PostMapping": "POST",
    "PutMapping": "PUT",
    "DeleteMapping": "DELETE",
    "PatchMapping": "PATCH",
}


@dataclass
class Endpoint:
    http_method: str
    full_path: str
    class_path: str
    method_path: str
    controller: str
    java_method: str
    file: str
    line: int


def git_value(repo_dir: Path, args: list[str]) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_dir), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return ""
    return out.strip()


def to_posix(path: Path) -> str:
    return path.as_posix()


def to_rel_posix(path: Path, base: Path) -> str:
    try:
        relative = path.resolve().relative_to(base.resolve())
    except Exception:
        relative = path.resolve()
    return to_posix(relative)


def repo_metadata(repo_dir: Path) -> dict[str, str]:
    return {
        "path": to_rel_posix(repo_dir, PROJECT_ROOT),
        "path_base": "project_root",
        "branch": git_value(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": git_value(repo_dir, ["rev-parse", "HEAD"]),
        "remote_origin": git_value(repo_dir, ["remote", "get-url", "origin"]),
    }


def normalize_path(path: str) -> str:
    if not path:
        return ""
    if not path.startswith("/"):
        path = f"/{path}"
    return re.sub(r"/{2,}", "/", path).rstrip("/") or "/"


def clean_annotation_path(raw: str | None) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    if raw.startswith("value") or raw.startswith("path"):
        m = re.search(r'=\s*"([^"]*)"', raw)
        return m.group(1) if m else ""
    return raw.strip('"').strip()


def extract_class_mapping(lines: list[str]) -> str:
    for line in lines:
        m = re.search(r'@RequestMapping\(([^)]*)\)', line)
        if m:
            return clean_annotation_path(m.group(1))
    return ""


def extract_java_method_name(lines: list[str], start_index: int) -> str:
    method_re = re.compile(
        r"\b(public|private|protected)\s+[A-Za-z0-9_<>, ?\[\]]+\s+([A-Za-z0-9_]+)\s*\("
    )
    for i in range(start_index, min(start_index + 10, len(lines))):
        m = method_re.search(lines[i])
        if m:
            return m.group(2)
    return "unknownMethod"


def extract_endpoints(backend_dir: Path) -> list[dict[str, Any]]:
    endpoints: list[Endpoint] = []
    controller_files = sorted(backend_dir.rglob("*Controller.java"))
    for file_path in controller_files:
        text = file_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        class_path = extract_class_mapping(lines)
        controller_name = file_path.stem

        for i, line in enumerate(lines):
            mapping_match = re.search(
                r'@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\s*(?:\(([^)]*)\))?',
                line,
            )
            if not mapping_match:
                continue

            mapping_type = mapping_match.group(1)
            method = HTTP_MAPPING_TO_METHOD[mapping_type]
            method_path = clean_annotation_path(mapping_match.group(2))
            full_path = normalize_path(f"{class_path}/{method_path}")
            java_method = extract_java_method_name(lines, i + 1)
            endpoints.append(
                Endpoint(
                    http_method=method,
                    full_path=full_path,
                    class_path=normalize_path(class_path),
                    method_path=normalize_path(method_path),
                    controller=controller_name,
                    java_method=java_method,
                    file=to_rel_posix(file_path, backend_dir),
                    line=i + 1,
                )
            )

    return [asdict(endpoint) for endpoint in endpoints]


def extract_entities(backend_dir: Path) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    java_files = sorted(backend_dir.rglob("*.java"))
    relation_patterns = (
        "@OneToMany",
        "@ManyToOne",
        "@OneToOne",
        "@ManyToMany",
    )
    for file_path in java_files:
        text = file_path.read_text(encoding="utf-8")
        if "@Entity" not in text:
            continue

        lines = text.splitlines()
        class_match = re.search(r"\bclass\s+([A-Za-z0-9_]+)", text)
        table_match = re.search(r'@Table\((?:name\s*=\s*)?"([^"]+)"', text)
        id_fields = []
        relationship_count = 0
        for i, line in enumerate(lines):
            if "@Id" in line:
                for j in range(i + 1, min(i + 4, len(lines))):
                    field_match = re.search(r"\b([A-Za-z0-9_]+)\s*;", lines[j])
                    if field_match:
                        id_fields.append(field_match.group(1))
                        break
            if any(p in line for p in relation_patterns):
                relationship_count += 1

        entities.append(
            {
                "class": class_match.group(1) if class_match else file_path.stem,
                "table": table_match.group(1) if table_match else "",
                "id_fields": id_fields,
                "relationship_annotations": relationship_count,
                "file": to_rel_posix(file_path, backend_dir),
            }
        )
    return entities


def extract_backend_structure(backend_dir: Path) -> dict[str, Any]:
    java_files = list(backend_dir.rglob("*.java"))
    return {
        "controllers": sorted(
            to_rel_posix(p, backend_dir) for p in backend_dir.rglob("*Controller.java")
        ),
        "services": sorted(
            to_rel_posix(p, backend_dir) for p in backend_dir.rglob("*Service.java")
        ),
        "repositories": sorted(
            to_rel_posix(p, backend_dir) for p in backend_dir.rglob("*Repository.java")
        ),
        "total_java_files": len(java_files),
    }


def extract_frontend_components(frontend_dir: Path) -> list[str]:
    components_dir = frontend_dir / "src" / "components"
    if not components_dir.exists():
        return []
    return sorted(to_rel_posix(p, frontend_dir) for p in components_dir.rglob("*.js"))


def extract_frontend_api_calls(frontend_dir: Path) -> list[dict[str, Any]]:
    utils_file = frontend_dir / "src" / "utils.js"
    if not utils_file.exists():
        return []

    lines = utils_file.read_text(encoding="utf-8").splitlines()
    calls: list[dict[str, Any]] = []
    current_fn = ""
    current_method = "GET"
    current_path = ""
    current_query_params: list[str] = []
    in_function = False
    brace_depth = 0

    fn_pattern = re.compile(r"export const ([A-Za-z0-9_]+)\s*=\s*\(")
    method_pattern = re.compile(r'method:\s*"([A-Z]+)"')
    path_pattern = re.compile(r"\$\{domain\}/([^`\"']+)")
    query_pattern = re.compile(r"searchParams\.append\(\"([A-Za-z0-9_]+)\"")

    for line in lines:
        fn_match = fn_pattern.search(line)
        if fn_match:
            if in_function and current_path:
                calls.append(
                    {
                        "function": current_fn,
                        "http_method": current_method,
                        "path_template": normalize_path(current_path),
                        "query_params": current_query_params,
                    }
                )

            current_fn = fn_match.group(1)
            current_method = "GET"
            current_path = ""
            current_query_params = []
            in_function = True
            brace_depth = line.count("{") - line.count("}")
            continue

        if not in_function:
            continue

        brace_depth += line.count("{") - line.count("}")
        method_match = method_pattern.search(line)
        if method_match:
            current_method = method_match.group(1)

        path_match = path_pattern.search(line)
        if path_match:
            current_path = path_match.group(1).split("?")[0]

        query_match = query_pattern.search(line)
        if query_match:
            current_query_params.append(query_match.group(1))

        if brace_depth <= 0:
            if current_path:
                calls.append(
                    {
                        "function": current_fn,
                        "http_method": current_method,
                        "path_template": normalize_path(current_path),
                        "query_params": current_query_params,
                    }
                )
            in_function = False

    if in_function and current_path:
        calls.append(
            {
                "function": current_fn,
                "http_method": current_method,
                "path_template": normalize_path(current_path),
                "query_params": current_query_params,
            }
        )

    return calls


def build_ground_truth(backend_dir: Path, frontend_dir: Path) -> dict[str, Any]:
    endpoints = extract_endpoints(backend_dir)
    entities = extract_entities(backend_dir)
    backend_structure = extract_backend_structure(backend_dir)
    frontend_components = extract_frontend_components(frontend_dir)
    frontend_api_calls = extract_frontend_api_calls(frontend_dir)

    return {
        "path_policy": {
            "filesystem_paths": "project_relative_or_repo_relative_posix",
            "path_separator": "/",
        },
        "sources": {
            "backend": repo_metadata(backend_dir),
            "frontend": repo_metadata(frontend_dir),
        },
        "backend": {
            "endpoints": endpoints,
            "entities": entities,
            "structure": backend_structure,
        },
        "frontend": {
            "components": frontend_components,
            "api_calls": frontend_api_calls,
        },
        "summary": {
            "backend_endpoint_count": len(endpoints),
            "backend_entity_count": len(entities),
            "backend_controller_count": len(backend_structure["controllers"]),
            "backend_service_count": len(backend_structure["services"]),
            "backend_repository_count": len(backend_structure["repositories"]),
            "frontend_component_count": len(frontend_components),
            "frontend_api_call_count": len(frontend_api_calls),
            "methodology_reference": {
                "expected_endpoint_count": 14,
                "expected_entity_count": 5,
            },
        },
    }


def write_markdown_report(data: dict[str, Any], report_path: Path) -> None:
    summary = data["summary"]
    backend = data["backend"]
    frontend = data["frontend"]
    src = data["sources"]

    lines = [
        "# StayBooking Ground Truth Snapshot",
        "",
        "## Source Repositories",
        f"- Backend: `{src['backend']['remote_origin']}` @ `{src['backend']['commit']}`",
        f"- Frontend: `{src['frontend']['remote_origin']}` @ `{src['frontend']['commit']}`",
        "",
        "## Counts",
        f"- Backend endpoints: {summary['backend_endpoint_count']}",
        f"- Backend entities: {summary['backend_entity_count']}",
        f"- Backend controllers/services/repositories: "
        f"{summary['backend_controller_count']}/{summary['backend_service_count']}/"
        f"{summary['backend_repository_count']}",
        f"- Frontend components: {summary['frontend_component_count']}",
        f"- Frontend API calls: {summary['frontend_api_call_count']}",
        "",
        "## Backend Endpoints",
    ]

    for ep in backend["endpoints"]:
        lines.append(
            f"- `{ep['http_method']} {ep['full_path']}` "
            f"({ep['controller']}.{ep['java_method']})"
        )

    lines.extend(["", "## Backend Entities"])
    for entity in backend["entities"]:
        table = entity["table"] if entity["table"] else "(default)"
        lines.append(f"- `{entity['class']}` table={table} id={entity['id_fields']}")

    lines.extend(["", "## Frontend API Calls"])
    for call in frontend["api_calls"]:
        lines.append(
            f"- `{call['http_method']} {call['path_template']}` via `{call['function']}`"
        )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract StayBooking ground truth data.")
    parser.add_argument(
        "--backend-dir",
        default="ground_truth/staybooking-project",
        help="Path to backend repository",
    )
    parser.add_argument(
        "--frontend-dir",
        default="ground_truth/stayboookingfe",
        help="Path to frontend repository",
    )
    parser.add_argument(
        "--output-json",
        default="ground_truth/benchmark/staybooking_ground_truth.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--output-md",
        default="ground_truth/benchmark/staybooking_ground_truth.md",
        help="Output markdown report path",
    )
    return parser.parse_args()


def resolve_input_path(path_value: str) -> Path:
    raw = Path(path_value)
    if raw.is_absolute():
        return raw

    cwd_candidate = (Path.cwd() / raw).resolve()
    if cwd_candidate.exists():
        return cwd_candidate

    project_candidate = (PROJECT_ROOT / raw).resolve()
    if project_candidate.exists():
        return project_candidate

    return project_candidate


def resolve_output_path(path_value: str) -> Path:
    raw = Path(path_value)
    if raw.is_absolute():
        return raw
    return (PROJECT_ROOT / raw).resolve()


def main() -> None:
    args = parse_args()
    backend_dir = resolve_input_path(args.backend_dir)
    frontend_dir = resolve_input_path(args.frontend_dir)
    output_json = resolve_output_path(args.output_json)
    output_md = resolve_output_path(args.output_md)

    if not backend_dir.exists():
        raise FileNotFoundError(f"Backend directory not found: {backend_dir}")
    if not frontend_dir.exists():
        raise FileNotFoundError(f"Frontend directory not found: {frontend_dir}")

    data = build_ground_truth(backend_dir, frontend_dir)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    write_markdown_report(data, output_md)

    print(f"Wrote JSON: {output_json}")
    print(f"Wrote report: {output_md}")


if __name__ == "__main__":
    main()
