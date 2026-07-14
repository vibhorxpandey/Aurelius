"""HypothesisValidatorAgent — feasibility + policy pre-screening.

Reuses Aurelius's existing ``screening.screen_topic`` (the restricted-domain heuristic and
policy) so the DAG applies the *same* admission rules as the host-driven and linear
autonomous modes. Sets ``state['approved']``; a False value routes the graph to an early
finish (see ``research_graph``).
"""
from __future__ import annotations

import json
from typing import Any

from ...orchestration.state import ResearchState
from ...tools import screening
from ..base import ResearchAgent

_SYSTEM = (
    "You are a Principal Investigator screening a hypothesis for feasibility. You admit only "
    "hypotheses that can be grounded in empirical, quantitative, web-verifiable evidence."
)


class HypothesisValidatorAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Hypothesis Validator",
            role="Screen the hypothesis for policy fit and feasibility",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        topic = state.get("topic", "")
        hypothesis = state.get("hypothesis", "")

        # 1) Deterministic policy heuristic (no key needed) — the authoritative gate.
        screen = screening.screen_topic(topic)
        if screen["likely_restricted"]:
            state["approved"] = False
            state["screen_reason"] = (
                f"Topic flagged under restricted domain '{screen['matched_domain']}'."
            )
            return self.log(state, "validate", state["screen_reason"], {"approved": False})

        # 2) Optional LLM feasibility refinement (only tightens, never loosens, the gate).
        raw = self._llm(
            _SYSTEM,
            f"Topic: {topic}\nHypothesis: {hypothesis}\n\nPolicy:\n"
            f"{json.dumps(screening.get_research_policy(), indent=2)}\n\n"
            'Respond with ONLY JSON: {"feasible": true/false, "reason": "<one sentence>"}',
            temperature=0.0,
            max_tokens=200,
        )
        approved, reason = True, "Passed policy heuristic."
        if raw:
            verdict = _parse_verdict(raw)
            approved = verdict.get("feasible", True)
            reason = verdict.get("reason", reason)

        state["approved"] = approved
        state["screen_reason"] = reason
        return self.log(state, "validate", reason, {"approved": approved, "llm": raw is not None})


def _parse_verdict(raw: Any) -> dict:
    try:
        start, end = raw.find("{"), raw.rfind("}")
        return json.loads(raw[start : end + 1])
    except (ValueError, TypeError):
        return {}
