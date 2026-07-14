"""AdversarialReviewerAgent — simulate a hostile peer reviewer.

Given the hypothesis, evidence ledger, and (if present) the draft, it stress-tests the work:
unsupported leaps, alternative explanations, methodological weaknesses. Purely additive —
it writes a review into the state and never edits the underlying claims.
"""
from __future__ import annotations

import json

from ...orchestration.state import ResearchState
from ..base import ResearchAgent

_SYSTEM = (
    "You are a demanding, fair peer reviewer (Reviewer 2). You look for unsupported claims, "
    "confounds, alternative explanations, and weak methodology, and you state them plainly."
)


class AdversarialReviewerAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Adversarial Reviewer",
            role="Stress-test the work as a hostile peer reviewer",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        report = state.get("verification_report", {})
        raw = self._llm(
            _SYSTEM,
            f"Hypothesis: {state.get('hypothesis','')}\n\n"
            f"Verification summary: {json.dumps(report.get('counts', {}))}\n\n"
            f"Draft (may be empty):\n{state.get('paper_draft','')[:4000]}\n\n"
            "Write a concise adversarial review: the 3-5 strongest objections and, for each, "
            "what evidence would answer it.",
            temperature=0.4,
            max_tokens=800,
        )
        state["adversarial_review"] = raw or "(adversarial review skipped — no LLM key)"
        return self.log(state, "adversarial_review", state["adversarial_review"], {"llm": raw is not None})
