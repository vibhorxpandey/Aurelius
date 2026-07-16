"""LaTeX writing: compile-ready skeletons, mirroring drafting.py's
draft_outline/save_draft pattern for the Markdown workflow.

Three templates (Phase 4), all deliberately buildable with plain pdflatex + bibtex on any
TeX distribution (no ieeetran/revtex/journal-class downloads required):
  * ``article``   — single-column preprint (the arXiv default look)
  * ``twocolumn`` — two-column conference/IEEE-style layout
  * ``report``    — chaptered long-form (theses, extended technical reports)
"""
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

LATEX_TWOCOLUMN = r"""\documentclass[10pt,twocolumn]{{article}}
\usepackage[margin=0.75in]{{geometry}}
\usepackage{{amsmath,amssymb}}
\usepackage{{graphicx}}
\usepackage[hidelinks]{{hyperref}}
\usepackage{{natbib}}
\setlength{{\columnsep}}{{0.25in}}

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
Findings with concrete, verifiable evidence using \citep{{key}} / \citet{{key}}.

\section{{Discussion}}
Interpretation; comparison to prior work; implications; limitations.

\section{{Conclusion}}
What was shown; why it matters; future directions.

\bibliographystyle{{plainnat}}
\bibliography{{references}}

\end{{document}}
"""

LATEX_REPORT = r"""\documentclass[11pt]{{report}}
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

\tableofcontents

\chapter{{Introduction}}
Context and motivation; the gap; the research question; what this work does.

\chapter{{Background}}
Prior work and key concepts, cited with \citep{{key}} / \citet{{key}}.

\chapter{{Methods}}
Data sources and analytical techniques; enough detail to be reproducible.

\chapter{{Results}}
Findings with concrete, verifiable evidence (numbers, effect sizes, citations).

\chapter{{Discussion}}
Interpretation; comparison to prior work; implications; limitations.

\chapter{{Conclusion}}
What was shown; why it matters; future directions.

\bibliographystyle{{plainnat}}
\bibliography{{references}}

\end{{document}}
"""

TEMPLATES: Dict[str, str] = {
    "article": LATEX_OUTLINE,
    "twocolumn": LATEX_TWOCOLUMN,
    "report": LATEX_REPORT,
}

BIBTEX_STUB = """@article{key,
  author  = {Last, First},
  title   = {Title of the work},
  journal = {Journal name},
  year    = {YYYY},
  doi     = {10.xxxx/xxxxx}
}
"""


def latex_outline(topic: str, template: str = "article") -> Dict[str, str]:
    """Return a compile-ready LaTeX skeleton + a BibTeX entry stub (no LLM call).

    Uses natbib (not biblatex+biber) so every template compiles with plain pdflatex +
    bibtex on any TeX distribution, with no extra backend toolchain required.

    Args:
        topic: The research topic; used as the document title.
        template: "article" (single-column preprint, arXiv default), "twocolumn"
            (conference/IEEE-style), or "report" (chaptered long-form). Unknown names
            fall back to "article".

    Returns {"topic": str, "template": str, "latex": str, "bibtex_stub": str}
    """
    name = template if template in TEMPLATES else "article"
    return {
        "topic": topic,
        "template": name,
        "latex": TEMPLATES[name].format(title=topic),
        "bibtex_stub": BIBTEX_STUB,
    }


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
