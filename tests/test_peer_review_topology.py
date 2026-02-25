from __future__ import annotations

import unittest

from agents import (
    ArchitectAgent,
    BackendDeveloperAgent,
    DevOpsAgent,
    FrontendDeveloperAgent,
    PeerReviewerAgent,
    ProductManagerAgent,
    QAAgent,
)
from core import Artifact, ReviewResult, ReviewStatus
from core.project_state import ProjectState
from core.orchestrator import Orchestrator
from topologies.peer_review import PeerReviewTopology


class AlwaysRejectReviewer(PeerReviewerAgent):
    """Force revision-needed outcome for all review targets."""

    def review(self, artifact: Artifact) -> ReviewResult:
        return ReviewResult(
            status=ReviewStatus.REVISION_NEEDED,
            comments=["forced rejection"],
            blocking_issues=["forced-issue"],
            reviewer=self.role,
        )


class PeerReviewTopologyTests(unittest.TestCase):
    def _register_common_agents(self, orchestrator: Orchestrator, reviewer: PeerReviewerAgent) -> None:
        orchestrator.register_agent(ProductManagerAgent("pm", "pm", []))
        orchestrator.register_agent(ArchitectAgent("architect", "arch", []))
        orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend", []))
        orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend", []))
        orchestrator.register_agent(reviewer)
        orchestrator.register_agent(QAAgent("qa", "qa", []))
        orchestrator.register_agent(DevOpsAgent("devops", "devops", []))

    def test_peer_review_flow_runs_revision_loops_and_completes(self) -> None:
        orchestrator = Orchestrator()
        reviewer = PeerReviewerAgent("reviewer", "reviewer", [])
        self._register_common_agents(orchestrator, reviewer)

        topology = PeerReviewTopology(orchestrator=orchestrator, max_revisions_per_target=1)
        turn_results = topology.run("peer-review-success")
        state = orchestrator.state

        reviewer_turns = [result for result in turn_results if result.agent_role == "reviewer"]
        revision_turns = [result for result in reviewer_turns if not result.success]
        approve_turns = [result for result in reviewer_turns if result.success]

        self.assertTrue(all(result.success or result.agent_role == "reviewer" for result in turn_results))
        self.assertEqual(12, len(turn_results))
        self.assertEqual(2, len(revision_turns))
        self.assertEqual(2, len(approve_turns))
        self.assertEqual(2, state.get_latest_artifact("backend_code").version)
        self.assertEqual(2, state.get_latest_artifact("frontend_code").version)
        self.assertIsNotNone(state.deployment)
        self.assertEqual(4380, state.total_tokens)
        self.assertEqual(8, state.total_api_calls)
        self.assertEqual(2, state.iteration)

    def test_peer_review_stops_when_revision_budget_exhausted(self) -> None:
        orchestrator = Orchestrator()
        reviewer = AlwaysRejectReviewer("reviewer", "reviewer", [])
        self._register_common_agents(orchestrator, reviewer)

        topology = PeerReviewTopology(orchestrator=orchestrator, max_revisions_per_target=1)
        turn_results = topology.run("peer-review-stop-on-exhausted-budget")
        state = orchestrator.state

        self.assertEqual("reviewer", turn_results[-1].agent_role)
        self.assertTrue(turn_results[-1].stop)
        self.assertIsNotNone(turn_results[-1].error)
        self.assertIsNone(state.deployment)

    def test_peer_review_can_continue_when_fail_fast_disabled(self) -> None:
        orchestrator = Orchestrator()
        reviewer = AlwaysRejectReviewer("reviewer", "reviewer", [])
        self._register_common_agents(orchestrator, reviewer)

        topology = PeerReviewTopology(
            orchestrator=orchestrator,
            max_revisions_per_target=0,
            fail_fast=False,
        )
        turn_results = topology.run("peer-review-continue-when-fail-fast-disabled")
        state = orchestrator.state

        self.assertTrue(any(result.agent_role == "qa" for result in turn_results))
        self.assertTrue(any(result.agent_role == "devops" for result in turn_results))
        self.assertIsNotNone(state.deployment)


if __name__ == "__main__":
    unittest.main()
