"""DraftPaperAgent — compile the verified material into a paper draft.

Reuses ``drafting.draft_outline`` for the canonical academic scaffold and
``drafting.save_draft`` for persistence. The draft is written from *verified* evidence
only: the verification report is passed to the model with an instruction to include no
claim the Evidence Ledger did not substantiate.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ...tools import drafting
from ..base import ResearchAgent

_SYSTEM = (
    "You are a rigorous academic writer. You write only what the provided verified evidence "
    "supports and never invent data or citations."
)


class DraftPaperAgent(ResearchAgent):
    def __init__(self, save: bool = True, **kwargs) -> None:
        super().__init__(
            name="Draft Paper",
            role="Compile verified material into a Markdown paper draft",
            **kwargs,
        )
        self.save = save

    def execute(self, state: ResearchState) -> ResearchState:
        topic = state.get("topic", "")
        outline = drafting.draft_outline(topic)["outline"]
        report = state.get("verification_report", {})
        raw = self._llm(
            _SYSTEM,
            f"Topic: {topic}\nHypothesis: {state.get('hypothesis','')}\n\n"
            f"Literature summary:\n{state.get('literature_summary','')}\n\n"
            f"Verified evidence ledger (Markdown):\n{report.get('markdown','')}\n\n"
            f"Fill in this outline. Include ONLY claims the ledger substantiates.\n\n{outline}",
            temperature=0.3,
            max_tokens=3000,
        )
        draft = raw or outline  # fall back to the empty scaffold with no LLM key
        state["paper_draft"] = draft
        meta = {"llm": raw is not None}
        if self.save:
            saved = drafting.save_draft(draft, filename=f"draft_{state.get('session_id','session')}.md")
            meta["path"] = saved["path"]
        return self.log(state, "draft_paper", draft, meta)
