"""LatexFormatterAgent — attach a compile-ready LaTeX skeleton for the paper.

Reuses ``latex.latex_outline`` (natbib-based, compiles with plain pdflatex+bibtex) rather
than reimplementing a template. Phase 1 provides the skeleton + BibTeX stub; converting the
full Markdown draft to LaTeX body text is left to a later refinement.
"""
from __future__ import annotations

from ...orchestration.state import ResearchState
from ...tools import latex
from ..base import ResearchAgent


class LatexFormatterAgent(ResearchAgent):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            name="LaTeX Formatter",
            role="Produce a compile-ready LaTeX skeleton for the paper",
            **kwargs,
        )

    def execute(self, state: ResearchState) -> ResearchState:
        out = latex.latex_outline(state.get("topic", ""))
        state["latex"] = out["latex"]
        return self.log(state, "format_latex", out["latex"], {"has_bibtex_stub": True})
