"""TheoryGeneratorAgent — Tree-of-Thoughts hypothesis generation (ARCHITECTURE.md §1.2).

Explores several candidate hypotheses/theories in parallel branches, rates each for
feasibility and originality, and selects the strongest as the working hypothesis. Falls
back to a deterministic placeholder hypothesis when no LLM key is configured so the graph
still advances.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from ...orchestration.state import ResearchState
from ..base import ResearchAgent

_SYSTEM = (
    "You are a creative but rigorous scientist. You generate testable, falsifiable "
    "hypotheses grounded in evidence, and you favor divergent thinking over the obvious."
)


class TheoryGeneratorAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Theory Generator",
            role="Generate and rank candidate hypotheses via Tree-of-Thoughts",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        topic = state.get("topic", "")
        literature = state.get("literature_summary", "")
        raw = self._llm(
            _SYSTEM,
            f"Topic: {topic}\n\nLiterature summary:\n{literature}\n\n"
            "Generate 3-5 alternative, testable hypotheses. For each, give a short "
            "'statement', an integer 'feasibility' (1-10) and 'originality' (1-10). "
            "Respond with ONLY a JSON array of objects with those keys.",
            temperature=0.7,
            max_tokens=800,
        )
        theories = _parse_theories(raw)
        if theories:
            best = max(theories, key=lambda t: t.get("feasibility", 0) + t.get("originality", 0))
            state["hypothesis"] = best.get("statement", "")
        elif not state.get("hypothesis"):
            state["hypothesis"] = (
                f"Investigate a measurable, evidence-grounded relationship within: {topic}."
            )
        state["alternative_hypotheses"] = theories
        return self.log(
            state, "generate_theories", state.get("hypothesis", ""),
            {"n_theories": len(theories), "llm": raw is not None},
        )


def _parse_theories(raw: Any) -> List[Dict[str, Any]]:
    if not raw:
        return []
    try:
        start, end = raw.find("["), raw.rfind("]")
        data = json.loads(raw[start : end + 1])
        return [t for t in data if isinstance(t, dict) and t.get("statement")]
    except (ValueError, TypeError):
        return []
