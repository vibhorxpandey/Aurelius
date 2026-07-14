"""CodeGeneratorAgent — write the analysis code for the designed experiment.

The code is *generated*, not executed. Execution belongs to the Phase 2 sandbox
(SandboxExecutorAgent, currently a placeholder), so this agent never runs untrusted code.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ..base import ResearchAgent

_SYSTEM = (
    "You are a scientific programmer. You write clean, self-contained Python analysis code "
    "with clearly stated data assumptions. You never fabricate data."
)


class CodeGeneratorAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Code Generator",
            role="Generate analysis code for the experiment design",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        design = state.get("experiment_design", "")
        raw = self._llm(
            _SYSTEM,
            f"Analysis plan:\n{design}\n\n"
            "Write a single self-contained Python script implementing this analysis. "
            "State data-loading assumptions in comments. Return ONLY the code in a ```python block.",
            temperature=0.2,
            max_tokens=1200,
        )
        state["experiment_code"] = raw or "# (code generation skipped — no LLM key)"
        return self.log(state, "generate_code", state["experiment_code"], {"llm": raw is not None})
