"""MethodologyAuditorAgent — detect p-hacking / data-dredging in the analysis.

Runs the dependency-free static auditor (``sandbox.methodology.audit_methodology``) over the
generated code and design, then optionally asks the LLM to add qualitative concerns. Writes
a structured methodology report into the state; a high risk score is surfaced (and folded
into the proof-of-rigor attestation) rather than silently ignored.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ...sandbox import methodology
from ..base import ResearchAgent

_SYSTEM = (
    "You are a rigorous methodologist reviewing an analysis for questionable research "
    "practices (p-hacking, data dredging, HARKing, optional stopping, reproducibility gaps)."
)


class MethodologyAuditorAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Methodology Auditor",
            role="Detect p-hacking / data-dredging and reproducibility issues",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        code = state.get("experiment_code", "")
        design = state.get("experiment_design", "")
        report = methodology.audit_methodology(code, design)  # static, always runs

        # Optional qualitative pass — appended, never overrides the static findings.
        note = self._llm(
            _SYSTEM,
            f"Design:\n{design[:1500]}\n\nCode:\n{code[:2500]}\n\n"
            f"Static auditor flagged: {[f['signal'] for f in report['findings']]}. "
            "Add any additional methodological concerns in 2-4 short bullet points, or say "
            "'no further concerns'.",
            temperature=0.2, max_tokens=400,
        )
        report["llm_notes"] = note
        state["methodology_report"] = report
        return self.log(
            state, "audit_methodology", report["summary"],
            {"risk": report["risk"], "risk_score": report["risk_score"],
             "n_findings": len(report["findings"])},
        )
