"""ExperimentDesignerAgent — turn a hypothesis into a reproducible analysis protocol."""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ..base import ResearchAgent

_SYSTEM = (
    "You are a research methodologist. You design reproducible, pre-registered-style analysis "
    "protocols: data sources, variables, method, and the pre-specified success criteria."
)


class ExperimentDesignerAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Experiment Designer",
            role="Design a reproducible analysis protocol for the hypothesis",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        raw = self._llm(
            _SYSTEM,
            f"Hypothesis: {state.get('hypothesis','')}\n"
            f"Topic: {state.get('topic','')}\n\n"
            "Write a concise, reproducible analysis plan: (1) data sources, (2) variables, "
            "(3) method/statistical test, (4) pre-specified success criteria. Markdown.",
            temperature=0.3,
            max_tokens=800,
        )
        state["experiment_design"] = raw or "(experiment design skipped — no LLM key)"
        return self.log(state, "design_experiment", state["experiment_design"], {"llm": raw is not None})
