"""CitationVerifierAgent — the single most important reuse seam in Phase 1.

It does **not** reimplement any verification logic: it hands the candidate citations and
load-bearing claims to Aurelius's existing, battle-tested ``ledger.verify_claims`` (which
routes citations to the retraction-aware ``scholarly.verify_citation`` and claims to an
academic web search), then writes the resulting scored Evidence Ledger and a
``STATUS:`` report into the research state.
"""
from __future__ import annotations

from typing import List

from ...orchestration.state import ResearchState
from ...tools import ledger
from ..base import ResearchAgent


class CitationVerifierAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="Citation Verifier",
            role="Verify every candidate citation/claim against the scholarly indexes",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        items: List[str] = list(state.get("candidate_citations", []))
        hypothesis = state.get("hypothesis", "")
        if hypothesis:
            items.append(hypothesis)  # verify the load-bearing claim too
        items = [i for i in items if i.strip()]

        if not items:
            state["verification_report"] = {
                "verification_score": 0.0,
                "counts": {"total": 0},
                "markdown": "STATUS: REJECTED\n\nNo citations or claims to verify.",
            }
            return self.log(state, "verify", "no items to verify", {"total": 0})

        result = ledger.verify_claims(items)  # <-- reuse existing tool, no new logic
        state["evidence_ledger"] = result["ledger"]
        state["verification_report"] = {
            "verification_score": result["verification_score"],
            "counts": result["counts"],
            "markdown": result["markdown"],
        }
        return self.log(
            state, "verify", result["markdown"],
            {"score": result["verification_score"], "counts": result["counts"]},
        )
