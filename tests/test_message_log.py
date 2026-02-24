from __future__ import annotations

import unittest

from core import AgentMessage, MessageLog, MessageType


class MessageLogTests(unittest.TestCase):
    def test_append_and_filters(self) -> None:
        log = MessageLog()
        log.append(
            AgentMessage(
                sender="orchestrator",
                receiver="pm",
                content="start",
                msg_type=MessageType.TASK,
            )
        )
        log.append(
            AgentMessage(
                sender="pm",
                receiver="architect",
                content="requirements-ready",
                msg_type=MessageType.APPROVAL,
            )
        )

        self.assertEqual(2, len(log.messages))
        self.assertEqual(1, len(log.by_sender("pm")))
        self.assertEqual(1, len(log.by_receiver("architect")))

    def test_recent_window(self) -> None:
        log = MessageLog()
        for idx in range(5):
            log.append(
                AgentMessage(
                    sender="agent",
                    receiver="broadcast",
                    content=f"msg-{idx}",
                    msg_type=MessageType.STATUS,
                )
            )

        recent = log.recent(limit=2)
        self.assertEqual(2, len(recent))
        self.assertEqual("msg-3", recent[0].content)
        self.assertEqual("msg-4", recent[1].content)


if __name__ == "__main__":
    unittest.main()
