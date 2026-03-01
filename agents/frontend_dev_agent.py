"""Frontend developer agent implementation (rule-driven baseline)."""

from __future__ import annotations

import copy
from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class FrontendDeveloperAgent(BaseAgent):
    """Generate frontend code artifact for auth flows."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        latest_frontend_artifact = context.get_latest_artifact("frontend_code")
        if latest_frontend_artifact is not None:
            generation = latest_frontend_artifact.metadata.get("generation", {})
            if isinstance(generation, dict) and generation.get("source") == "llm":
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
                                artifact_id="frontend-auth-module",
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
                            content="Frontend auth module ready for QA validation.",
                            msg_type=MessageType.TASK,
                            artifacts=["frontend-auth-module:v1"],
                        )
                    ],
                    "usage": {"tokens": 0, "api_calls": 0},
                }

        fallback_code_bundle = {
            "src/App.js": (
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
                "      const res = await fetch('http://localhost:8080/authenticate/login', {\n"
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
                "      <h1>StayBooking Login</h1>\n"
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
            "module": "auth",
            "changed_files": list(fallback_code_bundle.keys()),
            "code_bundle": fallback_code_bundle,
            "build_notes": {"build_status": "simulated_pass"},
            "ui_state_notes": {"loading_error_empty": "covered_in_fallback"},
        }
        frontend_artifact, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                "Generate a frontend auth module code_bundle JSON for the StayBooking project using scaffold-overlay mode.\n"
                "\n"
                "SCAFFOLD CONTEXT:\n"
                "- React 18, Create React App 5.0.1\n"
                "- Entry: src/index.js renders <App /> — you MUST override src/App.js\n"
                "- Available packages: react, react-dom, react-scripts, web-vitals (no other packages)\n"
                "- NO pre-existing application components — design everything from scratch\n"
                "\n"
                "FUNCTIONAL REQUIREMENTS:\n"
                "- Login page: POST /authenticate/login with {username, password}, store JWT, show main content\n"
                "- Register page: POST /authenticate/register with {username, password, role}, role = GUEST or HOST\n"
                "- Route protection: unauthenticated users see Login/Register, authenticated users see main content\n"
                "- Backend base URL: http://localhost:8080\n"
                "\n"
                "YOUR DESIGN DECISIONS:\n"
                "- Component names, file structure, state management approach\n"
                "- Routing approach (React Router or conditional rendering)\n"
                "- Styling approach (inline styles, CSS classes, etc.)\n"
                "\n"
                "FILE RULES:\n"
                "- Generate 2-5 files, all under src/\n"
                "- MANDATORY: include src/App.js in code_bundle\n"
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
                "- Generate 2-5 files; all paths must start with src/.",
                "- code_bundle keys must exactly match changed_files.",
                "- MANDATORY: src/App.js must be included in code_bundle.",
                "- Every import must resolve to a package in package.json or a relative file in the bundle.",
                "- Do NOT import packages not in the scaffold (no antd, no axios, no react-router unless in package.json).",
                "- Use functional components and hooks only; no class components.",
                "- Use plain JavaScript files (.js) compatible with react-scripts.",
                "- Avoid markdown and explanations; JSON data only.",
            ],
            retry_on_invalid_json=True,
            json_retry_attempts=2,
            max_output_tokens_override=3000,
        )
        return {
            "state_updates": {"frontend_code": {"artifact_ref": "frontend_code:v1"}},
            "artifacts": [
                {
                    "store_key": "frontend_code",
                    "artifact": Artifact(
                        artifact_id="frontend-auth-module",
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
                    content="Frontend auth module ready for QA validation.",
                    msg_type=MessageType.TASK,
                    artifacts=["frontend-auth-module:v1"],
                )
            ],
            "usage": usage,
        }
