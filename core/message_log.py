"""Message log for traceable cross-agent communication."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import AgentMessage


@dataclass
class MessageLog:
    """Ordered message log with query helpers."""

    messages: list[AgentMessage] = field(default_factory=list)

    def append(self, message: AgentMessage) -> None:
        self.messages.append(message)

    def extend(self, messages: list[AgentMessage]) -> None:
        self.messages.extend(messages)

    def by_sender(self, sender: str) -> list[AgentMessage]:
        return [message for message in self.messages if message.sender == sender]

    def by_receiver(self, receiver: str) -> list[AgentMessage]:
        return [message for message in self.messages if message.receiver == receiver]

    def recent(self, limit: int = 10) -> list[AgentMessage]:
        if limit <= 0:
            return []
        return self.messages[-limit:]

    def to_dict(self) -> list[dict[str, object]]:
        return [message.to_dict() for message in self.messages]

    @classmethod
    def from_dict(cls, data: list[dict[str, object]]) -> "MessageLog":
        return cls(messages=[AgentMessage.from_dict(item) for item in data])

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> "MessageLog":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(payload)
