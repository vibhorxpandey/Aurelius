"""PreprintPackagerAgent — assemble a submission-ready preprint bundle (Phase 4).

Wraps ``tools.preprint.build_submission_package``: compile-ready LaTeX, the verified draft,
a DOI-backed references.bib built from the Evidence Ledger, metadata, and a server-specific
checklist, zipped for upload. It does **not** submit — preprint servers require human
endorsement/moderation, so the final step is deliberately left to the researcher.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ...tools import preprint
from ..base import ResearchAgent


class PreprintPackagerAgent(ResearchAgent):
    def __init__(self, server: str = "arxiv", **kwargs) -> None:
        super().__init__(
            name="Preprint Packager",
            role="Assemble a submission-ready preprint bundle (manual submission by design)",
            **kwargs,
        )
        self.server = server

    def execute(self, state: ResearchState) -> ResearchState:
        if not state.get("paper_draft") and not state.get("latex"):
            state["preprint_package"] = {"ok": False, "note": "No draft/LaTeX to package."}
            return self.log(state, "skipped", "No draft or LaTeX in state - nothing to package.", {})

        pkg = preprint.build_submission_package(
            topic=state.get("topic", ""),
            session_id=state.get("session_id", ""),
            paper_draft=state.get("paper_draft", ""),
            latex=state.get("latex", ""),
            evidence_ledger=state.get("evidence_ledger", []),
            proof=state.get("proof", {}),
            server=self.server,
        )
        state["preprint_package"] = pkg
        return self.log(state, "package_preprint", pkg["note"],
                        {"server": pkg["server"], "zip": pkg["zip"], "files": len(pkg["files"])})
