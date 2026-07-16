"""Preprint submission packaging (Phase 4).

Builds a complete, submission-ready bundle for a preprint server — compile-ready LaTeX,
the verified draft, a DOI-backed references.bib, machine-readable metadata, and a
server-specific submission checklist — zipped for upload.

**Deliberately not auto-submission.** arXiv, bioRxiv, and medRxiv have no public
programmatic-submission APIs, require human endorsement/moderation, and (rightly) treat
bulk automated submissions as abuse. A project whose brand is research integrity should
not try to route around that. Aurelius therefore prepares everything up to the final
click — and the final click is the researcher's.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import get_output_dir
from .latex import latex_outline
from .scholarly import to_bibtex

SERVERS = ("arxiv", "biorxiv", "medrxiv")

_CHECKLISTS = {
    "arxiv": [
        "Create/log in to your arXiv account (https://arxiv.org).",
        "First submission in a category? You may need an ENDORSEMENT from an established "
        "author in that category - arXiv will tell you and give you an endorsement code to share.",
        "Pick the primary category (e.g. cs.LG, econ.EM, q-bio.QM) and any cross-lists.",
        "Choose a license (arXiv nonexclusive license is the common default).",
        "Upload the LaTeX source (paper.tex + references.bib), NOT a compiled PDF, so arXiv "
        "can build it; fix any compile errors it reports.",
        "Review arXiv's moderation hold policies; papers can be held for review.",
        "Disclose AI assistance per arXiv policy and your own standards.",
    ],
    "biorxiv": [
        "bioRxiv is for BIOLOGY preprints only - confirm the work is in scope.",
        "Create/log in at https://www.biorxiv.org and use 'Submit a Manuscript'.",
        "Upload the manuscript (PDF or Word compiled from this bundle) + any figures.",
        "Declare competing interests and (if applicable) ethics/IRB statements.",
        "Papers already published in a journal are NOT eligible.",
        "Screening takes ~24-48h before the preprint goes live.",
    ],
    "medrxiv": [
        "medRxiv is for HEALTH SCIENCES preprints - confirm scope.",
        "Health research requires ethics approval statements, trial registration numbers "
        "(if a trial), and funding/competing-interest declarations - prepare them first.",
        "Create/log in at https://www.medrxiv.org and submit the compiled manuscript.",
        "medRxiv screening is stricter and slower than bioRxiv (health claims risk).",
        "Do not submit work that could guide clinical practice without peer review caveats.",
    ],
}


def build_submission_package(
    topic: str,
    session_id: str,
    paper_draft: str = "",
    latex: str = "",
    evidence_ledger: Optional[List[Dict[str, Any]]] = None,
    proof: Optional[Dict[str, Any]] = None,
    server: str = "arxiv",
    template: str = "article",
) -> Dict[str, Any]:
    """Assemble a submission-ready preprint bundle on disk and zip it.

    Returns {"ok", "server", "dir", "zip", "files", "checklist", "note"}.
    """
    server = server if server in SERVERS else "arxiv"
    out = get_output_dir() / "preprints" / (session_id or "session")
    out.mkdir(parents=True, exist_ok=True)

    tex = latex or latex_outline(topic, template)["latex"]
    (out / "paper.tex").write_text(tex, encoding="utf-8")

    if paper_draft:
        (out / "draft.md").write_text(paper_draft, encoding="utf-8")

    bib = _bibliography_from_ledger(evidence_ledger or [])
    (out / "references.bib").write_text(bib or "% no verified DOI-backed references found\n",
                                        encoding="utf-8")

    metadata = {
        "title": topic,
        "session_id": session_id,
        "target_server": server,
        "verified_references": bib.count("@article"),
        "proof_content_hash": (proof or {}).get("content_hash"),
        "proof_sig_algo": (proof or {}).get("sig_algo"),
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    checklist = _CHECKLISTS[server]
    checklist_md = "\n".join(
        [f"# Submission checklist — {server}", "",
         "Aurelius prepares the bundle; **submission itself is manual by design** "
         "(preprint servers require human endorsement/moderation and prohibit automated "
         "submission).", ""]
        + [f"{i}. {item}" for i, item in enumerate(checklist, 1)]
        + ["", "Bundle contents: paper.tex, references.bib, draft.md, metadata.json."]
    )
    (out / "SUBMISSION_CHECKLIST.md").write_text(checklist_md, encoding="utf-8")

    files = ["paper.tex", "references.bib", "metadata.json", "SUBMISSION_CHECKLIST.md"]
    if paper_draft:
        files.insert(2, "draft.md")

    zip_path = out.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in files:
            zf.write(out / name, arcname=name)

    return {
        "ok": True,
        "server": server,
        "dir": str(out),
        "zip": str(zip_path),
        "files": files,
        "checklist": checklist,
        "note": "Bundle ready. Submission is manual by design - see SUBMISSION_CHECKLIST.md.",
    }


def _bibliography_from_ledger(ledger: List[Dict[str, Any]]) -> str:
    """BibTeX for every *verified* citation in the ledger that resolved to a real work."""
    entries: List[str] = []
    for item in ledger:
        if item.get("type") != "citation" or item.get("verdict") != "verified":
            continue
        for src in item.get("sources", []):
            if src and src.get("title"):
                entries.append(to_bibtex(src))
                break
    return "\n\n".join(entries)
