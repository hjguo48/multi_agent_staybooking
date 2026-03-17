"""Frontend developer agent implementation (rule-driven baseline)."""

from __future__ import annotations

import copy
import json
from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent
from .backend_dev_agent import _qa_rework_needed


def _build_frontend_qa_feedback(context: ProjectState) -> str:
    """Format QA bug reports as a feedback section for the frontend task instruction."""
    qa_art = context.get_latest_artifact("qa_report")
    if qa_art is None or not isinstance(qa_art.content, dict):
        return ""
    bug_reports = qa_art.content.get("bug_reports", [])
    if not isinstance(bug_reports, list) or not bug_reports:
        return ""
    # Prefer frontend-relevant bugs; fall back to all bugs if none found
    frontend_bugs = [
        b for b in bug_reports
        if isinstance(b, dict) and (
            str(b.get("file", "")).startswith("src/")
            and not str(b.get("file", "")).endswith(".java")
        )
    ] or [b for b in bug_reports if isinstance(b, dict)]
    lines = [
        "\n*** REVISION MODE ***",
        "Your previous implementation had QA failures listed below.",
        "Return a COMPLETE updated code_bundle that fixes ALL issues.\n",
        "QA BUG REPORTS TO FIX:",
    ]
    for bug in frontend_bugs:
        sev = bug.get("severity", "")
        f = bug.get("file", "")
        desc = bug.get("description", "")
        fix = bug.get("suggested_fix", "")
        lines.append(f"- [{sev}] {f}: {desc}")
        if fix:
            lines.append(f"  Fix: {fix}")
    return "\n".join(lines) + "\n"


class FrontendDeveloperAgent(BaseAgent):
    """Generate frontend code artifact for the current module."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        proj = context.project_config or {}
        mod = context.module_config or {}

        fe = proj.get("frontend", {})

        module_id = mod.get("module_id", "module")
        module_name = mod.get("module_name", module_id)
        app_root = fe.get("app_root_file", "src/App.js")
        entry_file = fe.get("entry_file", "src/index.js")
        deps_str = "\n  - ".join(fe.get("dependencies", []))
        min_files, max_files = 2, 5

        project_name = proj.get("project_name", "App")

        # Functional requirements from module config (plain strings)
        fr_raw = mod.get("functional_requirements", [])
        fr_lines = "\n".join(
            f"- {fr}" if isinstance(fr, str) else f"- {fr.get('user_story', str(fr))}"
            for fr in fr_raw
        ) if fr_raw else f"Implement the {module_name} UI."

        latest_frontend_artifact = context.get_latest_artifact("frontend_code")
        if latest_frontend_artifact is not None:
            cached_module = (
                latest_frontend_artifact.content.get("module", "")
                if isinstance(latest_frontend_artifact.content, dict)
                else ""
            )
            generation = latest_frontend_artifact.metadata.get("generation", {})
            if (
                isinstance(generation, dict)
                and generation.get("source") == "llm"
                and cached_module == module_id
                and not _qa_rework_needed(context)
            ):
                cached_content = (
                    copy.deepcopy(latest_frontend_artifact.content)
                    if isinstance(latest_frontend_artifact.content, dict)
                    else {}
                )
                return {
                    "state_updates": {"frontend_code": {"artifact_ref": "frontend_code:v1"}},
                    "artifacts": [
                        {
                            "store_key": "frontend_code",
                            "artifact": Artifact(
                                artifact_id=f"frontend-{module_id}-module",
                                artifact_type="frontend_code",
                                producer=self.role,
                                content=cached_content,
                                metadata={
                                    "generation": {
                                        "source": "llm",
                                        "provider": generation.get("provider", ""),
                                        "model": generation.get("model", ""),
                                        "cached_from_version": latest_frontend_artifact.version,
                                    }
                                },
                            ),
                        }
                    ],
                    "messages": [
                        AgentMessage(
                            sender=self.role,
                            receiver="qa",
                            content=f"Frontend {module_name} module ready for QA validation.",
                            msg_type=MessageType.TASK,
                            artifacts=[f"frontend-{module_id}-module:v1"],
                        )
                    ],
                    "usage": {"tokens": 0, "api_calls": 0},
                }

        # Inject api_contract from upstream architect agent.
        api_contract_art = context.get_latest_artifact("api_contract")
        api_contract = api_contract_art.content if api_contract_art is not None else {}
        endpoints = api_contract.get("endpoints", [])
        base_url = api_contract.get("base_url", fe.get("base_url", "http://localhost:8080"))

        # Determine a generic login URL hint from architect's contract (if relevant to module)
        login_ep = next((e for e in endpoints if "login" in e.get("path", "").lower()), None)
        login_url = f"{base_url}{login_ep.get('path', '/api/login')}" if login_ep else f"{base_url}/api/login"

        fallback_code_bundle = {
            app_root: (
                "import React, { useState } from 'react';\n"
                "\n"
                "function App() {\n"
                "  const [token, setToken] = useState(localStorage.getItem('token'));\n"
                "  const [username, setUsername] = useState('');\n"
                "  const [password, setPassword] = useState('');\n"
                "  const [error, setError] = useState('');\n"
                "\n"
                "  const handleLogin = async (e) => {\n"
                "    e.preventDefault();\n"
                "    try {\n"
                f"      const res = await fetch('{login_url}', {{\n"
                "        method: 'POST',\n"
                "        headers: { 'Content-Type': 'application/json' },\n"
                "        body: JSON.stringify({ username, password }),\n"
                "      });\n"
                "      if (!res.ok) throw new Error('Login failed');\n"
                "      const data = await res.json();\n"
                "      localStorage.setItem('token', data.token);\n"
                "      setToken(data.token);\n"
                "    } catch (err) {\n"
                "      setError(err.message);\n"
                "    }\n"
                "  };\n"
                "\n"
                "  if (token) return <div><h1>Welcome!</h1><button onClick={() => { localStorage.removeItem('token'); setToken(null); }}>Logout</button></div>;\n"
                "\n"
                "  return (\n"
                "    <div>\n"
                f"      <h1>{project_name}</h1>\n"
                "      {error && <p style={{color:'red'}}>{error}</p>}\n"
                "      <form onSubmit={handleLogin}>\n"
                "        <input placeholder='Username' value={username} onChange={e => setUsername(e.target.value)} />\n"
                "        <input type='password' placeholder='Password' value={password} onChange={e => setPassword(e.target.value)} />\n"
                "        <button type='submit'>Login</button>\n"
                "      </form>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
                "\n"
                "export default App;\n"
            )
        }
        fallback_frontend_artifact = {
            "module": module_id,
            "changed_files": list(fallback_code_bundle.keys()),
            "code_bundle": fallback_code_bundle,
            "build_notes": {"build_status": "simulated_pass"},
            "ui_state_notes": {"loading_error_empty": "covered_in_fallback"},
        }

        api_section = ""
        if endpoints:
            api_section = (
                "\nBACKEND API CONTRACT (you MUST call these exact paths with these exact field names):\n"
                + json.dumps(endpoints, indent=2)
                + f"\nBase URL: {base_url}\n"
                "CRITICAL: Use the path, method, request_fields, and response_fields above exactly.\n"
                "Do NOT invent different endpoint paths or field names.\n"
            )
        else:
            api_section = (
                "\n(No API contract from Architect yet — infer endpoints from functional requirements "
                "and architecture context. Use reasonable REST conventions.)\n"
            )

        backend_art = context.get_latest_artifact("backend_code")
        backend_files_section = ""
        if backend_art is not None and isinstance(backend_art.content, dict):
            bfiles = list(backend_art.content.get("code_bundle", {}).keys())
            if bfiles:
                backend_files_section = (
                    f"\nBACKEND FILES PRODUCED BY BACKEND AGENT: {bfiles}\n"
                    "These files are the backend implementation. Your frontend must align to the same API contract.\n"
                )

        fe_framework_line = (
            f"{fe.get('framework', 'React')} {fe.get('framework_version', '')}, "
            f"{fe.get('scaffolding_tool', 'Create React App')} {fe.get('scaffolding_version', '')}"
        ).strip(", ")

        qa_feedback_section = _build_frontend_qa_feedback(context) if _qa_rework_needed(context) else ""

        frontend_artifact, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                f"Generate a frontend {module_id} module code_bundle JSON for the "
                f"{project_name} project using scaffold-overlay mode.\n"
                + qa_feedback_section
                + "\n"
                "SCAFFOLD CONTEXT:\n"
                f"- {fe_framework_line}\n"
                f"- Entry: {entry_file} renders <App /> — you MUST override {app_root}\n"
                f"- Available packages:\n  - {deps_str}\n"
                "- NO pre-existing application components — design everything from scratch\n"
                + api_section
                + backend_files_section
                + "\n"
                "FUNCTIONAL REQUIREMENTS:\n"
                + fr_lines
                + "\n"
                "\n"
                "YOUR DESIGN DECISIONS:\n"
                "- Component names, file structure, page/view organization\n"
                "- State management approach (local state, React Context, etc.)\n"
                "- Routing approach (React Router or conditional rendering)\n"
                "- Styling approach (inline styles, CSS classes, etc.)\n"
                "\n"
                "FILE RULES:\n"
                f"- Generate {min_files}-{max_files} files, all under src/\n"
                f"- MANDATORY: include {app_root} in code_bundle\n"
                "- Every import must be a package from package.json or a relative file in the bundle\n"
                "- Use functional components and React hooks only\n"
                "- Handle loading states and error messages for API calls\n"
            ),
            fallback_payload=fallback_frontend_artifact,
            fallback_usage={"tokens": 610, "api_calls": 1},
            required_keys=[
                "module",
                "changed_files",
                "code_bundle",
                "build_notes",
                "ui_state_notes",
            ],
            extra_output_constraints=[
                f"- Generate {min_files}-{max_files} files; all paths must start with src/.",
                "- code_bundle keys must exactly match changed_files.",
                f"- MANDATORY: {app_root} must be included in code_bundle.",
                "- Every import must resolve to a package in package.json or a relative file in the bundle.",
                "- Do NOT import packages not in the scaffold (no antd, no axios, no react-router unless in package.json).",
                "- Use functional components and hooks only; no class components.",
                "- Use plain JavaScript files (.js) compatible with react-scripts.",
                "- Avoid markdown and explanations; JSON data only.",
            ],
            retry_on_invalid_json=True,
            json_retry_attempts=3,
            max_output_tokens_override=4000,
        )
        return {
            "state_updates": {"frontend_code": {"artifact_ref": "frontend_code:v1"}},
            "artifacts": [
                {
                    "store_key": "frontend_code",
                    "artifact": Artifact(
                        artifact_id=f"frontend-{module_id}-module",
                        artifact_type="frontend_code",
                        producer=self.role,
                        content=frontend_artifact,
                        metadata={"generation": generation_meta},
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="qa",
                    content=f"Frontend {module_name} module ready for QA validation.",
                    msg_type=MessageType.TASK,
                    artifacts=[f"frontend-{module_id}-module:v1"],
                )
            ],
            "usage": usage,
        }
