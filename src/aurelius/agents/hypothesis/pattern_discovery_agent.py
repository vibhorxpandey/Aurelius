"""PatternDiscoveryAgent — surface gaps, tensions, and under-explored angles.

Complements the TheoryGenerator: where that agent proposes hypotheses, this one names the
research *gaps* in the current literature so the swarm can aim at something novel.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ..base import ResearchAgent

_SYSTEM = (
    "You are a research strategist who identifies gaps and contradictions in a body of work "
    "— what has NOT been adequately studied, where findings conflict, what to investigate next."
)


class PatternDiscoveryAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Pattern Discovery",
            role="Identify research gaps and under-explored angles",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        topic = state.get("topic", "")
        literature = state.get("literature_summary", "")
        raw = self._llm(
            _SYSTEM,
            f"Topic: {topic}\n\nLiterature summary:\n{literature}\n\n"
            "List up to 5 concrete research gaps or unresolved tensions, one per line, "
            "each starting with '- '. Be specific and evidence-anchored.",
            temperature=0.5,
            max_tokens=500,
        )
        gaps = [
            line.lstrip("-* ").strip()
            for line in (raw or "").splitlines()
            if line.strip().startswith(("-", "*"))
        ]
        state["gaps"] = gaps
        return self.log(state, "discover_gaps", gaps, {"n_gaps": len(gaps), "llm": raw is not None})
