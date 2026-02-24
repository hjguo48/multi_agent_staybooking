"""Minimal orchestrator runtime for agent turn scheduling and state updates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.base_agent import BaseAgent

from .models import AgentMessage, Artifact, MessageType
from .project_state import ProjectState


@dataclass
class TurnResult:
    """Execution summary for one agent turn."""

    agent_role: str
    success: bool
    artifacts_registered: list[str] = field(default_factory=list)
    messages_emitted: int = 0
    usage_tokens: int = 0
    usage_api_calls: int = 0
    updated_fields: list[str] = field(default_factory=list)
    stop: bool = False
    error: str | None = None


class Orchestrator:
    """Manage agent lifecycle, message routing, and shared project state."""

    STATE_UPDATE_FIELDS = {
        "requirements",
        "architecture",
        "backend_code",
        "frontend_code",
        "qa_report",
        "deployment",
    }

    def __init__(self, state: ProjectState | None = None) -> None:
        self.state = state or ProjectState()
        self.agents: dict[str, BaseAgent] = {}
        self.turn_history: list[TurnResult] = []

    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent by role."""
        self.agents[agent.role] = agent

    def get_agent(self, role: str) -> BaseAgent:
        if role not in self.agents:
            raise KeyError(f"Agent not registered: {role}")
        return self.agents[role]

    def route_message(self, message: AgentMessage) -> None:
        """Route a message and persist it in global message log."""
        if message.receiver == "broadcast":
            for role, agent in self.agents.items():
                if role != message.sender:
                    agent.receive(message)
        elif message.receiver in self.agents:
            self.agents[message.receiver].receive(message)
        self.state.add_message(message)

    def _coerce_message(self, payload: AgentMessage | dict[str, Any]) -> AgentMessage:
        if isinstance(payload, AgentMessage):
            return payload
        return AgentMessage.from_dict(payload)

    def _coerce_artifact(self, payload: Artifact | dict[str, Any]) -> Artifact:
        if isinstance(payload, Artifact):
            return payload
        return Artifact.from_dict(payload)

    def _apply_state_updates(self, updates: dict[str, Any]) -> list[str]:
        updated_fields: list[str] = []
        for key, value in updates.items():
            if key not in self.STATE_UPDATE_FIELDS:
                continue
            setattr(self.state, key, value)
            updated_fields.append(key)
        if updated_fields:
            self.state.touch()
        return updated_fields

    def _register_artifacts(
        self, role: str, artifact_entries: list[dict[str, Any] | Artifact]
    ) -> list[str]:
        refs: list[str] = []
        for entry in artifact_entries:
            if isinstance(entry, Artifact):
                artifact = entry
                store_key = artifact.artifact_type
            else:
                store_key = entry.get("store_key")
                artifact_payload = entry.get("artifact", entry)
                artifact = self._coerce_artifact(artifact_payload)

            if not store_key:
                raise ValueError("Artifact entry must provide store_key or artifact_type")

            if not artifact.producer:
                artifact.producer = role
            stored = self.state.register_artifact(store_key, artifact)
            refs.append(f"{store_key}:v{stored.version}")
        return refs

    def run_turn(self, role: str) -> TurnResult:
        """Run one agent turn and apply produced updates/messages/artifacts."""
        agent = self.get_agent(role)
        try:
            output = agent.act(self.state)
        except Exception as exc:  # pragma: no cover - covered by integration behavior
            result = TurnResult(agent_role=role, success=False, error=str(exc))
            self.turn_history.append(result)
            return result

        output = output or {}
        usage = output.get("usage", {})
        tokens = int(usage.get("tokens", 0))
        api_calls = int(usage.get("api_calls", 0))
        if tokens or api_calls:
            self.state.update_usage(token_delta=tokens, api_call_delta=api_calls)

        updated_fields = self._apply_state_updates(output.get("state_updates", {}))
        artifact_refs = self._register_artifacts(role, output.get("artifacts", []))

        emitted_messages = 0
        for raw_message in output.get("messages", []):
            message = self._coerce_message(raw_message)
            if not message.sender:
                message.sender = role
            self.route_message(message)
            emitted_messages += 1

        result = TurnResult(
            agent_role=role,
            success=True,
            artifacts_registered=artifact_refs,
            messages_emitted=emitted_messages,
            usage_tokens=tokens,
            usage_api_calls=api_calls,
            updated_fields=updated_fields,
            stop=bool(output.get("stop", False)),
        )
        self.turn_history.append(result)
        return result

    def run_sequence(self, roles: list[str]) -> list[TurnResult]:
        """Run a fixed sequence of agent roles."""
        results: list[TurnResult] = []
        for role in roles:
            result = self.run_turn(role)
            results.append(result)
            if not result.success or result.stop:
                break
        return results

    def kickoff(self, receiver: str, content: str) -> AgentMessage:
        """Send initial orchestrator task message to start a workflow."""
        message = AgentMessage(
            sender="orchestrator",
            receiver=receiver,
            content=content,
            msg_type=MessageType.TASK,
        )
        self.route_message(message)
        return message
