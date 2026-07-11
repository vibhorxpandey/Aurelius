"""LaTeX writing: a compile-ready article skeleton, mirroring drafting.py's
draft_outline/save_draft pattern for the Markdown workflow."""
from __future__ import annotations

from typing import Any, Dict

from ..config import resolve_output_path

LATEX_OUTLINE = r"""\documentclass[11pt]{{article}}
\usepackage[margin=1in]{{geometry}}
\usepackage{{amsmath,amssymb}}
\usepackage{{graphicx}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{natbib}}

\title{{{title}}}
\author{{}}
\date{{}}

\begin{{document}}
\maketitle

\begin{{abstract}}
150-250 words: aim, method, key findings, implications.
\end{{abstract}}

\section{{Introduction}}
Context and motivation; the gap; the research question; what this work does.

\section{{Methods}}
Data sources and analytical techniques; enough detail to be reproducible.

\section{{Results}}
Findings with concrete, verifiable evidence (numbers, effect sizes, citations)
using \citep{{key}} / \citet{{key}} once entries exist in references.bib.

\section{{Discussion}}
Interpretation; comparison to prior work; implications.

\subsection{{Limitations}}
Honest constraints on the findings.

\section{{Conclusion}}
What was shown; why it matters; future directions.

\bibliographystyle{{plainnat}}
\bibliography{{references}}

\end{{document}}
"""

BIBTEX_STUB = """@article{key,
  author  = {Last, First},
  title   = {Title of the work},
  journal = {Journal name},
  year    = {YYYY},
  doi     = {10.xxxx/xxxxx}
}
"""


def latex_outline(topic: str) -> Dict[str, str]:
    """Return a compile-ready LaTeX article skeleton + a BibTeX entry stub (no LLM call).

    Uses natbib (not biblatex+biber) so it compiles with plain pdflatex + bibtex on
    any TeX distribution, with no extra backend toolchain required.

    Args:
        topic: The research topic; used as the document title.

    Returns {"topic": str, "latex": str, "bibtex_stub": str}
    """
    return {"topic": topic, "latex": LATEX_OUTLINE.format(title=topic), "bibtex_stub": BIBTEX_STUB}


def save_latex(content: str, filename: str = "paper.tex") -> Dict[str, Any]:
    """Save LaTeX (.tex) or BibTeX (.bib) source to the Aurelius output directory.

    Call this twice to produce a compilable pair -- once with a .tex filename for the
    document, once with a .bib filename for the bibliography.

    Args:
        content: The LaTeX or BibTeX source text.
        filename: Output filename (basename saved under the Aurelius output dir).
    """
    path = resolve_output_path(filename)
    path.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(path), "bytes": len(content.encode("utf-8"))}
