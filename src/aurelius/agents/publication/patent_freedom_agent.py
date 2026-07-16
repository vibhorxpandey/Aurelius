"""PatentFreedomAgent — screen the hypothesis for potentially-overlapping patents (Phase 5).

Wraps ``tools.patents.patent_freedom_report`` (PatentsView when a key is configured, web
fallback otherwise, honest 'insufficient data' when neither is available). The verdict and
disclaimer land in ``state['patent_report']`` — this is a screening aid, never legal advice.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ...tools import patents
from ..base import ResearchAgent


class PatentFreedomAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Patent Freedom",
            role="Screen for potentially-overlapping patents (not legal advice)",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        report = patents.patent_freedom_report(
            hypothesis=state.get("hypothesis", ""), topic=state.get("topic", "")
        )
        state["patent_report"] = report
        return self.log(state, "patent_freedom", report["note"],
                        {"verdict": report["verdict"], "backend": report["backend"],
                         "hits": len(report["hits"])})
